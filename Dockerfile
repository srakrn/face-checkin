FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=face_checkin.settings.production

WORKDIR /app

# Install system dependencies (including curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Copy Docker scripts
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/scheduler.sh /app/scheduler.sh
RUN chmod +x /app/entrypoint.sh /app/scheduler.sh

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Create necessary directories for SQLite database and set ownership
# VOLUME must be declared AFTER chown so Docker initialises the volume with correct ownership
RUN mkdir -p /data && chown -R appuser:appgroup /data && chmod 755 /data

USER appuser

# Declare volume after ownership is set so Docker copies the ownership into new volumes
VOLUME ["/data"]

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
