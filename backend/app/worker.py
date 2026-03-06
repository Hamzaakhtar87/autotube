import os
import sys
import logging
from celery import Celery
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.models import Job, JobLog, JobStatus, User
import time
from app.services.email_service import email_service

# Add app and core to sys.path so imports work
# Detect Docker vs local: worker.py is at backend/app/worker.py
_WORKER_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_WORKER_DIR)  # backend/
_CORE_DIR = os.path.join(_BACKEND_DIR, "core")

# Docker paths
if os.path.isdir("/app/core"):
    sys.path.insert(0, "/app")
    sys.path.insert(0, "/app/core")
else:
    # Local dev
    sys.path.insert(0, _BACKEND_DIR)
    sys.path.insert(0, _CORE_DIR)

# Define Celery App
celery = Celery(
    "worker",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler that writes logs to the database for a specific job.
    """
    def __init__(self, job_id, db_session):
        super().__init__()
        self.job_id = job_id
        self.db = db_session

    def emit(self, record):
        try:
            log_entry = JobLog(
                job_id=self.job_id,
                message=self.format(record),
                level=record.levelname,
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception:
            self.handleError(record)

@celery.task(bind=True)
def run_batch_task(self, job_id: int, test_mode: bool = False):
    """
    Celery task that runs the WeeklyBatchAgent.
    It intercepts logs and updates job status in the DB.
    """
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        return "Job not found"

    # Update status to RUNNING
    job.status = JobStatus.RUNNING
    db.commit()

    # Setup DB logging to capture Core output
    db_handler = DatabaseLogHandler(job_id, db)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    db_handler.setFormatter(formatter)
    
    # Attach handler to the root logger used by autotube core
    root_logger = logging.getLogger()
    root_logger.addHandler(db_handler)
    root_logger.setLevel(logging.INFO)

    try:
        # Import here to avoid early config loading issues if any
        from core.main import WeeklyBatchAgent
        
        # Initialize Agent
        root_logger.info(f"🚀 Starting Batch Job #{job_id} (Test Mode: {test_mode})")
        
        # Instantiate and Run
        # Note: We might need to adjust config.py paths in core dynamically if needed, 
        # provided they rely on relative paths or env vars.
        # Assuming core uses relative paths, we need to be in the right CWD 
        # OR ensure config.py handles paths correctly.
        # For now, let's switch CWD to core to be safe for file operations
        
        # Instantiate and Run
        original_cwd = os.getcwd()
        # Use relative path to support both Docker and local dev
        # worker.py is in backend/app, core is in backend/core (sibling)
        core_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core"))
        if not os.path.exists(core_path):
             # Fallback to /app/core if local path logic fails (e.g. running from odd location)
             core_path = "/app/core"
        
        os.chdir(core_path)
        
        # Get count from job config (default to 7 if not specified)
        root_logger.info(f"📂 Job Config detected: {job.config}")
        video_count = job.config.get("video_count", 7)
        root_logger.info(f"🔢 Final video count decided: {video_count}")
        
        # Get user tier, youtube credentials, and preferences
        user_tier = "free"
        youtube_creds = None
        user_preferences = {}
        user_email = None
        
        if job.user_id:
            user = db.query(User).filter(User.id == job.user_id).first()
            if user:
                user_email = user.email
            if user and hasattr(user, 'subscription_tier'):
                user_tier = user.subscription_tier or "free"
            
            # Load user preferences
            if user and hasattr(user, 'preferences') and user.preferences:
                user_preferences = user.preferences
                root_logger.info(f"⚙️ User preferences loaded: voice={user_preferences.get('voice', 'default')}, "
                                 f"bg_music={user_preferences.get('bg_music', True)}")
                
            # Grab user's connected YouTube credentials from the SaaS DB
            from app.models.models import YouTubeAccount
            account = db.query(YouTubeAccount).filter(YouTubeAccount.user_id == job.user_id).first()
            if account and account.credentials_json:
                youtube_creds = account.credentials_json
                
        # Get video_format and output_action from job config
        video_format = job.config.get("video_format", "short") if job.config else "short"
        output_action = job.config.get("output_action", "generate_only") if job.config else "generate_only"
        schedule_datetime = job.config.get("schedule_datetime", "") if job.config else ""
        
        # Inject into user_preferences so the agent pipeline can use them
        user_preferences["video_format"] = video_format
        user_preferences["output_action"] = output_action
        user_preferences["schedule_datetime"] = schedule_datetime
            
        root_logger.info(f"🎨 Visual tier: {user_tier} | Format: {video_format} | Action: {output_action}")
        if youtube_creds:
            root_logger.info("🔗 Found connected YouTube account for upload")
        elif not test_mode:
            root_logger.warning("⚠️ No connected YouTube account found! Upload may fail if no local credentials exist.")
            
        agent = WeeklyBatchAgent(
            test_mode=test_mode, 
            user_tier=user_tier, 
            youtube_creds=youtube_creds,
            preferences=user_preferences
        )
        success = agent.run_weekly_batch(limit=video_count)
        
        # Restore CWD
        os.chdir(original_cwd)
        
        if success:
            job.status = JobStatus.COMPLETED
            if user_email: email_service.send_job_completion(user_email, job_id, "completed")
            root_logger.info("✅ Job finished successfully")
        else:
            job.status = JobStatus.FAILED
            if user_email: email_service.send_job_completion(user_email, job_id, "failed")
            root_logger.error("❌ Job reported failure")

    except Exception as e:
        job.status = JobStatus.FAILED
        try:
            if 'user_email' in locals() and user_email: 
                email_service.send_job_completion(user_email, job_id, "failed")
        except: pass
        root_logger.error(f"❌ critical error in worker: {str(e)}")
    finally:
        # Capture status before closing session (avoid DetachedInstanceError)
        final_status = str(job.status) if job else "unknown"
        root_logger.removeHandler(db_handler)
        db.commit()
        db.close()

    return final_status
