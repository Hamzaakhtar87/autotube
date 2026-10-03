"""Load the repo .env before any app submodule reads os.environ.

This must live here, not in app.core.config: app.db builds its SQLAlchemy
engine at import time, and main.py imports the api package (-> app.db)
before anything imports app.core.config. A package __init__ is the only
spot guaranteed to run first for every entrypoint (uvicorn, pytest,
python -m app.niches.seed).

override=False: real environment variables win, so tests (conftest sets
DATABASE_URL before importing app) and deploy platforms are unaffected.
"""
from pathlib import Path

from dotenv import load_dotenv

# backend/app/__init__.py -> backend -> autotube/.env (the repo's gitignored env file)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
