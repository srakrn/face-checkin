# TASKS.md — Face Check-in Implementation Checklist

This file tracks implementation tasks for the Face Check-in project.
Each task is self-contained and LLM-agent-friendly: it names the files to touch,
the acceptance criteria, and any dependencies.

Legend: `[ ]` pending · `[-]` in progress · `[x]` done

---

## Phase 0 — Project bootstrap

- [x] **TASK-001** Initialise Git repository (`git init`, `main` branch)
- [x] **TASK-002** Create `requirements.txt` and `requirements-dev.txt`
- [x] **TASK-003** Create Django project skeleton (`face_checkin/` package, `manage.py`)
- [x] **TASK-004** Create settings split: `base.py`, `development.py`, `production.py`
- [x] **TASK-005** Create root `urls.py` wiring all app URL modules
- [x] **TASK-006** Create `apps/faces/` app with `FaceGroup` + `Face` models and admin
- [x] **TASK-007** Create `apps/classes/` app with `Class` + `ClassTag` models and admin
- [x] **TASK-008** Create `apps/sessions/` app with `Session` model, state machine, and admin
- [x] **TASK-009** Create `apps/checkin/` app with `CheckIn` model and admin
- [x] **TASK-010** Create `apps/checkin/matching.py` — cosine similarity face matching
- [x] **TASK-011** Create `POST /api/checkin/match/` view (`apps/checkin/views.py`)
- [x] **TASK-012** Create `GET /api/sessions/<pk>/` and `GET /api/sessions/<pk>/report/` views
- [x] **TASK-013** Create `GET /api/sessions/<pk>/embeddings/` view
- [x] **TASK-014** Create kiosk HTML view (`apps/checkin/kiosk_views.py` + `templates/checkin/kiosk.html`)
- [x] **TASK-015** Create `auto_close_sessions` management command
- [x] **TASK-016** Create `Dockerfile` (Python 3.12-slim, gunicorn)
- [x] **TASK-017** Create `docker-compose.yml` with `sqlite` and `postgres` profiles
- [x] **TASK-018** Create `docker/Caddyfile` reverse proxy config
- [x] **TASK-019** Create `.env.example` with all required variables documented
- [x] **TASK-020** Create `.gitignore`
- [x] **TASK-021** Create `AGENTS.md` coding-agent guide
- [x] **TASK-022** Create `pytest.ini`

---

## Phase 1 — Migrations & initial data

- [ ] **TASK-101** Run `python manage.py makemigrations` for all apps and commit migration files
  - Files: `apps/faces/migrations/`, `apps/classes/migrations/`, `apps/sessions/migrations/`, `apps/checkin/migrations/`
  - Acceptance: `python manage.py migrate` runs without errors on a fresh SQLite DB

---

## Phase 2 — Face enrollment UI (admin + webcam)

- [x] **TASK-201** Add webcam capture widget to the Face admin change form
  - Files: `apps/faces/admin.py`, `templates/admin/faces/face/change_form.html`, `static/js/webcam_capture.js`
  - Acceptance: Admin can open a face record, click "Capture from webcam", take a photo, and it populates the `photo` field
  - Notes: Use `getUserMedia`, draw to canvas, convert to base64, POST to a dedicated upload endpoint

- [x] **TASK-202** Create face enrollment endpoint that accepts a photo, runs face detection client-side (face-api.js), and saves the embedding
  - Files: `apps/faces/views.py`, `apps/faces/urls.py`
  - Acceptance: `POST /faces/<pk>/enroll/` with a photo file → extracts embedding via face-api.js in browser → saves `Face.embedding`
  - Notes: Embedding extraction happens in the browser; the server receives the embedding as a JSON array alongside the photo

- [ ] **TASK-203** Add bulk photo upload to FaceGroup admin
  - Files: `apps/faces/admin.py`, `templates/admin/faces/facegroup/change_form.html`
  - Acceptance: Admin can upload multiple photos at once; each photo creates a new `Face` record in the group

---

## Phase 3 — Kiosk UI polish

