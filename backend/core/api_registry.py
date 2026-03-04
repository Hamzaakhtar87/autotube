import random
import requests
import logging

logger = logging.getLogger(__name__)

class PublicAPIAdapter:
    """Base class for pluggable public visual APIs"""
    def __init__(self, name: str, niche: str):
        self.name = name
        self.niche = niche

    def fetch_visuals(self, optimized_queries: list[str]) -> list[str]:
        """Returns a list of image/video URLs. To be implemented by subclasses."""
        raise NotImplementedError

class CataasAPI(PublicAPIAdapter):
    def __init__(self):
        super().__init__("Cataas", "animals")
    
    def fetch_visuals(self, optimized_queries: list[str]) -> list[str]:
        return ["https://cataas.com/cat"]

class DogAPI(PublicAPIAdapter):
    def __init__(self):
        super().__init__("Dog.ceo", "animals")
    
    def fetch_visuals(self, optimized_queries: list[str]) -> list[str]:
        try:
            res = requests.get("https://dog.ceo/api/breeds/image/random", timeout=5)
            if res.status_code == 200:
                return [res.json().get("message")]
        except Exception as e:
            logger.error(f"DogAPI error: {e}")
        return []

class FoodishAPI(PublicAPIAdapter):
    def __init__(self):
        super().__init__("Foodish", "food_drink")
    
    def fetch_visuals(self, optimized_queries: list[str]) -> list[str]:
        try:
            res = requests.get("https://foodish-api.com/api/", timeout=5)
            if res.status_code == 200:
                return [res.json().get("image")]
        except Exception as e:
            logger.error(f"FoodishAPI error: {e}")
        return []

class NASAAPI(PublicAPIAdapter):
    def __init__(self):
        super().__init__("NASA", "science_math")
    
    def fetch_visuals(self, optimized_queries: list[str]) -> list[str]:
        try:
            # Using demo key
            res = requests.get("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY", timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get("media_type") == "image":
                    return [data.get("url")]
        except Exception as e:
            logger.error(f"NASA API error: {e}")
        return []

class PicsumAPI(PublicAPIAdapter):
    def __init__(self, niche="general"):
        super().__init__("Picsum", niche)
    
    def fetch_visuals(self, optimized_queries: list[str]) -> list[str]:
        return [f"https://picsum.photos/seed/{random.randint(1,1000)}/1080/1920"]

# --- Pluggable API Registry ---
API_REGISTRY: dict[str, list[PublicAPIAdapter]] = {
    "animals": [CataasAPI(), DogAPI()],
    "food_drink": [FoodishAPI()],
    "science_math": [NASAAPI()],
    "space": [NASAAPI()],
    "tech": [PicsumAPI("tech")],
    "finance": [PicsumAPI("finance")],
}

def get_apis_for_niche(niche: str) -> list[PublicAPIAdapter]:
    """Returns list of registered API adapters for a niche"""
    return API_REGISTRY.get(niche.lower(), [PicsumAPI(niche)])

# Niche Detection Logic
NICHE_MAPPING = {
    "crypto": ["bitcoin", "ethereum", "crypto", "blockchain"],
    "finance": ["money", "stock", "trading", "invest", "wealth"],
    "space": ["nasa", "space", "galaxy", "star", "planet", "moon"],
    "animals": ["cat", "dog", "pet", "lion", "animal", "wildlife"],
    "food_drink": ["food", "cooking", "chef", "eat", "drink", "coffee"],
    "tech": ["computer", "ai", "coding", "software", "robot"]
}

def detect_niche(keywords: list[str]) -> str:
    """Detect niche from a list of keywords"""
    for kw in keywords:
        kw_l = kw.lower()
        for niche, symbols in NICHE_MAPPING.items():
            if any(s in kw_l for s in symbols):
                return niche
    return "general"
