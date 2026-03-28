FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=face_checkin.settings.production \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install system dependencies (including curl for health checks and gosu for privilege dropping)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies from lockfile (no dev deps)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy project
COPY . .

# Copy Docker scripts
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/scheduler.sh /app/scheduler.sh
RUN chmod +x /app/entrypoint.sh /app/scheduler.sh

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user for running the application
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Create necessary directories for SQLite database
# The entrypoint (running as root) will chown /data to appuser at runtime,
# which handles both new volumes and pre-existing root-owned volumes.
RUN mkdir -p /data

EXPOSE 8000

# Entrypoint runs as root so it can fix /data ownership, then drops to appuser via gosu
CMD ["/app/entrypoint.sh"]
