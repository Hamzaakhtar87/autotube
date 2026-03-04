from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, jobs, stats, settings

app = FastAPI(
    title="Autotube API",
    description="AI-powered YouTube Shorts automation platform",
    version="2.0.0"
)

import os

app_url = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    app_url
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Note: auth.router has prefix="/auth" built-in
app.include_router(auth.router, tags=["auth"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(stats.router, tags=["stats"])
app.include_router(settings.router, tags=["settings"])
# Billing router
from app.api import billing
app.include_router(billing.router, tags=["billing"])

# Webhook router (for AI video generation callbacks)
from app.api import webhooks
app.include_router(webhooks.router)

@app.get("/")
def root():
    return {"status": "ok", "service": "autotube-backend"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "autotube-backend"}
