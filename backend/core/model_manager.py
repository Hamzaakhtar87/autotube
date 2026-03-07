"""
Model Manager v3: Gemini + Groq LLM cascade with smart rate limiting.

Priority: Gemini 2.5 Flash (best) → Gemini 2.0 Flash → Groq Llama (unlimited fallback)
Rate-limited to stay within Gemini free-tier quotas (5 RPM).
Groq has 14,400 req/day free tier — perfect overflow valve.
"""

import logging
import os
import re
import time
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Models
GEMINI_PRIMARY = "gemini-2.5-flash"
GEMINI_FALLBACK = "gemini-2.0-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Rate limit: 5 requests per minute for Gemini free tier
RATE_LIMIT_RPM = 5
RATE_LIMIT_INTERVAL = 60.0 / RATE_LIMIT_RPM  # 12 seconds between calls


class ModelManager:
    def __init__(self):
        self.gemini_client = None
        self.groq_client = None
        self._last_call_time = 0.0
        self._rate_lock = threading.Lock()
        self._initialize()

    def _initialize(self):
        """Initialize available LLM providers."""
        # 1. Gemini (Primary)
        if GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info(f"🚀 [LLM] Gemini loaded | Model: {GEMINI_PRIMARY} (PRIMARY)")
            except ImportError:
                logger.warning("⚠️ google-genai package not installed")
            except Exception as e:
                logger.error(f"❌ Gemini init failed: {e}")
        else:
            logger.info("ℹ️ GEMINI_API_KEY not set, skipping Gemini")

        # 2. Groq (Fallback — 14,400 req/day free tier, fast)
        if GROQ_API_KEY:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=GROQ_API_KEY)
                logger.info(f"🔄 [LLM] Groq loaded | Model: {GROQ_MODEL} (FALLBACK)")
            except ImportError:
                logger.warning("⚠️ groq package not installed. Run: pip install groq")
            except Exception as e:
                logger.error(f"❌ Groq init failed: {e}")
        else:
            logger.info("ℹ️ GROQ_API_KEY not set, skipping Groq")

        if not self.gemini_client and not self.groq_client:
            logger.error("❌ NO LLM PROVIDERS AVAILABLE. Script generation will fail.")

    def _wait_for_rate_limit(self):
        """Ensure we don't exceed Gemini's per-minute request limit."""
        with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < RATE_LIMIT_INTERVAL:
                wait_time = RATE_LIMIT_INTERVAL - elapsed
                logger.info(f"⏳ Rate limit: waiting {wait_time:.1f}s before next Gemini call...")
                time.sleep(wait_time)
            self._last_call_time = time.time()

    def generate_content(self, prompt: str, task: str = "general") -> str:
        """Generate text: Gemini Primary → Gemini Fallback → Groq → Error."""
        errors = []

        # Try Gemini models first (best quality)
        if self.gemini_client:
            # Try primary
            try:
                self._wait_for_rate_limit()
                result = self._call_gemini(prompt, GEMINI_PRIMARY, task)
                if result:
                    return result
            except Exception as e:
                errors.append(f"Gemini({GEMINI_PRIMARY}): {e}")
                logger.warning(f"⚠️ Gemini primary failed, trying fallback...")

            # Try fallback
            try:
                self._wait_for_rate_limit()
                result = self._call_gemini(prompt, GEMINI_FALLBACK, task)
                if result:
                    return result
            except Exception as e:
                errors.append(f"Gemini({GEMINI_FALLBACK}): {e}")
                logger.warning(f"⚠️ Gemini fallback failed, cascading to Groq...")

        # Groq fallback (no rate limit issues — 14,400 RPD)
        if self.groq_client:
            try:
                result = self._call_groq(prompt, task)
                if result:
                    return result
            except Exception as e:
                errors.append(f"Groq: {e}")
                logger.warning(f"⚠️ Groq failed: {e}")

        logger.error(f"❌ All LLM providers failed: {errors}")
        raise Exception("LLM_SERVICE_UNAVAILABLE")

    def _call_gemini(self, prompt: str, model: str, task: str) -> str:
        """Call Gemini API with rate-limit-aware retry."""
        logger.info(f"🤖 [GEMINI] Generating {task} with {model}...")
        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                safe_prompt = prompt[:4000]
                
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=safe_prompt,
                    config={
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "top_k": 40,
                        "max_output_tokens": 800,
                    }
                )
                result = response.text.strip()
                if not result:
                    raise Exception("EMPTY_RESPONSE")
                return result
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    logger.warning(f"⚠️ Quota exhausted on {model}. Permanently cascading to Groq fallback...")
                    # Permanently disable Gemini for this worker session to prevent further lag
                    self.gemini_client = None
                    raise
                elif attempt < max_retries:
                    wait = 3
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def _call_groq(self, prompt: str, task: str) -> str:
        """Call Groq API with retry."""
        logger.info(f"🤖 [GROQ] Generating {task} with {GROQ_MODEL}...")
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # SECURE: Limit API Exhaustion
                safe_prompt = prompt[:4000]
                
                response = self.groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are an expert AI scriptwriter. Follow instructions strictly."},
                        {"role": "user", "content": safe_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=800, # Hard cap output tokens
                    timeout=15.0 # Strict HTTP timeout
                )
                result = response.choices[0].message.content.strip()
                if not result:
                    raise Exception("EMPTY_RESPONSE")
                return result
            except Exception as e:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"⚠️ Groq attempt {attempt + 1} failed, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def optimize_image_prompt(self, scene_description: str) -> str:
        """
        Skip LLM optimization to conserve API quota.
        Use simple keyword extraction for Pexels search instead.
        """
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'can', 'shall',
            'of', 'in', 'to', 'for', 'with', 'on', 'at', 'from', 'by',
            'as', 'into', 'through', 'during', 'before', 'after', 'and',
            'but', 'or', 'nor', 'not', 'so', 'yet', 'both', 'either',
            'neither', 'each', 'every', 'all', 'any', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'only', 'own', 'same',
            'than', 'too', 'very', 'just', 'that', 'this', 'these', 'those',
            'it', 'its', 'they', 'them', 'their', 'we', 'our', 'you', 'your',
            'he', 'she', 'his', 'her', 'him', 'my', 'me', 'who', 'whom',
            'which', 'what', 'where', 'when', 'how', 'why',
        }
        words = scene_description.split()
        keywords = [w.strip('.,!?;:()[]"\'') for w in words
                     if w.lower().strip('.,!?;:()[]"\'') not in stop_words]
        result = ' '.join(keywords[:8]) if keywords else scene_description[:60]
        return result


# Singleton
model_manager = ModelManager()

if __name__ == "__main__":
    test_prompt = "Generate a 3-word motivating quote about science."
    try:
        print(f"Testing LLM:\n{model_manager.generate_content(test_prompt)}")
    except Exception as e:
        print(f"Test failed: {e}")