- [ ] **TASK-301** Style the kiosk page with a clean, full-screen layout suitable for a tablet
  - Files: `templates/checkin/kiosk.html`, `static/css/kiosk.css`
  - Acceptance: Page fills the viewport; camera preview is centred; status messages are large and readable; "Take Photo" button is prominent

- [ ] **TASK-302** Add face detection overlay on the kiosk camera preview
  - Files: `templates/checkin/kiosk.html`
  - Acceptance: A bounding box is drawn around the detected face in real-time using face-api.js `detectAllFaces` in a `requestAnimationFrame` loop

- [ ] **TASK-303** Add session-closed / session-not-found error states to the kiosk page
  - Files: `templates/checkin/kiosk.html`, `apps/checkin/kiosk_views.py`
  - Acceptance: If the session is `closed` or `draft`, the kiosk shows a clear message instead of the camera

- [ ] **TASK-304** Implement client-side embedding cache using `/api/sessions/<pk>/embeddings/`
  - Files: `templates/checkin/kiosk.html`
  - Acceptance: On page load, the kiosk fetches all embeddings and stores them in memory; matching is done client-side first, then confirmed server-side

---

## Phase 4 — Session management UI

- [ ] **TASK-401** Create a session list/detail page (HTMX-powered) for admins
  - Files: `apps/sessions/views.py`, `apps/sessions/urls.py`, `templates/sessions/`
  - Acceptance: Admin can see all sessions for a class, with state badges; can activate/close sessions via HTMX buttons without full page reload

- [ ] **TASK-402** Create a session report page
  - Files: `apps/sessions/views.py`, `templates/sessions/report.html`
  - Acceptance: Shows a table of all check-ins for a session: participant name, custom ID, time, matched/unmatched; exportable to CSV

---

## Phase 5 — Testing

- [ ] **TASK-501** Write unit tests for `apps/checkin/matching.py`
  - Files: `apps/checkin/tests/test_matching.py`
  - Acceptance: Tests cover: exact match, no match (below threshold), empty face group, zero-norm vector edge case

- [ ] **TASK-502** Write unit tests for `Session` state machine
  - Files: `apps/sessions/tests/test_models.py`
  - Acceptance: Tests cover: valid transitions (draft→active, active→closed), invalid transitions raise `ValueError`, `should_auto_close` property

- [ ] **TASK-503** Write integration tests for `POST /api/checkin/match/`
  - Files: `apps/checkin/tests/test_views.py`
  - Acceptance: Tests cover: matched check-in, unmatched check-in, duplicate check-in, inactive session rejection, missing fields

- [ ] **TASK-504** Write integration tests for session API views
  - Files: `apps/sessions/tests/test_views.py`
  - Acceptance: Tests cover: `session_detail` returns correct JSON, `session_report` lists all check-ins

- [ ] **TASK-505** Write tests for `auto_close_sessions` management command
  - Files: `apps/sessions/tests/test_commands.py`
  - Acceptance: Command closes sessions past `auto_close_at`; does not close sessions before `auto_close_at`; does not touch draft/closed sessions

---

## Phase 6 — Deployment hardening

- [ ] **TASK-601** Add `python manage.py migrate` to Docker entrypoint / startup script
  - Files: `Dockerfile` or a new `docker/entrypoint.sh`
  - Acceptance: Container runs migrations automatically on startup before gunicorn starts

- [ ] **TASK-602** Configure periodic `auto_close_sessions` execution inside Docker
  - Files: `docker-compose.yml` or a new `docker/cron` service
  - Acceptance: `auto_close_sessions` runs every minute inside the container

- [ ] **TASK-603** Add health-check endpoint
  - Files: `face_checkin/urls.py`, a simple view returning `{"status": "ok"}`
  - Acceptance: `GET /health/` returns HTTP 200 with `{"status": "ok"}`; Docker Compose `healthcheck` uses it

- [ ] **TASK-604** Document production deployment steps in `README.md`
  - Files: `README.md` (create)
  - Acceptance: README covers: prerequisites, `.env` setup, Docker Compose commands, first-run superuser creation, face-api.js model download instructions
