"""
App-level configuration for FastAPI authentication and shared settings.
Core video generation settings are in backend/core/config.py.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env as defaults — real environment variables take precedence
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)

# Where the pipeline in backend/core writes finished videos (core/config.py uses the same default).
CORE_DIR = Path(__file__).resolve().parent.parent.parent / "core"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", CORE_DIR / "output_v2"))

# Auth Settings
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
