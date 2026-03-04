import os
import logging
import random
from api_registry import get_apis_for_niche
from trend_agent import TrendAgent

logger = logging.getLogger(__name__)

class TrendAgentAPI:
    def __init__(self, trend_agent: TrendAgent):
        self.trend_agent = trend_agent
        from config import USE_API_TOPICS
        self.use_api_topics = USE_API_TOPICS

    def discover_topic(self, niche: str = None) -> str:
        """
        Enriches trend discovery with API data and returns a single topic.
        """
        all_base = []
        all_base.extend(self.trend_agent.get_google_trends())
        all_base.extend(self.trend_agent.get_reddit_topics())
        base_filtered = self.trend_agent.filter_relevant_topics(all_base)

        if not self.use_api_topics or not niche:
            if base_filtered and (not niche or niche.lower() == "mixed"):
                topic = random.choice(base_filtered)
                self.trend_agent._mark_topic_used(topic)
                return topic
            return self.trend_agent.discover_topic(niche=niche)

        logger.info(f"📈 Enriching trends with Public APIs for niche: {niche}...")
        api_topics = []
        
        apis = get_apis_for_niche(niche.lower())
        for api in apis:
            try:
                new_trends = api.fetch_trends([])
                if new_trends:
                    api_topics.extend(new_trends)
            except Exception as e:
                logger.warning(f"❌ Trend fetch failed for {api.name}: {e}")

        # If there's a specific niche that isn't 'mixed', don't dilute it with global Reddit/Google trends
        if niche and niche.lower() != "mixed":
            combined = list(set(api_topics))
        else:
            combined = list(set(base_filtered + api_topics))
            
        if combined:
            topic = random.choice(combined)
            logger.info(f"✨ Selected enriched topic: {topic}")
            self.trend_agent._mark_topic_used(topic)
            return topic
        
        # Absolute fallback to original discover_topic (Template/Synthetic/AI)
        return self.trend_agent.discover_topic(niche=niche)

    def __getattr__(self, name):
        return getattr(self.trend_agent, name)
