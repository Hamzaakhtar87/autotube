"""
Fallback Provider: Always succeeds — generates gradient background via PIL.
This is the last resort in the cascade. It can never fail.
"""

import logging
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

GRADIENT_PALETTES = [
    ("#0f0c29", "#302b63", "#24243e"),  # Deep space
    ("#1a1a2e", "#16213e", "#0f3460"),  # Midnight blue
    ("#0d1117", "#161b22", "#21262d"),  # GitHub dark
    ("#141e30", "#243b55", "#2c5364"),  # Ocean blue
    ("#1f1c2c", "#928dab", "#1f1c2c"),  # Purple night
    ("#232526", "#414345", "#232526"),  # Metal grey
    ("#000428", "#004e92", "#000428"),  # Electric blue
    ("#1c1c1c", "#333333", "#1c1c1c"),  # Carbon
]


class FallbackProvider:
    """Generates a solid gradient background image. Always succeeds."""
    name = "Gradient Fallback"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, scene_description: str, duration: float):
        """Generate a gradient background image."""
        from visual_engine import VisualResult
        from config import TEMP_DIR, VIDEO_WIDTH, VIDEO_HEIGHT

        palette = random.choice(GRADIENT_PALETTES)
        img = self._create_gradient(VIDEO_WIDTH, VIDEO_HEIGHT, palette)

        filename = f"fallback_{random.randint(10000, 99999)}.jpg"
        path = TEMP_DIR / filename
        img.save(path, quality=90)

        logger.info(f"🎨 [FALLBACK] Generated gradient: {path}")
        return VisualResult(path=path, is_image=True, source="fallback_gradient")

    def _create_gradient(self, width: int, height: int, palette: tuple) -> Image.Image:
        """Create a vertical gradient from top to bottom."""
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)

        top_color = self._hex_to_rgb(palette[0])
        mid_color = self._hex_to_rgb(palette[1])
        bottom_color = self._hex_to_rgb(palette[2])

        half = height // 2
        for y in range(half):
            ratio = y / half
            r = int(top_color[0] + (mid_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (mid_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (mid_color[2] - top_color[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        for y in range(half, height):
            ratio = (y - half) / half
            r = int(mid_color[0] + (bottom_color[0] - mid_color[0]) * ratio)
            g = int(mid_color[1] + (bottom_color[1] - mid_color[1]) * ratio)
            b = int(mid_color[2] + (bottom_color[2] - mid_color[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        return img

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
