# Face Check-in

A Django web application for face-based attendance check-in with time logging.

## Features

- **Face-based Check-in**: Participants check in by showing their face to a camera
- **Face Enrollment**: Easy enrollment via photo upload or direct webcam capture
- **Session Management**: Create and manage check-in sessions with automatic open/close times
- **Real-time Recognition**: Client-side face detection using face-api.js
- **Kiosk Mode**: Full-screen tablet-optimized check-in interface
- **Reports**: View and export attendance reports

## Tech Stack

- **Backend**: Django 5.x (Python 3.12)
- **Frontend**: AlpineJS + HTMX, served via Django templates
- **Face Recognition**: face-api.js (TensorFlow.js-based)
- **Database**: SQLite (development) or PostgreSQL (production)
- **Reverse Proxy**: Caddy
- **Deployment**: Docker & Docker Compose

## Quick Start (Development)

### Prerequisites

- Python 3.12+
- uv package manager
- Modern browser with webcam support

### Setup

1. **Clone the repository**

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Copy environment file**
   ```bash
   cp .env.example .env
   ```

4. **Edit `.env` with your settings** (see Configuration Reference below)

5. **Run migrations**
   ```bash
   uv run python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   uv run python manage.py createsuperuser
   ```

7. **Start development server**
   ```bash
   uv run python manage.py runserver
   ```

8. **Access the application**
   - Admin panel: http://localhost:8000/admin/
   - Kiosk mode: http://localhost:8000/kiosk/<session_id>/

## Production Deployment with Docker

### Prerequisites

- Docker & Docker Compose
- At least 1GB RAM
- Modern browser with webcam support (for kiosk devices)

### Quick Start (Docker)

1. **Clone and configure**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with production settings**

3. **Start with SQLite (recommended for small deployments)**
   ```bash
   docker compose --profile sqlite up --build
   ```

4. **Or start with PostgreSQL**
   ```bash
   docker compose --profile postgres up --build
   ```

5. **Create superuser**
   ```bash
   docker compose exec django_sqlite python manage.py createsuperuser
   # For PostgreSQL: docker compose exec django_postgres python manage.py createsuperuser
   ```

6. **Access the application**
   - Application: http://localhost
   - Health check: http://localhost/health/

### Docker Profiles

The application supports two profiles:

| Profile | Description | Use Case |
|---------|-------------|----------|
| `sqlite` | SQLite database on persistent volume | Small deployments, development |
| `postgres` | PostgreSQL database | Production with multiple users |

### Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Caddy      │───▶│   Django     │    │  Scheduler   │  │
│  │ (Reverse     │    │   (Gunicorn) │    │  (Session    │  │
│  │  Proxy)      │    │              │    │   Manager)   │  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘  │
│                            │                                │
│                    ┌───────┴───────┐                      │
│                    │  SQLite/Postgres │                   │
│                    │   Database      │                   │
│                    └─────────────────┘                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | Django secret key |
| `DEBUG` | `False` | Enable debug mode |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hosts |
| `DATABASE_URL` | SQLite | Database connection string |
| `USE_S3` | `False` | Use Backblaze B2 for file storage |
| `AWS_*` | — | B2 credentials (when `USE_S3=True`) |
| `TIME_ZONE` | `UTC` | IANA timezone for admin/template display |
| `FACE_MATCH_THRESHOLD` | `0.6` | Cosine similarity threshold (0.0-1.0) |

### Example `.env` for Production

```bash
# Security
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (SQLite profile)
DATABASE_URL=sqlite:////data/db.sqlite3

# Or PostgreSQL profile
# DATABASE_URL=postgresql://user:password@db:5432/face_checkin

# Timezone
TIME_ZONE=Asia/Bangkok

# Face Matching
FACE_MATCH_THRESHOLD=0.6
```

### Face Matching Threshold Tuning

The `FACE_MATCH_THRESHOLD` controls how strict the face matching is:

- **Lower (0.4-0.5)**: More permissive, may accept different people
- **Default (0.6)**: Balanced accuracy
- **Higher (0.7-0.8)**: Stricter, may reject legitimate matches

## Face-api.js Models

The required face recognition models are already included in the repository:

- **SSD MobileNetV1**: Face detection model
- **Face Landmark 68**: Facial landmark detection
- **Face Recognition**: Face embedding extraction

Models are located in: `static/js/face-api/models/`

No additional download is required.

## Usage Guide

### 1. Create Face Groups

1. Log in to the admin panel: http://localhost/admin/
2. Navigate to **Face groups** → Add Face group
3. Enter a name (e.g., "Class A Students")
4. Save

