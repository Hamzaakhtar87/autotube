"""
Google Veo Direct Provider: Video generation via Google AI Studio API.
Uses the official google-genai SDK with Veo 3.1 model.
Synchronous polling pattern (long-running operation).
"""
from __future__ import annotations

import logging
import os
import time
import random
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
VEO_MODEL = "veo-3.1-generate-preview"
POLL_INTERVAL_SEC = 10
MAX_POLL_ATTEMPTS = 40  # 40 × 10s = ~6.5 min


class VeoDirectProvider:
    """Generates video via Google's Veo model through AI Studio API."""
    name = "Google Veo Direct"

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except ImportError:
                logger.warning("⚠️ google-genai not installed for Veo Direct")
            except Exception as e:
                logger.warning(f"⚠️ Veo Direct init failed: {e}")

    def is_available(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, scene_description: str, duration: float):
        """Generate a video clip using Google Veo."""
        from visual_engine import VisualResult
        from config import TEMP_DIR

        if not self.client:
            return None

        logger.info(f"🎬 [VEO] Generating video: '{prompt[:80]}...'")

        try:
            operation = self.client.models.generate_videos(
                model=VEO_MODEL,
                prompt=prompt,
                config={
                    "aspect_ratio": "9:16",
                    "number_of_videos": 1,
                }
            )

            # Poll for completion
            for attempt in range(MAX_POLL_ATTEMPTS):
                if operation.done:
                    break
                time.sleep(POLL_INTERVAL_SEC)
                try:
                    operation = self.client.operations.get(operation)
                except Exception:
                    pass

            if not operation.done:
                logger.error("❌ [VEO] Timed out waiting for video generation")
                return None

            # Extract video from response
            if hasattr(operation, 'response') and operation.response:
                generated_videos = operation.response.generated_videos
                if generated_videos:
                    video = generated_videos[0]
                    video_data = video.video

                    if hasattr(video_data, 'uri') and video_data.uri:
                        video_path = self._download_video(video_data.uri, TEMP_DIR)
                        if video_path:
                            return VisualResult(path=video_path, is_image=False, source="google_veo")

            logger.warning("⚠️ [VEO] No video in response")
            return None

        except Exception as e:
            logger.error(f"❌ [VEO] Generation failed: {e}")
            return None

    def _download_video(self, url: str, temp_dir: Path) -> Path | None:
        """Download video from Google's signed URL."""
        try:
            response = requests.get(url, timeout=120, stream=True)
            response.raise_for_status()

            filename = f"veo_{random.randint(10000, 99999)}.mp4"
            path = temp_dir / filename

            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"✅ [VEO] Downloaded: {path} ({path.stat().st_size / 1024:.0f}KB)")
            return path

        except Exception as e:
            logger.error(f"❌ [VEO] Download failed: {e}")
            return None
