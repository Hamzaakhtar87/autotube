import os
import logging
import random
import requests
from pathlib import Path
from api_registry import get_apis_for_niche, detect_niche
from visual_agent import VisualAgent

logger = logging.getLogger(__name__)

class VisualAgentAPI:
    def __init__(self, visual_agent: VisualAgent):
        from config import USE_API_VISUALS
        self.visual_agent = visual_agent
        self.use_api_visuals = USE_API_VISUALS

    def fetch_visual(self, visual_keywords: str, duration: float):
        """
        Extends VisualAgent logic. 
        1. Checks feature flag.
        2. Detects niche.
        3. Attempts to fetch from public APIs.
        4. Falls back to original Pexels logic.
        """
        if self.use_api_visuals:
            # We break keywords by spaces/commas for detection
            keywords_list = visual_keywords.replace(',', ' ').split()
            niche = detect_niche(keywords_list)
            
            if niche != "general":
                logger.info(f"🔎 Detected niche: {niche} for keywords '{visual_keywords}'")
                apis = get_apis_for_niche(niche)
                for api in apis:
                    try:
                        urls = api.fetch_visuals(keywords_list)
                        if urls:
                            url = urls[0]
                            logger.info(f"✨ Found API visual from {api.name}: {url}")
                            
                            # We treat most public API returns as images for safe Ken Burns
                            # unless we know it's a video. For simplicity, most are images.
                            # NASA APOD and Picsum are images.
                            
                            filename = f"api_visual_{api.niche}_{random.randint(1000,9999)}.jpg"
                            # VisualAgent doesn't have download_image, but we can reuse pexels logic 
                            # or simple downloader.
                            temp_path = self._download_resource(url, filename)
                            if temp_path:
                                return temp_path, True # Treat as image
                    except Exception as e:
                        logger.warning(f"❌ API {api.name} failed: {e}. Falling back...")
        
        # Fallback to original Pexels/Stock logic
        return self.visual_agent.fetch_visual(visual_keywords, duration)

    def _download_resource(self, url: str, filename: str) -> Path:
        from config import TEMP_DIR
        output_path = TEMP_DIR / filename
        try:
            res = requests.get(url, timeout=30)
            res.raise_for_status()
            with open(output_path, 'wb') as f:
                f.write(res.content)
            return output_path
        except:
            return None

    # Proxy other methods to original agent
    def __getattr__(self, name):
        return getattr(self.visual_agent, name)
