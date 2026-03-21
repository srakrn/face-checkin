#!/bin/sh
# Docker entrypoint script for Face Check-in application
# Runs database migrations before starting gunicorn

set -e

echo "=========================================="
echo "Face Check-in - Starting Container"
echo "=========================================="

echo "Running database migrations..."
python manage.py migrate --noinput

if [ $? -eq 0 ]; then
    echo "✓ Database migrations completed successfully"
else
    echo "✗ Database migrations failed"
    exit 1
fi

echo "=========================================="
echo "Starting gunicorn web server..."
echo "=========================================="

exec gunicorn face_checkin.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
