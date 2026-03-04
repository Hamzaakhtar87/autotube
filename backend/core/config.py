import os
import yaml
import psutil
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env as DEFAULTS only — Docker-injected env vars take precedence
load_dotenv(Path(__file__).parent / ".env", override=False)

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yml"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    if not CONFIG_PATH.exists():
        logger.error(f"❌ config.yml missing at {CONFIG_PATH}")
        raise FileNotFoundError("config.yml missing")

    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

CONF = load_config()

# ============================================================================
# EXPORTED CONFIGS
# ============================================================================

# System & Safety
TEST_MODE = CONF["system"]["test_mode"]
RAM_MIN_GB = CONF["system"]["ram_min_gb"]
LOAD_TIMEOUT_SEC = CONF["system"]["load_timeout_sec"]
LOG_LEVEL = CONF["system"]["log_level"]

# Paths
MEMORY_FILE = BASE_DIR / "memory.json"
OUTPUT_DIR = BASE_DIR / "output_v2"
TEMP_DIR = BASE_DIR / "temp_v2"
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# ============================================================================
# LLM Settings (Cloud-first: Gemini Flash API)
# ============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_ENGINE = "gemini"  # Cloud LLM, no local model needed
MODEL_MAX_CONTEXT = CONF["model"]["max_context"]
MODEL_TEMP = CONF["model"]["temperature"]
MODEL_TOP_P = CONF["model"]["top_p"]
MODEL_TOP_K = CONF["model"]["top_k"]

# ============================================================================
# AI Video Generation (Tiered Cascade)
# ============================================================================
GEMINIGEN_API_KEY = os.getenv("GEMINIGEN_API_KEY", "")
GEMINIGEN_WEBHOOK_SECRET = os.getenv("GEMINIGEN_WEBHOOK_SECRET", "")

# ============================================================================
# Visual Settings
# ============================================================================
USE_API_VISUALS = CONF["visuals"]["use_api_visuals"]
VISUAL_PRIORITY = CONF["visuals"]["priority_order"]
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_VIDEO_URL = CONF["visuals"]["pexels"]["video_url"]
PEXELS_IMAGE_URL = CONF["visuals"]["pexels"]["image_url"]

# Video Settings
VIDEO_WIDTH = CONF["video"]["width"]
VIDEO_HEIGHT = CONF["video"]["height"]
VIDEO_FPS = CONF["video"]["fps"]
SCRIPT_MIN_DURATION = CONF["video"]["duration"]["min"]
SCRIPT_MAX_DURATION = CONF["video"]["duration"]["max"]
VIDEO_BITRATE = CONF["video"]["bitrate"]
AUDIO_BITRATE = CONF["video"]["audio_bitrate"]
VIDEO_PRESET = CONF["video"]["preset"]
VIDEO_CRF = CONF["video"]["crf"]

# Background Video
BACKGROUND_VIDEO_URL = CONF["video"]["background_video_url"]
BACKGROUND_VIDEO_PATH = TEMP_DIR / "autotube_bg.mp4"

# Subtitle Styling
SUBTITLE_FONT = "Impact"
SUBTITLE_SIZE = 85
SUBTITLE_COLOR = "&H0000FFFF"
SUBTITLE_SECONDARY_COLOR = "&H00FFFFFF"
SUBTITLE_OUTLINE_COLOR = "&H00000000"
SUBTITLE_OUTLINE_WIDTH = 3.0
SUBTITLE_SHADOW = 2
SUBTITLE_MARGIN_V = 100

# Voice Settings
VOICE_NAME = CONF["voice"]["name"]
VOICE_RATE = CONF["voice"]["rate"]
VOICE_PITCH = CONF["voice"]["pitch"]

# Upload Settings
UPLOAD_PRIVACY = CONF["upload"]["privacy"]
VIDEOS_PER_BATCH = CONF["upload"]["videos_per_batch"]
UPLOAD_TIME_HOUR = CONF["upload"]["hour"]
UPLOAD_TIME_MINUTE = CONF["upload"]["minute"]

# Content Settings
TOPIC_CATEGORIES = CONF["content"]["categories"]
MAX_TOPICS_IN_MEMORY = CONF["content"]["max_topics_memory"]
ENABLE_TOPIC_VALIDATION = CONF["content"]["validate_topics"]
USE_API_TOPICS = CONF["content"]["use_api_topics"]

# Trend Sources
GOOGLE_TRENDS_RSS = CONF["trend_sources"]["google_trends_rss"]
REDDIT_SUBREDDITS = CONF["trend_sources"]["reddit_subreddits"]

# YouTube OAuth
YOUTUBE_CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
YOUTUBE_CREDENTIALS = BASE_DIR / "credentials.json"

# Auth Settings (FastAPI)
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Logging
LOG_FILE = BASE_DIR / "autotube.log"
