"""
Pixabay Video Provider: High-quality stock footage search.

Uses Pixabay's video API with smart keyword matching.
Prioritizes film-quality footage over animation/CG content.

API: https://pixabay.com/api/docs/#videos
Free: 5,000 requests/hour, no credit card needed.
"""
from __future__ import annotations

import logging
import os
import random
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"

# Minimum file size for quality footage (500KB minimum)
MIN_FILE_SIZE = 500_000


class PixabayProvider:
    """Searches Pixabay for high-quality stock video footage."""
    name = "Pixabay Stock"

    def __init__(self):
        self.api_key = PIXABAY_API_KEY

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, scene_description: str, duration: float):
        """Search Pixabay for the best matching stock footage."""
        from visual_engine import VisualResult
        from config import TEMP_DIR

        keywords = self._extract_keywords(scene_description)

        # Try film-type first (real footage, high quality)
        logger.info(f"🔍 [PIXABAY] Searching: '{keywords}'")
        video_path = self._search_pixabay(keywords, TEMP_DIR, video_type="film")
        if video_path:
            return VisualResult(path=video_path, is_image=False, source="pixabay")

        # Try all types
        video_path = self._search_pixabay(keywords, TEMP_DIR, video_type="all")
        if video_path:
            return VisualResult(path=video_path, is_image=False, source="pixabay")

        # Broaden search with fewer keywords
        broad = " ".join(keywords.split()[:2])
        if broad != keywords:
            logger.info(f"🔍 [PIXABAY] Broadening search: '{broad}'")
            video_path = self._search_pixabay(broad, TEMP_DIR, video_type="all")
            if video_path:
                return VisualResult(path=video_path, is_image=False, source="pixabay")

        return None

    def _extract_keywords(self, description: str) -> str:
        """Generate practical stock-footage-friendly search terms."""
        try:
            from model_manager import model_manager
            prompt = (
                f"You are a stock footage search expert. Given this scene, "
                f"generate the BEST 2-3 word search query for Pixabay.\n\n"
                f"RULES:\n"
                f"- Use common, concrete nouns that real cameramen film\n"
                f"- Think of REAL footage: people, nature, cities, technology\n"
                f"- BAD: 'brain neurons glowing' → abstract, won't find real footage\n"
                f"- GOOD: 'woman sleeping peacefully' → real, filmable\n"
                f"- BAD: 'thought bubble dreaming' → cartoon concept\n"
                f"- GOOD: 'person sleeping bed' → real footage exists\n\n"
                f"Scene: '{description}'\n\n"
                f"Reply with ONLY 2-3 search words, nothing else."
            )
            keywords = model_manager.generate_content(prompt, task="keyword_extraction")
            result = keywords.split('\n')[0].replace('"', '').replace("'", "").strip()
            return result if result else description.split('.')[0][:30]
        except Exception:
            return description.split('.')[0][:30]

    def _search_pixabay(self, query: str, temp_dir: Path, video_type: str = "film") -> Path | None:
        """Search Pixabay Videos API for high-quality footage."""
        if not self.api_key:
            return None

        try:
            params = {
                "key": self.api_key,
                "q": query,
                "video_type": video_type,
                "per_page": 10,
                "safesearch": "true",
                "min_width": 1080,
            }
            response = requests.get(PIXABAY_VIDEO_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            hits = data.get("hits", [])
            if not hits:
                return None

            # Sort by quality - prefer larger files (better quality)
            # Pick from top 5 results randomly for variety
            pool = hits[:5] if len(hits) >= 5 else hits
            video = random.choice(pool)
            videos = video.get("videos", {})

            # Prefer large quality for better visuals
            video_data = videos.get("large", videos.get("medium", videos.get("small", {})))
            url = video_data.get("url")

            if url:
                return self._download(url, temp_dir)
            return None

        except Exception as e:
            logger.error(f"❌ [PIXABAY] Search failed: {e}")
            return None

    def _download(self, url: str, temp_dir: Path) -> Path | None:
        """Download video from Pixabay."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            filename = f"pixabay_{random.randint(10000, 99999)}.mp4"
            path = temp_dir / filename

            with open(path, 'wb') as f:
                f.write(response.content)

            size = path.stat().st_size
            if size < MIN_FILE_SIZE:
                path.unlink()
                logger.warning(f"⚠️ [PIXABAY] File too small ({size/1024:.0f}KB), skipping")
                return None

            logger.info(f"✅ [PIXABAY] Downloaded: {path.name} ({size / 1024:.0f}KB)")
            return path
        except Exception as e:
            logger.error(f"❌ [PIXABAY] Download failed: {e}")
            return None
