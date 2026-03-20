#!/bin/sh
set -e

if [ -d "alembic" ]; then
    echo "Running database migrations..."
    # Try normal upgrade first
    if ! alembic upgrade head 2>&1; then
        echo "Normal upgrade failed. Stamping at 008 and retrying..."
        # DB likely has columns through 008 but alembic_version is out of sync
        alembic stamp 008 2>/dev/null || true
        if ! alembic upgrade head 2>&1; then
            echo "Migration still failing, continuing with create_all..."
        fi
    fi
else
    echo "No alembic directory, skipping migrations."
fi

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
