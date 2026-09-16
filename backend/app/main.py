from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, jobs, stats, settings

tags_metadata = [
    {
        "name": "auth",
        "description": "Operations with users, authentication, and password management.",
    },
    {
        "name": "jobs",
        "description": "Video generation job submission, status tracking, and usage limits.",
    },
    {
        "name": "billing",
        "description": "Subscription tiers, Lemon Squeezy integration, and billing webhooks.",
    },
    {
        "name": "admin",
        "description": "**Restricted**. Platform statistics and user administration operations.",
    },
]

app = FastAPI(
    title="Autotube Enterprise API",
    description="""
    AI-powered YouTube Shorts automation platform.
    
    ## Authentication
    Most endpoints require a JWT Bearer token obtained from `/auth/login`.
    """,
    version="2.0.0",
    openapi_tags=tags_metadata
)

import os

app_url = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://autotube-beta.vercel.app",
    app_url
]

# Note: Add security middleware first so they run early in request lifecycle
from app.middleware import (
    ErrorSanitizationMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware
)

app.add_middleware(ErrorSanitizationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import auth, jobs, stats, settings, videos

# Note: auth.router has prefix="/auth" built-in
app.include_router(auth.router, tags=["auth"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(stats.router, tags=["stats"])
app.include_router(settings.router, tags=["settings"])
app.include_router(videos.router)

# BYOK key vault (Phase 2)
from app.api import keys
app.include_router(keys.router)

# Admin router
from app.api import admin
app.include_router(admin.router, tags=["admin"])

# Billing router
from app.api import billing
app.include_router(billing.router, tags=["billing"])

# Webhook router (for AI video generation callbacks)
from app.api import webhooks
app.include_router(webhooks.router)

# Enterprise
from app.api import workspaces, competitors
app.include_router(workspaces.router)
app.include_router(competitors.router)

# Mount local output directory so generate_only videos can be downloaded from the Dashboard
from fastapi.staticfiles import StaticFiles
from app.core.config import OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# FastAPI's stock 422 body echoes the offending `input` back to the client; for a
# body carrying an API key that would put the key in a response. Keep loc/msg/type only.
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_error_without_echo(request, exc: RequestValidationError):
    errors = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/")
def root():
    return {"status": "ok", "service": "autotube-backend"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "autotube-backend"}
