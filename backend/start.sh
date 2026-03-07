#!/bin/bash
# start.sh

echo "Starting Autotube Backend & Celery Worker..."

# Run database migrations to initialize tables on the fresh Supabase database
echo "Running database migrations..."
python -m alembic upgrade head

# Seed the environment with basic startup accounts (Enterprise User)
python seed_admin.py

# Start Celery worker in the background (Concurrency 1 to prevent OOM on Free Tier)
python -m celery -A app.worker.celery worker --beat --concurrency=1 --loglevel=info &

# Start Uvicorn web server in the foreground
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} &

# Wait for any process to exit
wait -n
exit $?
