# AGENTS.md — Coding Agent Guide

This document describes the project structure, conventions, and workflow for AI coding agents (LLMs) working on the **Face Check-in** codebase.

---

## Project overview

A Django web application for face-based attendance check-in.

- **Frontend**: AlpineJS + HTMX, served via Django templates.
- **Backend**: Django 5.x (Python 3.12).
- **Face recognition**: face-api.js runs entirely in the browser; the server only does embedding comparison.
- **Deployment**: Docker Compose with SQLite or PostgreSQL profiles; Cloudflare cloudflared provides HTTPS.

---

## Repository layout

```
face-checkin/
├── apps/
│   ├── faces/          # FaceGroup + Face models; enrollment logic
│   ├── classes/        # Class + ClassTag models
│   ├── sessions/       # Session model + state machine + auto-close/open commands
│   └── checkin/        # CheckIn model, matching logic, API views, kiosk view
├── face_checkin/
│   ├── settings/
│   │   ├── base.py         # Shared settings
│   │   ├── development.py  # Dev overrides (debug toolbar, etc.)
│   │   └── production.py   # Production hardening
│   ├── urls.py
│   └── wsgi.py
├── templates/
│   ├── base.html
│   └── checkin/
│       └── kiosk.html      # Kiosk check-in page (AlpineJS + face-api.js)
├── static/
│   └── js/face-api/        # face-api.js bundle + model weights (committed)
├── docker/
│   ├── entrypoint.sh
│   └── scheduler.sh
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── pyproject.toml
├── pytest.ini
├── .env.example
├── SPECS.md
└── TASKS.md
```

---

## Key models

| Model | App | Notes |
|-------|-----|-------|
| `FaceGroup` | `apps.faces` | Collection of enrolled faces |
| `Face` | `apps.faces` | Participant; stores embedding as raw `float32` bytes |
| `Class` | `apps.classes` | Groups sessions; tied to one `FaceGroup` |
| `ClassTag` | `apps.classes` | Many tags per class |
| `Session` | `apps.sessions` | Check-in slot; states: `draft → active → closed` |
| `CheckIn` | `apps.checkin` | Every attempt (matched or not); stores raw face image |

---

## API endpoints

| Method | URL | View | Description |
|--------|-----|------|-------------|
| `POST` | `/api/checkin/match/` | `apps.checkin.views.checkin_match` | Submit embedding + image; returns match result |
| `GET` | `/api/sessions/<pk>/` | `apps.sessions.views.session_detail` | Session state |
| `GET` | `/api/sessions/<pk>/report/` | `apps.sessions.views.session_report` | Check-in report |
| `GET` | `/kiosk/<session_id>/` | `apps.checkin.kiosk_views.kiosk` | Kiosk HTML page |
| `GET` | `/health/` | — | Health check endpoint |

---

## Face matching

- Embeddings are 128-d `float32` vectors produced by face-api.js (`FaceRecognitionNet`).
- Stored in `Face.embedding` as raw bytes (`numpy.ndarray.tobytes()`).
- Matching: cosine similarity in [`apps/checkin/matching.py`](apps/checkin/matching.py).
- Threshold controlled by `FACE_MATCH_THRESHOLD` env var (default `0.6`).

---

## Session state machine

```
Draft ──activate()──▶ Active ──close()──▶ Closed
```

- `Session.activate()` / `Session.close()` enforce valid transitions.
- `auto_close_sessions` management command closes overdue active sessions.
- `auto_open_sessions` management command activates sessions whose scheduled time has passed.
- Both commands run periodically via the `scheduler` Docker service (every 60 seconds).
- Run manually: `python manage.py auto_close_sessions` / `python manage.py auto_open_sessions`.

---

## Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | Django secret key |
| `DEBUG` | `False` | Enable debug mode |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hosts |
| `DATABASE_URL` | SQLite | dj-database-url connection string |
| `POSTGRES_USER` | `face` | PostgreSQL username (Docker postgres profile) |
| `POSTGRES_PASSWORD` | `face` | PostgreSQL password (Docker postgres profile) |
| `POSTGRES_DB` | `face_checkin` | PostgreSQL database name (Docker postgres profile) |
| `USE_S3` | `False` | Use Backblaze B2 for file storage |
| `AWS_*` | — | B2 credentials (when `USE_S3=True`) |
| `TIME_ZONE` | `UTC` | IANA timezone name for admin/template display |
| `FACE_MATCH_THRESHOLD` | `0.6` | Cosine similarity threshold |
| `CSRF_TRUSTED_ORIGINS` | (none) | Comma-separated HTTPS origins for CSRF (e.g., `https://example.com`) |
| `TUNNEL_TOKEN` | (none) | Cloudflare tunnel token (required for cloudflared Docker service) |
| `DJANGO_SUPERUSER_USERNAME` | (none) | Auto-created superuser username on first container start |
| `DJANGO_SUPERUSER_EMAIL` | (none) | Auto-created superuser email on first container start |
| `DJANGO_SUPERUSER_PASSWORD` | (none) | Auto-created superuser password on first container start |

Copy `.env.example` → `.env` and fill in values before running.

---

## Development setup

```bash
uv sync                        # creates .venv and installs all deps (including dev)
cp .env.example .env           # edit as needed
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Settings module used by `manage.py`: `face_checkin.settings.development`.

---

## Running tests

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov
```

---

## Docker

```bash
# SQLite (default, lightweight)
docker compose --profile sqlite up --build

# PostgreSQL
docker compose --profile postgres up --build
```

The Docker deployment includes a `scheduler` service that automatically runs `auto_close_sessions` and `auto_open_sessions` every 60 seconds (configured in `docker/scheduler.sh`).

---

## Conventions for agents

1. **One concern per app**: `faces` owns enrollment, `sessions` owns lifecycle, `checkin` owns the matching pipeline and kiosk UI.
2. **No REST framework**: Use plain Django views returning `JsonResponse`. HTMX handles partial HTML updates.
3. **Embedding bytes**: Always serialise with `numpy.ndarray.tobytes()` and deserialise with `numpy.frombuffer(..., dtype='float32')`.
4. **State transitions**: Always use `Session.activate()` / `Session.close()` — never set `state` directly.
5. **All check-ins are logged**: Even duplicates and unmatched attempts. Never skip `CheckIn` creation.
6. **Static face-api.js assets**: `face-api.min.js` and model weight files are committed under `static/js/face-api/`. No additional download required.
7. **Migrations**: After changing models, run `python manage.py makemigrations` and commit the migration files.
8. **Tests**: Place tests in `tests/` at the app level or in a top-level `tests/` directory. Use `pytest-django`.
9. **Template styling**: Prefer plain Bootstrap markup and utilities over custom CSS. Keep pages visually simple, boring, and efficient; avoid decorative styling like custom shadows, fancy spacing systems, or bespoke component classes unless required for functionality (for example kiosk camera UI or print-specific report rules).
