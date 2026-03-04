"""
Main Autonomous Agent - WEEKLY BATCH MODE
Generates 7 videos at once: 1 immediate + 6 scheduled
Run once per week
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import time

from trend_agent import TrendAgent
from script_agent import ScriptAgent
from voice_agent import VoiceAgent
from video_agent import VideoAgent
from metadata_agent import MetadataAgent
from youtube_agent import YouTubeAgent

# API Wrappers
from trend_agent_api import TrendAgentAPI

from config import LOG_FILE, TEMP_DIR, VIDEOS_PER_BATCH, LLM_ENGINE
from visual_engine import UserTier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class WeeklyBatchAgent:
    """
    Generates YouTube Shorts videos in batch.
    Supports any count: 1 video on-demand or 7 for weekly scheduling.
    Video 1 uploads immediately, remaining are scheduled daily.
    """
    
    def __init__(self, test_mode=False, user_tier: str = UserTier.FREE, youtube_creds: dict = None, preferences: dict = None):
        self.test_mode = test_mode
        self.preferences = preferences or {}
        logger.info("\n" + "🤖"*40)
        logger.info("AUTOTUBE AGENT - INITIALIZING")
        logger.info("🤖"*40 + "\n")
        
        # Extract new preferences
        self.video_format = self.preferences.get("video_format", "short")
        self.channel_style = self.preferences.get("channel_style", "narration")
        self.tone = self.preferences.get("tone", "serious")
        self.custom_topic = self.preferences.get("custom_topic", "")
        self.custom_niche = self.preferences.get("custom_niche", "")
        
        try:
            self.trend_agent = TrendAgentAPI(TrendAgent())
            self.script_agent = ScriptAgent(
                video_format=self.video_format,
                channel_style=self.channel_style,
                tone=self.tone
            )
            
            # Use voice from user preferences if set
            voice_name = self.preferences.get("voice")
            self.voice_agent = VoiceAgent(voice_name=voice_name)
            if voice_name:
                logger.info(f"🎤 Using user-selected voice: {voice_name}")
            
            # VideoAgent with tiered visual engine + bg_music preference
            bg_music = self.preferences.get("bg_music", "random")
            bg_music_volume = self.preferences.get("bg_music_volume", 0.15)
            self.video_agent = VideoAgent(
                user_tier=user_tier, 
                bg_music=bg_music, 
                bg_music_volume=bg_music_volume,
                video_format=self.video_format
            )
            
            self.metadata_agent = MetadataAgent()
            if not test_mode:
                self.youtube_agent = YouTubeAgent(credentials_dict=youtube_creds)
            else:
                self.youtube_agent = None
                logger.info("🧪 Generate-only mode: Skipping YouTube initialization")
            
            logger.info(f"✅ All agents initialized successfully")
            logger.info(f"   Format: {self.video_format.upper()} | Style: {self.channel_style} | Tone: {self.tone}\n")
            
            # Show channel info
            if self.youtube_agent:
                channel_info = self.youtube_agent.get_channel_info()
                if channel_info:
                    logger.info(f"📺 Connected to: {channel_info.get('title', 'Unknown')}")
                    logger.info(f"📊 Current stats: {channel_info.get('videos', 0)} videos, "
                               f"{channel_info.get('subscribers', 'Hidden')} subscribers\n")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize agents: {e}")
            raise
    
    def generate_single_video(self, video_number: int, total: int, niche: str = "mixed") -> tuple:
        """
        Generate one complete video
        Returns (video_path, metadata) tuple
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🎬 GENERATING VIDEO {video_number}/{total} (Niche: {niche})")
        logger.info(f"{'='*80}\n")
        
        try:
            # Step 1: Discover topic (or use custom topic)
            logger.info(f"[{video_number}/{total}] Step 1/6: Discovering topic...")
            if self.custom_topic:
                topic = self.custom_topic
                logger.info(f"✓ Using custom topic: {topic}\n")
            else:
                # Use custom_niche if provided, otherwise fallback to dropdown niche
                effective_niche = self.custom_niche if self.custom_niche else niche
                topic = self.trend_agent.discover_topic(niche=effective_niche)
                logger.info(f"✓ Topic: {topic}\n")
            
            # Step 2: Generate script (40-60 seconds, ultra-realistic)
            logger.info(f"[{video_number}/{total}] Step 2/6: Generating realistic script...")
            script_data = self.script_agent.generate_script(topic)
            full_text = script_data["full_text"]
            scenes = script_data["scenes"]
            logger.info(f"✓ Script ready ({len(full_text)} chars, {len(scenes)} scenes)\n")
            
            # Step 3: Generate voice
            logger.info(f"[{video_number}/{total}] Step 3/6: Creating voiceover...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"audio_{video_number}_{timestamp}.mp3"
            # we use full_text for voice generation
            audio_path = self.voice_agent.generate_audio(full_text, audio_filename)
            duration = self.voice_agent.get_audio_duration(audio_path)
            logger.info(f"✓ Audio generated ({duration:.1f}s)\n")
            
            # Step 4: Create premium video
            logger.info(f"[{video_number}/{total}] Step 4/6: Creating premium video...")
            video_filename = f"short_{video_number}_{timestamp}.mp4"
            video_path = self.video_agent.create_video(
                audio_path, duration, full_text, video_filename, scenes=scenes, niche=niche
            )
            logger.info(f"✓ Video created\n")
            
            # Step 5: Generate metadata
            logger.info(f"[{video_number}/{total}] Step 5/6: Generating metadata...")
            metadata = self.metadata_agent.generate_metadata(topic, full_text)
            logger.info(f"✓ Title: {metadata['title']}")
            logger.info(f"✓ Tags: {metadata['tags']}\n")
            
            # Cleanup audio (keep video for upload)
            try:
                audio_path.unlink()
            except:
                pass
            
            logger.info(f"✅ Video {video_number}/{total} ready for upload\n")
            
            return (video_path, metadata)
            
        except Exception as e:
            logger.error(f"❌ Error generating video {video_number}: {e}", exc_info=True)
            raise
    
    def run_weekly_batch(self, limit: int = None):
        """
        Main method: Generate videos and upload in batch
        limit: Max videos to generate (default: VIDEOS_PER_BATCH)
        """
        start_time = datetime.now()
        
        target_count = limit if limit else VIDEOS_PER_BATCH
        
        logger.info("\n" + "🌟"*40)
        logger.info("BATCH GENERATION - STARTING")
        logger.info(f"Target: {target_count} videos")
        logger.info(f"Started: {start_time.strftime('%Y-%m-%d %I:%M:%S %p')}")
        logger.info("🌟"*40 + "\n")
        
        videos_with_metadata = []
        
        try:
            providers = []
            if hasattr(self, '_model_manager_info'):
                providers = self._model_manager_info
            else:
                try:
                    from model_manager import model_manager
                    if getattr(model_manager, 'gemini_client', None):
                        providers.append("Gemini Flash")
                except Exception:
                    providers.append(LLM_ENGINE)
            logger.info(f"⚙️ [SYSTEM_INIT] LLM: {' → '.join(providers) if providers else LLM_ENGINE}")
            
            # Generate the requested number of videos
            niche = self.preferences.get("niche", "mixed")
            for i in range(1, target_count + 1):
                video_data = self.generate_single_video(i, target_count, niche=niche)
                videos_with_metadata.append(video_data)
                
                # Brief pause between generations
                if i < target_count:
                    logger.info("⏸️  Pausing 5 seconds before next video...\n")
                    time.sleep(5)
            
            logger.info("\n" + "="*80)
            logger.info("✅ ALL VIDEOS GENERATED SUCCESSFULLY")
            logger.info("="*80 + "\n")
            
            # Upload all videos in batch (if not in test mode)
            uploaded_ids = []
            if self.youtube_agent:
                logger.info("📤 Starting batch upload to YouTube...\n")
                uploaded_ids = self.youtube_agent.upload_batch(videos_with_metadata)
            else:
                logger.info("🧪 Test mode active: Skipping YouTube upload stage")
                uploaded_ids = [f"test_id_{i}" for i in range(1, len(videos_with_metadata) + 1)]
            
            # Dynamic summary based on actual results
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() / 60
            total_generated = len(uploaded_ids)
            
            logger.info("\n" + "🎉"*40)
            logger.info(f"SUCCESS! BATCH COMPLETE — {total_generated} VIDEO{'S' if total_generated > 1 else ''} GENERATED")
            logger.info("🎉"*40)
            logger.info(f"\n📊 SUMMARY:")
            logger.info(f"   Videos generated: {total_generated}")
            
            if total_generated == 1:
                logger.info(f"   Upload: 1 video (immediate)")
            elif total_generated <= 7:
                logger.info(f"   Upload: 1 video (immediate) + {total_generated - 1} scheduled (next {total_generated - 1} days)")
            else:
                logger.info(f"   Upload: {total_generated} videos queued")
            
            logger.info(f"   Visual tier: {self.video_agent.visual_engine.user_tier}")
            logger.info(f"   Total time: {duration:.1f} minutes")
            logger.info(f"   Completed: {end_time.strftime('%Y-%m-%d %I:%M:%S %p')}")
            
            if not self.youtube_agent:
                logger.info(f"\n🧪 TEST MODE — Videos were generated locally but NOT uploaded.")
                logger.info(f"   To upload, run with YouTube connected and test_mode=False.")
            else:
                logger.info(f"\n🔗 VIDEO LINKS:")
                for i, video_id in enumerate(uploaded_ids, start=1):
                    if total_generated == 1:
                        status = "🔴 LIVE NOW"
                    else:
                        status = "🔴 LIVE NOW" if i == 1 else f"📅 Scheduled (Day {i})"
                    logger.info(f"   Video {i}: https://youtube.com/shorts/{video_id} - {status}")
            
            # Cleanup video files (only in production, preserve for test mode preview)
            if self.test_mode:
                logger.info("\n📂 TEST MODE — Videos preserved for preview:")
                for video_path, metadata in videos_with_metadata:
                    logger.info(f"   🎥 {video_path}")
                    logger.info(f"      Title: {metadata.get('title', 'N/A')}")
            else:
                logger.info("\n🧹 Cleaning up generated video files...")
                for video_path, _ in videos_with_metadata:
                    try:
                        video_path.unlink()
                        logger.info(f"   Deleted: {video_path.name}")
                    except Exception as e:
                        logger.warning(f"   Could not delete {video_path.name}: {e}")
            
            logger.info(f"\n✅ Batch complete! Generated {total_generated} video{'s' if total_generated > 1 else ''}.\n")
            return True
            
        except Exception as e:
            logger.error(f"\n❌ BATCH FAILED: {e}\n", exc_info=True)
            logger.info("Please check the logs and try again.\n")
            return False


def main():
    """Entry point"""
    import argparse
    from datetime import timedelta
    
    parser = argparse.ArgumentParser(
        description='Weekly YouTube Shorts Batch Generator'
    )
    
    # Startup checks
    logger.info("🚀 Running startup checks...")
    parser.add_argument(
        '--test-single',
        action='store_true',
        help='Generate only 1 video for testing'
    )
    parser.add_argument(
        '--show-schedule',
        action='store_true',
        help='Show upload schedule without generating videos'
    )
    
    args = parser.parse_args()
    
    try:
        if args.show_schedule:
            # Just show the schedule
            agent = WeeklyBatchAgent()
            schedule_times = agent.youtube_agent.calculate_schedule_times()
            
            print("\n📅 Upload Schedule:")
            print(f"   Video 1: IMMEDIATE (as soon as you run)")
            for i, time in enumerate(schedule_times, start=2):
                print(f"   Video {i}: {time.strftime('%A, %B %d at %I:%M %p')}")
            print()
            
        elif args.test_single:
            # Test mode: generate only 1 video
            logger.info("🧪 TEST MODE: Generating 1 video only\n")
            agent = WeeklyBatchAgent(test_mode=True)
            video_data = agent.generate_single_video(1, 1)
            video_path, metadata = video_data
            
            logger.info("\n✅ Test video generated successfully!")
            logger.info(f"   Video: {video_path}")
            logger.info(f"   Title: {metadata['title']}")
            logger.info("\nTo upload this video, run without --test-single flag\n")
            
        else:
            # Full batch mode
            agent = WeeklyBatchAgent()
            success = agent.run_weekly_batch()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("\n\n⏹️  Stopped by user\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n\n❌ Fatal error: {e}\n", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()