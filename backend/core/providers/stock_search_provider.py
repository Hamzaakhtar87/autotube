"""
Stock Search Provider: AI-enhanced stock footage search.
Level 3 fallback: Pexels Video + basic keyword matching.

Uses Gemini to optimize narration → cinematic search query,
then searches Pexels Video API for best vertical match.
"""
from __future__ import annotations

import logging
import os
import random
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_IMAGE_URL = "https://api.pexels.com/v1/search"


class StockSearchProvider:
    """Searches Pexels for stock video/image matching the scene narration."""
    name = "Stock Search (Pexels)"

    def __init__(self):
        self.api_key = PEXELS_API_KEY
        self.headers = {"Authorization": self.api_key} if self.api_key else {}

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, scene_description: str, duration: float):
        """Search Pexels for a matching video clip, fall back to image."""
        from visual_engine import VisualResult
        from config import TEMP_DIR

        # Use scene_description for search (more natural keywords)
        search_query = self._extract_keywords(scene_description)
        logger.info(f"🔍 [STOCK] Searching Pexels: '{search_query}'")

        # Try video first
        video_path = self._search_pexels_video(search_query, TEMP_DIR)
        if video_path:
            return VisualResult(path=video_path, is_image=False, source="pexels_video")

        # Fall back to image
        image_path = self._search_pexels_image(search_query, TEMP_DIR)
        if image_path:
            return VisualResult(path=image_path, is_image=True, source="pexels_image")

        # Try broader query (first 2 words)
        broad_query = " ".join(search_query.split()[:2])
        if broad_query != search_query:
            logger.info(f"🔍 [STOCK] Broadening search: '{broad_query}'")
            video_path = self._search_pexels_video(broad_query, TEMP_DIR)
            if video_path:
                return VisualResult(path=video_path, is_image=False, source="pexels_video")

        return None

    def _extract_keywords(self, description: str) -> str:
        """Extract practical stock footage search terms from description."""
        try:
            from model_manager import model_manager
            prompt = (
                f"You are a stock footage search expert. Given this video scene description, "
                f"generate the BEST search query to find matching footage on Pexels/Pixabay.\n\n"
                f"RULES:\n"
                f"- Use 2-4 common, concrete words that stock sites actually have\n"
                f"- Think about what a cameraman would film, not abstract concepts\n"
                f"- Avoid metaphors, abstract ideas, or overly specific scenarios\n"
                f"- Prefer: people, nature, technology, emotions, actions\n"
                f"- BAD: 'brain scan colorful swirls' (too specific, won't exist)\n"
                f"- GOOD: 'neuroscience laboratory research' (real footage exists)\n"
                f"- BAD: 'split-screen comparison charity' (impossible to find)\n"
                f"- GOOD: 'volunteer helping community' (common stock footage)\n\n"
                f"Scene: '{description}'\n\n"
                f"Reply with ONLY the search query, nothing else."
            )
            keywords = model_manager.generate_content(prompt, task="keyword_extraction")
            sanitized = keywords.split('\n')[0].replace('Keywords:', '').replace('"', '').replace("'", "").strip()
            return sanitized if sanitized else description
        except Exception:
            return description

    def _search_pexels_video(self, query: str, temp_dir: Path) -> Path | None:
        """Search Pexels for vertical video matching query."""
        if not self.api_key:
            return None

        try:
            params = {"query": query, "per_page": 5, "orientation": "portrait"}
            response = requests.get(
                PEXELS_VIDEO_URL, headers=self.headers, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            videos = data.get("videos", [])
            if not videos:
                return None

            video = random.choice(videos)
            files = video.get("video_files", [])

            # Prefer vertical (portrait) video files
            vertical = [f for f in files if f.get("width", 0) < f.get("height", 0)]
            if vertical:
                best = max(vertical, key=lambda x: x.get("width", 0))
            else:
                best = files[0] if files else None

            if not best:
                return None

            link = best.get("link")
            return self._download(link, "pexels_vid", temp_dir)

        except Exception as e:
            logger.error(f"❌ [STOCK] Pexels video search failed: {e}")
            return None

    def _search_pexels_image(self, query: str, temp_dir: Path) -> Path | None:
        """Search Pexels for portrait image matching query."""
        if not self.api_key:
            return None

        try:
            params = {"query": query, "per_page": 5, "orientation": "portrait"}
            response = requests.get(
                PEXELS_IMAGE_URL, headers=self.headers, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            photos = data.get("photos", [])
            if not photos:
                return None

            photo = random.choice(photos)
            link = photo.get("src", {}).get("portrait") or photo.get("src", {}).get("large2x")
            return self._download(link, "pexels_img", temp_dir)

        except Exception as e:
            logger.error(f"❌ [STOCK] Pexels image search failed: {e}")
            return None

    def _download(self, url: str, prefix: str, temp_dir: Path) -> Path | None:
        """Download a file from URL to temp dir."""
        if not url:
            return None

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            ext = ".mp4" if "video" in content_type else ".jpg"
            filename = f"{prefix}_{random.randint(10000, 99999)}{ext}"
            path = temp_dir / filename

            with open(path, 'wb') as f:
                f.write(response.content)

            return path

        except Exception as e:
            logger.error(f"❌ [STOCK] Download failed: {e}")
            return None
