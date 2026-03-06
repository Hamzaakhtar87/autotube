#!/bin/bash
# start.sh

echo "Starting Autotube Backend & Celery Worker..."

# Start Celery worker in the background
python -m celery -A app.worker.celery worker --beat --loglevel=info &

# Start Uvicorn web server in the foreground
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} &

# Wait for any process to exit
wait -n
exit $?
