#!/bin/sh
# Docker entrypoint script for Face Check-in application
# Runs database migrations before starting gunicorn

set -e

echo "=========================================="
echo "Face Check-in - Starting Container"
echo "=========================================="

# Ensure database directory exists for SQLite
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "^sqlite"; then
    # Strip the sqlite:// prefix to get the absolute path (e.g. sqlite:///data/db.sqlite3 -> /data/db.sqlite3)
    DB_PATH=$(echo "$DATABASE_URL" | sed 's|sqlite://||')
    DB_DIR=$(dirname "$DB_PATH")
    if [ "$DB_DIR" != "." ] && [ "$DB_DIR" != "/" ]; then
        echo "Creating database directory: $DB_DIR"
        mkdir -p "$DB_DIR"
        chmod 755 "$DB_DIR"
    fi
fi

# Wait for PostgreSQL to be ready before running migrations
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "^postgresql"; then
    echo "Waiting for PostgreSQL to be ready..."
    # Extract host and port from DATABASE_URL (postgresql://user:pass@host:port/db)
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^@]+@([^:/]+).*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^@]+@[^:]+:([0-9]+).*|\1|')
    DB_PORT=${DB_PORT:-5432}
    RETRIES=30
    until nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null || [ "$RETRIES" -eq 0 ]; do
        echo "  PostgreSQL not ready yet (${RETRIES} retries left)..."
        RETRIES=$((RETRIES - 1))
        sleep 2
    done
    if [ "$RETRIES" -eq 0 ]; then
        echo "✗ PostgreSQL did not become ready in time"
        exit 1
    fi
    echo "✓ PostgreSQL is ready"
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
