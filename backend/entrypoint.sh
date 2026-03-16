#!/bin/sh
set -e

# Run Alembic migrations (stamp if first run, then upgrade)
echo "Running database migrations..."
alembic upgrade head 2>/dev/null || {
    echo "Migration failed — stamping base and retrying..."
    # DB was created by create_all without Alembic tracking.
    # Remove it and let create_all + migrations work from scratch.
    rm -f /data/simulator.db
    echo "Removed stale DB, will recreate on startup."
}

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
