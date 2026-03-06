#!/bin/bash
# start.sh
# Entrypoint for Render.com free tier to bypass requiring two instances.
# It starts both the FastAPI web server AND the Celery worker concurrently.

echo "🚀 Starting Autotube Backend & Celery Worker..."

# 1. Start Celery worker in the background
celery -A app.worker.celery worker --beat --loglevel=info &
CELERY_PID=$!

# 2. Start Uvicorn web server in the foreground
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} &
UVICORN_PID=$!

echo "✅ Both processes are running! Waiting..."

# Optional: Add trap to clean up on exit
trap 'kill $CELERY_PID $UVICORN_PID' EXIT

# Wait for any process to exit
wait -n
  
# Exit with status of process that exited first
exit $?
