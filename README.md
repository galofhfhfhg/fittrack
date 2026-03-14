# 💪 FitTrack

FastAPI + SQLite. Один файл — весь бэкенд.

## Запуск

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Открой http://localhost:8000 — там и сайт, и API.

## Эндпоинты

| Метод  | URL               | Что делает              |
|--------|-------------------|-------------------------|
| GET    | /workouts         | Список (фильтр: ?type=) |
| GET    | /workouts/{id}    | Одна тренировка         |
| POST   | /workouts         | Создать                 |
| PUT    | /workouts/{id}    | Обновить                |
| DELETE | /workouts/{id}    | Удалить                 |
| GET    | /stats            | Вся статистика          |