### 2. Enroll Faces

You can enroll faces in two ways:

**Option A: Photo Upload**
1. Open a Face group in admin
2. Add new Face
3. Enter participant details (name, custom_id)
4. Upload a photo
5. Save

**Option B: Webcam Capture**
1. Open a Face in admin
2. Click "Capture from webcam"
3. Allow camera access
4. Position face in frame
5. Click "Capture" to take photo
6. The photo will be saved automatically

### 3. Create Classes

1. Navigate to **Classes** → Add Class
2. Enter class name
3. Select the associated Face group
4. Add tags (optional)
5. Save

### 4. Manage Sessions

1. Navigate to **Sessions** (from the main sidebar)
2. Click on a class to view its sessions
3. Create a new session:
   - Set session name
   - Set scheduled start time
   - Set auto-close time (optional)
4. Activate the session when ready
5. The session will automatically close at the specified time

### 5. Launch Kiosk Mode

1. Find an active session
2. Click the kiosk link or visit: `/kiosk/<session_id>/`
3. The kiosk page will open in full-screen mode
4. Position the camera so faces are detected
5. Participants can check in by showing their face

### 6. View Reports

1. Navigate to **Sessions** → Select a class
2. Click on a session
3. View the check-in report with:
   - Participant names
   - Check-in times
   - Match status (matched/unmatched)
4. Export to CSV if needed

## Management Commands

The application includes several management commands:

### auto_close_sessions

Closes all active sessions whose auto_close_at time has passed.

```bash
python manage.py auto_close_sessions
```

In Docker:
```bash
docker compose exec django_sqlite python manage.py auto_close_sessions
```

### auto_open_sessions

Re-opens all closed sessions whose scheduled_at time has passed.

```bash
python manage.py auto_open_sessions
```

### Scheduler Service

The Docker deployment includes a scheduler service that automatically runs these commands every 60 seconds. This is configured in `docker/scheduler.sh` and runs as the `scheduler_sqlite` or `scheduler_postgres` service.

## Testing

Run the test suite:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov
```

## Session State Machine

Sessions follow a state machine:

```
Draft ──activate()──▶ Active ──close()──▶ Closed
```

- **Draft**: Session created but not active
- **Active**: Session is live and accepting check-ins
- **Closed**: Session has ended

State transitions are enforced by the model methods:
- `session.activate()` - Transition from Draft to Active
- `session.close()` - Transition from Active to Closed

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/checkin/match/` | Submit face embedding for matching |
| `GET` | `/api/sessions/<pk>/` | Get session details |
| `GET` | `/api/sessions/<pk>/report/` | Get session check-in report |
| `GET` | `/api/sessions/<pk>/embeddings/` | Get all embeddings for caching |
| `GET` | `/kiosk/<session_id>/` | Kiosk check-in page |
| `GET` | `/health/` | Health check endpoint |

## Troubleshooting

### Camera Not Working

1. Ensure the browser has camera permissions
2. Use HTTPS (required for camera access in production)
3. Try a different browser (Chrome recommended)

### Face Not Recognized

1. Ensure good lighting on the face
2. Position face directly in front of camera
3. Adjust `FACE_MATCH_THRESHOLD` in settings
4. Ensure face is properly enrolled with clear photo

### Database Issues

1. Check that the database volume is properly mounted
2. For SQLite: ensure `/data` directory is writable
3. For PostgreSQL: verify database credentials

### Docker Issues

1. Check logs: `docker compose logs <service>`
2. Ensure ports are not already in use
3. Restart services: `docker compose restart <service>`

### Common Docker Commands

```bash
# View logs
docker compose logs -f django_sqlite
docker compose logs -f scheduler_sqlite

# Restart service
docker compose restart django_sqlite

# Stop all services
docker compose --profile sqlite down

# Rebuild and start
docker compose --profile sqlite up --build
```

## Project Structure

```
face-checkin/
├── apps/
│   ├── faces/          # FaceGroup + Face models
│   ├── classes/       # Class + ClassTag models
│   ├── sessions/       # Session model + management
│   └── checkin/        # CheckIn model + matching + kiosk
├── face_checkin/       # Django project settings
├── templates/          # HTML templates
├── static/             # CSS, JS, face-api models
├── docker/             # Docker scripts
├── docker-compose.yml  # Container orchestration
├── Dockerfile          # Container image
└── README.md           # This file
```

## Additional Documentation

- [SPECS.md](SPECS.md) - Detailed specifications
- [AGENTS.md](AGENTS.md) - Developer guide for AI agents

## License

MIT License
