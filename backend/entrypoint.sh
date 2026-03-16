#!/bin/sh
set -e

# Skip Alembic migrations if not configured — let create_all handle schema.
if [ -d "alembic" ]; then
    echo "Running database migrations..."
    alembic upgrade head 2>/dev/null || {
        echo "Migration failed — stamping base and retrying..."
        alembic stamp head 2>/dev/null || true
        alembic upgrade head 2>/dev/null || echo "Migration still failing, continuing..."
    }
else
    echo "No alembic directory, skipping migrations. Schema managed by create_all."
fi

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
