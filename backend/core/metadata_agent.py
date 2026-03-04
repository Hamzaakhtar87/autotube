"""
Metadata Agent: Generates optimized titles, descriptions, and tags
"""

import logging
from model_manager import model_manager
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetadataAgent:
    def __init__(self):
        pass
    
    def generate_metadata(self, topic: str, script: str) -> Dict[str, str]:
        """
        Generate YouTube metadata (title, description, tags)
        Returns dict with 'title', 'description', 'tags'
        """
        logger.info(f"📋 Generating metadata for topic: {topic}")
        
        prompt = f"""You are a YouTube Shorts optimization expert.

Generate metadata for a Short about: {topic}

Script excerpt: {script[:200]}...

Generate:

TITLE (max 8 words, curiosity-driven, no clickbait):
[your title here]

DESCRIPTION (2-3 sentences, natural, includes topic):
[your description here]

TAGS (5-8 relevant tags, comma-separated):
[your tags here]

REQUIREMENTS:
- Title must be ≤8 words
- Title should trigger curiosity without being misleading
- Description should be conversational and natural
- Tags should be specific and relevant
- No ALL CAPS, no excessive punctuation

Output in this exact format:
TITLE: [title]
DESCRIPTION: [description]
TAGS: [tags]"""

        try:
            response_text = model_manager.generate_content(prompt, task="metadata")
            
            # Parse response
            metadata = self._parse_metadata(response_text)
            
            logger.info(f"✅ [QUALITY_MODE: FULL] Metadata generated via LLM:")
            logger.info(f"   Title: {metadata['title']}")
            logger.info(f"   Description: {metadata['description'][:50]}...")
            logger.info(f"   Tags: {metadata['tags']}")
            
            return metadata
            
        except Exception as e:
            if "SURVIVAL_MODE_TRIGGER" in str(e):
                logger.warning("🏁 GPT4All unreachable. Using Fallback templates (Survival Mode)...")
            else:
                logger.error(f"Error generating metadata: {e}")
            # Fallback metadata
            return self._generate_fallback_metadata(topic)
    
    def _parse_metadata(self, response: str) -> Dict[str, str]:
        """Parse Claude's response into structured metadata"""
        lines = response.split('\n')
        metadata = {
            'title': '',
            'description': '',
            'tags': ''
        }
        
        current_key = None
        current_value = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('TITLE:'):
                if current_key and current_value:
                    metadata[current_key] = ' '.join(current_value).strip()
                current_key = 'title'
                current_value = [line.replace('TITLE:', '').strip()]
            elif line.startswith('DESCRIPTION:'):
                if current_key and current_value:
                    metadata[current_key] = ' '.join(current_value).strip()
                current_key = 'description'
                current_value = [line.replace('DESCRIPTION:', '').strip()]
            elif line.startswith('TAGS:'):
                if current_key and current_value:
                    metadata[current_key] = ' '.join(current_value).strip()
                current_key = 'tags'
                current_value = [line.replace('TAGS:', '').strip()]
            elif line and current_key:
                current_value.append(line)
        
        # Add last item
        if current_key and current_value:
            metadata[current_key] = ' '.join(current_value).strip()
        
        # Validate and clean
        metadata['title'] = self._clean_title(metadata['title'])
        metadata['description'] = metadata['description'][:500].strip()
        
        return metadata

    def _clean_title(self, raw_title: str) -> str:
        """Surgical Title Guard: 60 chars, Title Case, Semantic Cut"""
        # 1. Basic cleaning
        title = raw_title.strip().strip('"').strip("'")
        
        # 2. Enforce Title Case
        title = title.title()
        
        # 3. 60 Character Cap with Semantic Boundary Cutting
        if len(title) > 60:
            # Find the last space within the 60 char limit
            cut_index = title.rfind(' ', 0, 60)
            if cut_index == -1: cut_index = 57 # Hard cut if no space
            title = title[:cut_index].strip()
            # Remove trailing incomplete markers like '...' or 'The'
            for filler in ["...", "The", "And", "Of", "With"]:
                if title.endswith(filler):
                    title = title[:-len(filler)].strip()
        
        return title
    
    def _generate_fallback_metadata(self, topic: str) -> Dict[str, str]:
        """Generate simple fallback metadata if AI fails"""
        words = topic.split()[:6]
        title = ' '.join(words).title()
        
        return {
            'title': title,
            'description': f"Discover the truth about {topic.lower()}. Follow for more insights. #shorts",
            'tags': 'psychology, facts, shorts, viral, truth'
        }


if __name__ == "__main__":
    # Test
    agent = MetadataAgent()
    topic = "Why silence is more powerful than words"
    script = "Silence makes people uncomfortable. When you stay quiet, others feel pressured to fill the void. This reveals their true thoughts."
    metadata = agent.generate_metadata(topic, script)
    
    print(f"\n{'='*60}")
    print(f"TITLE: {metadata['title']}")
    print(f"DESCRIPTION: {metadata['description']}")
    print(f"TAGS: {metadata['tags']}")
    print(f"{'='*60}")