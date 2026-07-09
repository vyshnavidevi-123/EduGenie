# ER Diagram

## Current state

EduGenie's core app (`main.py`) is **stateless** — every request to
`/api/ask`, `/api/explain`, `/api/quiz`, `/api/summarize`, and
`/api/learning-path` is answered directly from the AI model and nothing is
persisted. This satisfies the brief's five learning features without a
database, and is why `requirements.txt` doesn't include a DB driver.

The project brief's hardware/software requirements list a database
(SQL / PostgreSQL / SQLite) as an intended part of the stack — that layer
is designed below and ready to add whenever you want to support saved
history, user accounts, or progress tracking.

## Proposed schema (for saved history / accounts)

```mermaid
erDiagram
    USER ||--o{ QUERY_LOG : submits
    USER ||--o{ QUIZ : requests
    USER ||--o{ LEARNING_PATH : requests

    QUIZ ||--|{ QUIZ_QUESTION : contains
    QUIZ ||--o{ QUIZ_ATTEMPT : "attempted via"

    LEARNING_PATH ||--|{ LEARNING_STAGE : contains

    USER {
        int id PK
        string name
        string email
        datetime created_at
    }

    QUERY_LOG {
        int id PK
        int user_id FK
        string feature "ask | explain | summarize"
        text input_text
        text output_text
        string source "gemini | local-lamini"
        datetime created_at
    }

    QUIZ {
        int id PK
        int user_id FK
        string topic
        string difficulty
        datetime created_at
    }

    QUIZ_QUESTION {
        int id PK
        int quiz_id FK
        text question
        json options
        int answer_index
        text explanation
    }

    QUIZ_ATTEMPT {
        int id PK
        int quiz_id FK
        int user_id FK
        int score
        datetime attempted_at
    }

    LEARNING_PATH {
        int id PK
        int user_id FK
        string topic
        string current_level
        string goal
        datetime created_at
    }

    LEARNING_STAGE {
        int id PK
        int learning_path_id FK
        string stage_name
        json focus_areas
        json resources_to_seek
        string estimated_time
        int sequence_order
    }
```

## Notes

- **USER** anchors all history so a student can revisit past answers, quizzes,
  and learning paths.
- **QUERY_LOG** stores every Ask/Explain/Summarize interaction, including
  which backend (`gemini` vs `local-lamini`) answered it — useful both for
  a "history" feature and for auditing model usage/cost.
- **QUIZ** / **QUIZ_QUESTION** normalize the JSON quiz payload the API
  already returns, so a saved quiz can be re-taken later.
- **QUIZ_ATTEMPT** is separate from **QUIZ** so the same quiz can be
  attempted multiple times and scored for progress tracking.
- **LEARNING_PATH** / **LEARNING_STAGE** mirror the existing
  `LearningPathResponse` schema in `app/schemas.py`, just normalized into
  rows instead of nested JSON.
- Recommended engine: **SQLite** for local development (zero setup, matches
  the brief's "Database(sql/PostgreSQL/sqlite)" requirement), **PostgreSQL**
  for production. `SQLAlchemy` + `Alembic` would be the natural fit if this
  layer is implemented, since the app is already async/FastAPI-based.
