from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta

# ── Database ──────────────────────────────────────────────────────────────────
engine = create_engine("sqlite:///./fittrack.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Workout(Base):
    __tablename__ = "workouts"
    id        = Column(Integer, primary_key=True)
    date      = Column(Date, nullable=False)
    type      = Column(String(50), nullable=False)
    duration  = Column(Integer, nullable=False)
    calories  = Column(Integer, default=0)
    notes     = Column(Text, default="")
    exercises = relationship("Exercise", back_populates="workout", cascade="all, delete-orphan")

class Exercise(Base):
    __tablename__ = "exercises"
    id         = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey("workouts.id"), nullable=False)
    name       = Column(String(100), nullable=False)
    sets       = Column(Integer, default=1)
    reps       = Column(Integer, default=1)
    weight     = Column(Float, default=0.0)
    workout    = relationship("Workout", back_populates="exercises")

Base.metadata.create_all(bind=engine)

# ── Schemas ───────────────────────────────────────────────────────────────────
class ExerciseIn(BaseModel):
    name:   str
    sets:   int = 3
    reps:   int = 10
    weight: float = 0.0

class ExerciseOut(ExerciseIn):
    id: int
    class Config:
        from_attributes = True

class WorkoutIn(BaseModel):
    date:      date
    type:      str
    duration:  int
    calories:  int = 0
    notes:     str = ""
    exercises: List[ExerciseIn] = []

class WorkoutOut(BaseModel):
    id:        int
    date:      date
    type:      str
    duration:  int
    calories:  int
    notes:     str
    exercises: List[ExerciseOut] = []
    class Config:
        from_attributes = True

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="FitTrack API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

# ── Workouts CRUD ─────────────────────────────────────────────────────────────
@app.get("/workouts", response_model=List[WorkoutOut])
def list_workouts(type: Optional[str] = None, s: Session = Depends(db)):
    q = s.query(Workout)
    if type:
        q = q.filter(Workout.type == type)
    return q.order_by(Workout.date.desc()).all()

@app.get("/workouts/{wid}", response_model=WorkoutOut)
def get_workout(wid: int, s: Session = Depends(db)):
    w = s.get(Workout, wid)
    if not w:
        raise HTTPException(404, "Не найдено")
    return w

@app.post("/workouts", response_model=WorkoutOut, status_code=201)
def create_workout(data: WorkoutIn, s: Session = Depends(db)):
    w = Workout(date=data.date, type=data.type, duration=data.duration,
                calories=data.calories, notes=data.notes)
    s.add(w)
    s.flush()
    for ex in data.exercises:
        s.add(Exercise(workout_id=w.id, **ex.model_dump()))
    s.commit()
    s.refresh(w)
    return w

@app.put("/workouts/{wid}", response_model=WorkoutOut)
def update_workout(wid: int, data: WorkoutIn, s: Session = Depends(db)):
    w = s.get(Workout, wid)
    if not w:
        raise HTTPException(404, "Не найдено")
    for k, v in data.model_dump(exclude={"exercises"}).items():
        setattr(w, k, v)
    s.query(Exercise).filter(Exercise.workout_id == wid).delete()
    for ex in data.exercises:
        s.add(Exercise(workout_id=wid, **ex.model_dump()))
    s.commit()
    s.refresh(w)
    return w

@app.delete("/workouts/{wid}", status_code=204)
def delete_workout(wid: int, s: Session = Depends(db)):
    w = s.get(Workout, wid)
    if not w:
        raise HTTPException(404, "Не найдено")
    s.delete(w)
    s.commit()

# ── Stats ─────────────────────────────────────────────────────────────────────
@app.get("/stats")
def stats(s: Session = Depends(db)):
    ws = s.query(Workout).all()
    total     = len(ws)
    total_min = sum(w.duration for w in ws)
    total_cal = sum(w.calories for w in ws)

    # streak
    dates = sorted({w.date for w in ws}, reverse=True)
    streak, prev = 0, None
    for d in dates:
        if prev is None:
            if (date.today() - d).days > 1:
                break
            streak += 1; prev = d
        elif (prev - d).days == 1:
            streak += 1; prev = d
        else:
            break

    # weekly (последние 7 дней)
    today = date.today()
    weekly = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        rows = [w for w in ws if w.date == day]
        weekly.append({"date": day.isoformat(), "minutes": sum(w.duration for w in rows), "calories": sum(w.calories for w in rows)})

    # by type
    type_map: dict = {}
    for w in ws:
        type_map[w.type] = type_map.get(w.type, 0) + 1

    # by month
    month_map: dict = {}
    for w in ws:
        key = w.date.strftime("%Y-%m")
        month_map[key] = month_map.get(key, 0) + w.duration

    return {
        "total_workouts": total,
        "total_minutes":  total_min,
        "total_calories": total_cal,
        "avg_duration":   round(total_min / total, 1) if total else 0,
        "streak_days":    streak,
        "weekly":         weekly,
        "by_type":        [{"type": k, "count": v} for k, v in type_map.items()],
        "by_month":       [{"month": k, "minutes": v} for k, v in sorted(month_map.items())],
    }

# Отдаём фронтенд
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
