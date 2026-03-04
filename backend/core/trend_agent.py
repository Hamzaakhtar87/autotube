"""
Trend Agent: Discovers trending topics from multiple sources
"""

import feedparser
import requests
import random
import logging
from typing import List, Dict
import json
from config import GOOGLE_TRENDS_RSS, REDDIT_SUBREDDITS, TOPIC_CATEGORIES, MEMORY_FILE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrendAgent:
    def __init__(self):
        self.memory = self._load_memory()
    
    def _load_memory(self) -> Dict:
        """Load used topics from memory"""
        try:
            if MEMORY_FILE.exists():
                with open(MEMORY_FILE, 'r') as f:
                    return json.load(f)
            return {"used_topics": [], "last_upload": None}
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            return {"used_topics": [], "last_upload": None}
    
    def _save_memory(self):
        """Save memory to disk"""
        try:
            with open(MEMORY_FILE, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def _is_topic_used(self, topic: str) -> bool:
        """Check if topic was already used"""
        topic_lower = topic.lower().strip()
        return any(topic_lower in used.lower() for used in self.memory.get("used_topics", []))
    
    def _mark_topic_used(self, topic: str):
        """Mark topic as used"""
        if "used_topics" not in self.memory:
            self.memory["used_topics"] = []
        self.memory["used_topics"].append(topic)
        # Keep only last 100 topics
        self.memory["used_topics"] = self.memory["used_topics"][-100:]
        self._save_memory()
    
    def get_google_trends(self) -> List[str]:
        """Fetch trending topics from Google Trends RSS"""
        try:
            feed = feedparser.parse(GOOGLE_TRENDS_RSS)
            trends = []
            for entry in feed.entries[:20]:
                title = entry.get('title', '').strip()
                if title and len(title) > 3:
                    trends.append(title)
            logger.info(f"Fetched {len(trends)} Google Trends")
            return trends
        except Exception as e:
            logger.error(f"Error fetching Google Trends: {e}")
            return []
    
    def get_reddit_topics(self) -> List[str]:
        """Fetch hot topics from Reddit (via RSS, no auth needed)"""
        topics = []
        for subreddit in REDDIT_SUBREDDITS:
            try:
                rss_url = f"https://www.reddit.com/r/{subreddit}/hot/.rss"
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:10]:
                    title = entry.get('title', '').strip()
                    if title and len(title) > 10:
                        topics.append(title)
                logger.info(f"Fetched {len(feed.entries[:10])} topics from r/{subreddit}")
            except Exception as e:
                logger.error(f"Error fetching r/{subreddit}: {e}")
        return topics
    
    def generate_synthetic_topic(self) -> str:
        """Generate a psychological/dark topic when sources fail"""
        templates = [
            "Why {subject} {verb} {object}",
            "The dark psychology behind {subject}",
            "What {subject} reveals about human nature",
            "{subject}: The uncomfortable truth",
            "How {subject} manipulates your brain"
        ]
        
        subjects = [
            "silence", "eye contact", "first impressions", "body language",
            "compliments", "criticism", "rejection", "success", "failure",
            "confidence", "insecurity", "jealousy", "envy", "guilt"
        ]
        
        verbs = ["controls", "manipulates", "influences", "reveals", "exposes"]
        objects = ["your decisions", "your emotions", "people", "relationships", "success"]
        
        template = random.choice(templates)
        topic = template.format(
            subject=random.choice(subjects),
            verb=random.choice(verbs),
            object=random.choice(objects)
        )
        return topic
    
    def filter_relevant_topics(self, topics: List[str]) -> List[str]:
        """Filter topics relevant to our content categories"""
        relevant = []
        keywords = [
            "psychology", "brain", "mind", "behavior", "people", "human",
            "social", "money", "wealth", "success", "manipulation", "truth",
            "secret", "fact", "why", "how", "dark", "hidden", "never"
        ]
        
        for topic in topics:
            topic_lower = topic.lower()
            if any(keyword in topic_lower for keyword in keywords):
                if not self._is_topic_used(topic):
                    relevant.append(topic)
        
        return relevant
    
    def discover_topic(self, niche: str = None) -> str:
        """
        Main method: Discover a fresh, relevant topic
        Returns a topic string ready for script generation
        """
        logger.info(f"🔍 Starting topic discovery... (Niche: {niche})")
        
        # 1. AI-Driven Topic Generation (if niche provided)
        if niche:
            try:
                from model_manager import model_manager
                prompt = (
                    f"You are a viral YouTube Shorts producer. "
                    f"Suggest exactly 5 highly engaging, untold, or mind-blowing topic ideas for the niche: '{niche}'. "
                    f"Return ONLY a bulleted list of 5 short topic titles (no extra text, prefixes, or quotes). "
                    f"Make them sound like viral hooks."
                )
                response = model_manager.generate_content(prompt, task="topic_generation")
                
                if response:
                    lines = [line.strip().lstrip('*-1234567890. ') for line in response.split('\n') if line.strip()]
                    llm_topics = [t.strip('"\'') for t in lines if len(t) > 5]
                    
                    for topic in llm_topics:
                        if not self._is_topic_used(topic):
                            logger.info(f"✅ Selected AI-generated niche topic: {topic}")
                            self._mark_topic_used(topic)
                            return topic
            except Exception as e:
                logger.warning(f"AI Topic Generation failed: {e}. Falling back to standard sources.")

        # 2. Collect from all sources (Fallback)
        all_topics = []
        all_topics.extend(self.get_google_trends())
        all_topics.extend(self.get_reddit_topics())
        
        # Filter relevant topics
        relevant_topics = self.filter_relevant_topics(all_topics)
        
        # If no relevant topics found, generate synthetic
        if not relevant_topics:
            logger.warning("No relevant topics found, generating synthetic topic")
            for _ in range(10):  # Try 10 times to find unused synthetic topic
                topic = self.generate_synthetic_topic()
                if not self._is_topic_used(topic):
                    relevant_topics.append(topic)
                    break
        
        # Pick random topic
        if relevant_topics:
            topic = random.choice(relevant_topics)
            logger.info(f"✅ Selected topic: {topic}")
            self._mark_topic_used(topic)
            return topic
        
        # Absolute Fallback
        logger.error("Failed to discover any topic")
        raise Exception("Topic discovery failed")


if __name__ == "__main__":
    # Test
    agent = TrendAgent()
    topic = agent.discover_topic()
    print(f"Discovered topic: {topic}")