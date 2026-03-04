"""
Coverr Video Provider: Free stock video with AI-generated content.

Coverr has both human-shot and AI-generated footage.
We use the AI filter hack — appending AI modifiers to queries.

API: https://coverr.co/api (OpenAPI docs)
  - Search: GET https://api.coverr.co/videos?query={term}
  - Download: GET https://api.coverr.co/storage/videos/{base_filename}
  - Vertical filter: GET https://api.coverr.co/videos/filters/is_vertical/true

Free for commercial use with attribution.
1,000 calls/month (unverified key), 500/min (production key).
"""
from __future__ import annotations

import logging
import os
import random
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

COVERR_API_KEY = os.getenv("COVERR_API_KEY", "")
COVERR_API_BASE = "https://api.coverr.co"

AI_MODIFIERS = ["ai", "abstract", "futuristic", "cinematic", "animation"]


class CoverrAIProvider:
    """Searches Coverr for AI-style stock footage using AI filter hack."""
    name = "Coverr AI Stock"

    def __init__(self):
        self.api_key = COVERR_API_KEY
        self.headers = {}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def is_available(self) -> bool:
        # Coverr API works without key too (limited), so always available
        return True

    def generate(self, prompt: str, scene_description: str, duration: float):
        """Search Coverr for AI-style footage."""
        from visual_engine import VisualResult
        from config import TEMP_DIR

        keywords = self._extract_ai_keywords(scene_description)
        logger.info(f"🔍 [COVERR-AI] Searching: '{keywords}'")

        video_path = self._search_and_download(keywords, TEMP_DIR)
        if video_path:
            return VisualResult(path=video_path, is_image=False, source="coverr_ai")

        # Try without AI modifier
        base_kw = keywords.rsplit(' ', 1)[0] if ' ' in keywords else keywords
        video_path = self._search_and_download(base_kw, TEMP_DIR)
        if video_path:
            return VisualResult(path=video_path, is_image=False, source="coverr_ai")

        return None

    def _extract_ai_keywords(self, description: str) -> str:
        """Extract keywords and append AI modifier."""
        try:
            from model_manager import model_manager
            prompt = (
                f"Extract 2-3 specific visual keywords from: '{description}'. "
                f"Reply with ONLY keywords, nothing else."
            )
            keywords = model_manager.generate_content(prompt, task="keyword_extraction")
            base = keywords.split('\n')[0].replace('Keywords:', '').strip()
            if not base:
                base = description.split('.')[0][:40]
        except Exception:
            base = description.split('.')[0][:40]

        modifier = random.choice(AI_MODIFIERS)
        return f"{base} {modifier}"

    def _search_and_download(self, query: str, temp_dir: Path) -> Path | None:
        """Search Coverr and download best match."""
        try:
            url = f"{COVERR_API_BASE}/videos"
            params = {"query": query}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)

            if response.status_code != 200:
                logger.warning(f"⚠️ [COVERR-AI] Search returned {response.status_code}")
                return None

            videos = response.json()
            if not isinstance(videos, list) or not videos:
                return None

            # Filter for vertical videos if possible, otherwise take any
            vertical = [v for v in videos if v.get("is_vertical", False)]
            pool = vertical if vertical else videos

            video = random.choice(pool[:5])
            base_filename = video.get("base_filename")
            if not base_filename:
                return None

            # Get download URL
            download_url = f"{COVERR_API_BASE}/storage/videos/{base_filename}"
            dl_response = requests.get(download_url, headers=self.headers, timeout=10)

            if dl_response.status_code != 200:
                logger.warning(f"⚠️ [COVERR-AI] Download URL request failed")
                return None

            # Response is a signed URL string or JSON with URL
            media_url = dl_response.text.strip().strip('"')
            if not media_url.startswith("http"):
                try:
                    media_url = dl_response.json()
                    if isinstance(media_url, dict):
                        media_url = media_url.get("url", "")
                except Exception:
                    return None

            if not media_url:
                return None

            return self._download(media_url, temp_dir)

        except Exception as e:
            logger.error(f"❌ [COVERR-AI] Error: {e}")
            return None

    def _download(self, url: str, temp_dir: Path) -> Path | None:
        """Download video from signed URL."""
        try:
            response = requests.get(url, timeout=60, stream=True)
            response.raise_for_status()

            filename = f"coverr_{random.randint(10000, 99999)}.mp4"
            path = temp_dir / filename

            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            size = path.stat().st_size
            if size < 5000:
                path.unlink()
                return None

            logger.info(f"✅ [COVERR-AI] Downloaded: {path} ({size / 1024:.0f}KB)")
            return path

        except Exception as e:
            logger.error(f"❌ [COVERR-AI] Download failed: {e}")
            return None
