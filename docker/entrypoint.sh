#!/bin/sh
# Docker entrypoint script for Face Check-in application
# Runs database migrations before starting gunicorn

set -e

echo "=========================================="
echo "Face Check-in - Starting Container"
echo "=========================================="

# Ensure database directory exists for SQLite
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "^sqlite"; then
    DB_PATH=$(echo "$DATABASE_URL" | sed 's|sqlite://||')
    DB_DIR=$(dirname "$DB_PATH")
    if [ "$DB_DIR" != "." ]; then
        echo "Creating database directory: $DB_DIR"
        mkdir -p "$DB_DIR"
        chmod 755 "$DB_DIR"
    fi
fi

echo "Running database migrations..."
python manage.py migrate --noinput

if [ $? -eq 0 ]; then
    echo "✓ Database migrations completed successfully"
else
    echo "✗ Database migrations failed"
    exit 1
fi

# Create superuser from environment variables if configured
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    echo "Creating superuser from environment variables..."
    python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="$DJANGO_SUPERUSER_USERNAME").exists():
    User.objects.create_superuser(
        username="$DJANGO_SUPERUSER_USERNAME",
        email="${DJANGO_SUPERUSER_EMAIL:-}",
        password="$DJANGO_SUPERUSER_PASSWORD"
    )
    print("✓ Superuser '$DJANGO_SUPERUSER_USERNAME' created")
else:
    print("✓ Superuser '$DJANGO_SUPERUSER_USERNAME' already exists")
EOF
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
