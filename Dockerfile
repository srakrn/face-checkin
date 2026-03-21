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

# Create necessary directories for SQLite database
RUN mkdir -p /data && chmod 755 /data

# Create non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
# Ensure appuser can access the data directory
RUN chown -R appuser:appgroup /data
USER appuser

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
