"""
Visual Engine v3.2: Multi-provider stock footage with quality priority.

CASCADE ORDER:
1. Pexels Stock  (free, great curation, high quality)
2. Pixabay Stock (free, huge library, 5K req/hour)
3. Veo Direct    (Google AI Pro, Pro/Enterprise only)
4. Fallback      (static frame, last resort)

Pexels goes first because it has the best curated, cinematic footage.
Pixabay provides variety when Pexels doesn't have a match.
Veo is a bonus for paid tiers when we have AI Pro credits.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class UserTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class VisualResult:
    """Result from a visual provider."""
    def __init__(self, path: Path, is_image: bool = False, source: str = "unknown"):
        self.path = path
        self.is_image = is_image
        self.source = source


class VisualProvider(ABC):
    """Base class for all visual providers."""
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, scene_description: str, duration: float):
        """Generate or fetch a visual for the given scene. Returns None on failure."""
        ...


class VisualEngine:
    """
    Orchestrates visual generation with quality-first cascading.
    Pexels (best quality) → Pixabay (variety) → Veo (AI) → Fallback.
    """

    def __init__(self, user_tier: str = UserTier.FREE):
        self.user_tier = user_tier
        self.free_providers: list[VisualProvider] = []
        self.paid_providers: list[VisualProvider] = []
        self._initialize_providers()

    def _initialize_providers(self):
        """Load all providers based on available API keys."""
        from providers.fallback_provider import FallbackProvider

        # === 1. PEXELS (Free, all tiers, best curated quality) ===
        try:
            from providers.stock_search_provider import StockSearchProvider
            pexels = StockSearchProvider()
            if pexels.is_available():
                self.free_providers.append(pexels)
                self.paid_providers.append(pexels)
                logger.info("✅ [VISUAL] Pexels Stock loaded (primary)")
        except ImportError:
            logger.warning("⚠️ [VISUAL] Pexels provider not available")

        # === 2. PIXABAY (Free, all tiers, huge library for variety) ===
        try:
            from providers.pixabay_provider import PixabayProvider
            pixabay = PixabayProvider()
            if pixabay.is_available():
                self.free_providers.append(pixabay)
                self.paid_providers.append(pixabay)
                logger.info("✅ [VISUAL] Pixabay Stock loaded")
        except ImportError:
            logger.warning("⚠️ [VISUAL] Pixabay provider not available")

        # === 3. VEO DIRECT (Pro/Enterprise only, AI Pro credits) ===
        try:
            from providers.veo_direct_provider import VeoDirectProvider
            veo = VeoDirectProvider()
            if veo.is_available():
                self.paid_providers.append(veo)
                logger.info("✅ [VISUAL] Google Veo Direct loaded (Pro/Enterprise)")
        except ImportError:
            pass

        # === 4. FALLBACK (always) ===
        fallback = FallbackProvider()
        self.free_providers.append(fallback)
        self.paid_providers.append(fallback)
        logger.info("✅ [VISUAL] Fallback provider loaded")

    def get_visual(self, scene_description: str, duration: float = 5.0) -> VisualResult:
        """
        Get visual for a scene using quality-first cascade.
        """
        optimized_prompt = self._optimize_prompt(scene_description)
        logger.info(f"🎬 [VISUAL] Scene: '{scene_description[:60]}...' → Prompt: '{optimized_prompt[:60]}...'")

        providers = self._select_providers()

        for provider in providers:
            try:
                logger.info(f"🔄 [VISUAL] Trying provider: {provider.name}")
                result = provider.generate(optimized_prompt, scene_description, duration)
                if result and result.path and result.path.exists():
                    logger.info(f"✅ [VISUAL] Success via {provider.name}: {result.path}")
                    return result
                logger.warning(f"⚠️ [VISUAL] {provider.name} returned no result, cascading...")
            except Exception as e:
                logger.error(f"❌ [VISUAL] {provider.name} failed: {e}, cascading...")

        logger.error("🚨 [VISUAL] All providers failed! Using emergency fallback")
        from providers.fallback_provider import FallbackProvider
        return FallbackProvider().generate(optimized_prompt, scene_description, duration)

    def _select_providers(self) -> list[VisualProvider]:
        """Select provider list based on user tier."""
        if self.user_tier in (UserTier.PRO, UserTier.ENTERPRISE):
            return self.paid_providers
        return self.free_providers

    def _optimize_prompt(self, scene_description: str) -> str:
        """Use LLM to create an optimized visual search/generation prompt."""
        try:
            from model_manager import model_manager
            return model_manager.optimize_image_prompt(scene_description)
        except Exception:
            return scene_description
