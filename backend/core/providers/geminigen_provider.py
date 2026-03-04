"""
GeminiGen AI Provider: AI video generation via Veo 3 / Veo 2.
Webhook-based async pattern — submit request, wait for webhook callback.

API Endpoint: POST https://api.geminigen.ai/uapi/v1/video-gen/veo
Auth: x-api-key header
Pattern: POST → get UUID → wait for webhook callback → download MP4
Webhook event: VIDEO_GENERATION_COMPLETED (status: 2 = done)

Docs: https://ainnate-geminigen.github.io/GEMINIGEN.AI-API-DEMO/demo.html
"""
from __future__ import annotations

import logging
import os
import time
import random
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

GEMINIGEN_API_KEY = os.getenv("GEMINIGEN_API_KEY", "")
GEMINIGEN_ENDPOINT = "https://api.geminigen.ai/uapi/v1/video-gen/veo"
DEFAULT_MODEL = "veo-3"  # Options: veo-3, veo-2
WEBHOOK_POLL_INTERVAL = 10  # seconds
WEBHOOK_MAX_WAIT = 420  # 7 minutes max wait for webhook result


class GeminiGenProvider:
    """Generates AI video clips via GeminiGen AI aggregator API."""
    name = "GeminiGen AI"

    def __init__(self):
        self.api_key = GEMINIGEN_API_KEY
        self.headers = {
            "x-api-key": self.api_key,
        }

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, scene_description: str, duration: float):
        """Generate an AI video clip for the given scene."""
        from visual_engine import VisualResult
        from config import TEMP_DIR

        logger.info(f"🎬 [GEMINIGEN] Requesting AI video: '{prompt[:80]}...'")

        # Step 1: Submit generation request
        uuid = self._submit_request(prompt)
        if not uuid:
            return None

        # Step 2: Wait for webhook result (stored by our webhook endpoint)
        media_url = self._wait_for_webhook_result(uuid)
        if not media_url:
            return None

        # Step 3: Download the generated video
        video_path = self._download_video(media_url, TEMP_DIR)
        if not video_path:
            return None

        return VisualResult(path=video_path, is_image=False, source="geminigen_ai")

    def _submit_request(self, prompt: str) -> str | None:
        """
        Submit video generation request via form data.
        POST https://api.geminigen.ai/uapi/v1/video-gen/veo
        Body (form-encoded): prompt=...&model=veo-3&aspect_ratio=9:16
        Returns UUID on success.
        """
        form_data = {
            "prompt": prompt,
            "model": DEFAULT_MODEL,
            "aspect_ratio": "9:16",
        }

        try:
            response = requests.post(
                GEMINIGEN_ENDPOINT,
                headers=self.headers,
                data=form_data,
                timeout=30
            )

            # Handle specific GeminiGen error codes before raise_for_status
            if response.status_code in (400, 402, 403):
                try:
                    error_data = response.json().get("detail", {})
                    error_code = error_data.get("error_code", "")
                    error_msg = error_data.get("error_message", str(error_data))

                    if error_code == "PREMIUM_PLAN_REQUIRED":
                        logger.error(f"❌ [GEMINIGEN] Premium API plan required for video generation.")
                        logger.error(f"   Your GeminiGen account needs an API subscription ($10/3 days).")
                        logger.error(f"   Purchase at: https://geminigen.ai/pricing")
                    elif error_code == "INSUFFICIENT_CREDIT":
                        logger.error(f"❌ [GEMINIGEN] Insufficient credits. Top up at: https://geminigen.ai/pricing")
                    else:
                        logger.error(f"❌ [GEMINIGEN] API error [{error_code}]: {error_msg}")
                except Exception:
                    logger.error(f"❌ [GEMINIGEN] HTTP {response.status_code}: {response.text[:200]}")
                return None

            response.raise_for_status()
            data = response.json()

            uuid = data.get("uuid")
            if uuid:
                logger.info(f"✅ [GEMINIGEN] Request submitted. UUID: {uuid}")
                logger.info(f"   Model: {data.get('model_name', DEFAULT_MODEL)}")
                logger.info(f"   Estimated credits: {data.get('estimated_credit', '?')}")
                return uuid

            logger.error(f"❌ [GEMINIGEN] No UUID in response: {data}")
            return None

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ [GEMINIGEN] HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"❌ [GEMINIGEN] Submit failed: {e}")
            return None

    def _wait_for_webhook_result(self, uuid: str) -> str | None:
        """
        Wait for the webhook endpoint to receive the VIDEO_GENERATION_COMPLETED event.
        The webhook stores results in memory keyed by UUID.
        We poll our own webhook store until the result appears or timeout.
        """
        logger.info(f"⏳ [GEMINIGEN] Waiting for webhook result (UUID: {uuid})...")
        logger.info(f"   Max wait: {WEBHOOK_MAX_WAIT}s | Poll interval: {WEBHOOK_POLL_INTERVAL}s")

        elapsed = 0
        while elapsed < WEBHOOK_MAX_WAIT:
            try:
                from app.api.webhooks import get_webhook_result
                result = get_webhook_result(uuid)
                if result:
                    media_url = result.get("media_url")
                    status = result.get("status")
                    error = result.get("error_message", "")

                    if status == 2 and media_url:
                        logger.info(f"✅ [GEMINIGEN] Webhook received! Video ready.")
                        return media_url
                    elif error:
                        logger.error(f"❌ [GEMINIGEN] Generation failed: {error}")
                        return None
            except ImportError:
                # Webhook module not available (running outside FastAPI context)
                # Fall through to timeout
                pass
            except Exception as e:
                logger.warning(f"⚠️ [GEMINIGEN] Webhook poll error: {e}")

            time.sleep(WEBHOOK_POLL_INTERVAL)
            elapsed += WEBHOOK_POLL_INTERVAL

            if elapsed % 60 == 0:
                logger.info(f"⏳ [GEMINIGEN] Still waiting... ({elapsed}s elapsed)")

        logger.error(f"❌ [GEMINIGEN] Timed out after {WEBHOOK_MAX_WAIT}s waiting for webhook")
        return None

    def _download_video(self, url: str, temp_dir: Path) -> Path | None:
        """Download generated video from Cloudflare R2 signed URL."""
        try:
            response = requests.get(url, timeout=120, stream=True)
            response.raise_for_status()

            filename = f"geminigen_{random.randint(10000, 99999)}.mp4"
            path = temp_dir / filename

            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = path.stat().st_size
            if file_size < 10000:  # Less than 10KB = probably error page
                path.unlink()
                logger.error("❌ [GEMINIGEN] Downloaded file too small, likely invalid")
                return None

            logger.info(f"✅ [GEMINIGEN] Downloaded: {path} ({file_size / 1024:.0f}KB)")
            return path

        except Exception as e:
            logger.error(f"❌ [GEMINIGEN] Download failed: {e}")
            return None
