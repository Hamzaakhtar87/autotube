"""
Visual Agent: Fetches high-quality stock visuals for scenes.
QUALITY-FIRST HIERARCHY:
1. PRIMARY: Pexels Stock (Video then Image)
2. SECONDARY: Public APIs (Cataas, DogAPI, NASA, etc.)
3. FALLBACK: AI-assisted synthetic visual (Solid color with optimized prompt)
"""

import logging
import requests
import random
from pathlib import Path
from config import PEXELS_API_KEY, PEXELS_VIDEO_URL, PEXELS_IMAGE_URL, TEMP_DIR, VIDEO_WIDTH, VIDEO_HEIGHT, VISUAL_PRIORITY
from model_manager import model_manager
from api_registry import detect_niche, get_apis_for_niche

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VisualAgent:
    def __init__(self):
        self.pexels_key = PEXELS_API_KEY
        self.headers = {"Authorization": self.pexels_key} if self.pexels_key else {}

    def fetch_visual(self, scene_description: str, duration: float) -> tuple[Path, bool]:
        """
        Fetch visual following strict hierarchy.
        Phi-2 is used to optimize the search query.
        """
        # Step 1: Optimize Search Query using Phi-2
        optimized_query = self._optimize_query(scene_description)
        logger.info(f"🔍 [VISUAL_PLAN] Optimized Query: '{optimized_query}' (Source: '{scene_description}')")
        
        # Step 2: Traverse Hierarchy
        for source in VISUAL_PRIORITY:
            if source == "pexels":
                path, is_img = self._try_pexels(optimized_query)
                if path: return path, is_img
                
            elif source == "public_api":
                path = self._try_public_apis(optimized_query)
                if path: return path, True
                
            elif source == "ai_fallback":
                logger.warning(f"⚠️ [QUALITY_MODE: FALLBACK] No stock found. Generating synthetic visual.")
                return self._get_ai_fallback(optimized_query), True

        # Ultimate safety fallback
        return self._get_ai_fallback("Default fallback"), True

    def _optimize_query(self, description: str) -> str:
        """Use Phi-2 to extract best 2-3 visual keywords for stock search"""
        prompt = (
            f"Given this scene description: '{description}', "
            "provide strictly 2-3 specific visual keywords for a stock video search. "
            "Example: 'busy city street rain'. Do not include quotes."
        )
        try:
            keywords = model_manager.generate_content(prompt, task="visual_query_optimization")
            # Clean up potential LLM verbosity
            sanitized = keywords.split('\n')[0].replace('Keywords:', '').strip()
            return sanitized if sanitized else description
        except:
            return description

    def _try_pexels(self, query: str) -> tuple[Path, bool]:
        """Try Pexels Video then Image"""
        if not self.pexels_key: return None, False
        
        # 1. Try Video
        video_path = self._fetch_pexels_video(query)
        if video_path:
            logger.info("✨ [VISUAL_SOURCE: PEXELS_VIDEO]")
            return video_path, False
            
        # 2. Try Image
        image_path = self._fetch_pexels_image(query)
        if image_path:
            logger.info("✨ [VISUAL_SOURCE: PEXELS_IMAGE]")
            return image_path, True
            
        return None, False

    def _try_public_apis(self, query: str) -> Path:
        """Try niche-specific public APIs"""
        niche = detect_niche([query])
        apis = get_apis_for_niche(niche)
        for api in apis:
            try:
                urls = api.fetch_visuals([query])
                if urls:
                    path = self._download_file(urls[0], f"public_{api.name}")
                    if path:
                        logger.info(f"✨ [VISUAL_SOURCE: PUBLIC_{api.name.upper()}]")
                        return path
            except:
                continue
        return None

    def _download_file(self, url: str, prefix: str) -> Path:
        """Helper to download file with timeout and validation"""
        try:
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            
            # Detect extension
            content_type = res.headers.get("Content-Type", "")
            ext = ".mp4" if "video" in content_type else ".jpg"
            
            filename = f"{prefix}_{random.randint(1000, 9999)}{ext}"
            path = TEMP_DIR / filename
            
            with open(path, 'wb') as f:
                f.write(res.content)
            return path
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def _get_ai_fallback(self, query: str) -> Path:
        """Deterministic fallback visual (Solid color + branding)"""
        from PIL import Image, ImageDraw
        colors = ["#1a1a1a", "#2c3e50", "#27ae60", "#2980b9", "#8e44ad", "#c0392b"]
        color = random.choice(colors)
        
        img = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), color=color)
        draw = ImageDraw.Draw(img)
        
        # Add minimal branding/info footer
        draw.text((100, 1800), f"AI Fallback: {query[:30]}", fill="rgba(255,255,255,128)")
            
        filename = f"fallback_{random.randint(1000, 9999)}.jpg"
        path = TEMP_DIR / filename
        img.save(path)
        return path

    def _fetch_pexels_video(self, keyword: str) -> Path:
        params = {"query": keyword, "per_page": 5, "orientation": "portrait"}
        try:
            res = requests.get(PEXELS_VIDEO_URL, headers=self.headers, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            if not data.get("videos"): return None
            
            video = random.choice(data["videos"])
            # Get best vertical quality
            files = video.get("video_files", [])
            vertical = [f for f in files if f.get("width", 0) < f.get("height", 0)]
            best_link = max(vertical, key=lambda x: x.get("width", 0)).get("link") if vertical else files[0].get("link")
            
            return self._download_file(best_link, "pexels_vid")
        except: return None

    def _fetch_pexels_image(self, keyword: str) -> Path:
        params = {"query": keyword, "per_page": 5, "orientation": "portrait"}
        try:
            res = requests.get(PEXELS_IMAGE_URL, headers=self.headers, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            if not data.get("photos"): return None
            
            photo = random.choice(data["photos"])
            link = photo.get("src", {}).get("portrait") or photo.get("src", {}).get("large2x")
            
            return self._download_file(link, "pexels_img")
        except: return None

if __name__ == "__main__":
    agent = VisualAgent()
    print("🧪 Test: Optimized fallback for 'cyberpunk city background'")
    path, is_img = agent.fetch_visual("cyberpunk city background", 5)
    print(f"Result: {path} (Image: {is_img})")
