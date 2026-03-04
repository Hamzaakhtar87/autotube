"""
YouTube Agent: Uploads videos DIRECTLY TO PUBLIC with scheduling
Batch mode: Upload 1 now + schedule 6 for next 6 days
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from config import (
    YOUTUBE_CLIENT_SECRETS, YOUTUBE_CREDENTIALS, 
    UPLOAD_PRIVACY, UPLOAD_TIME_HOUR, UPLOAD_TIME_MINUTE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]


class YouTubeAgent:
    def __init__(self, credentials_dict: Optional[dict] = None):
        self.service = None
        self._authenticate(credentials_dict)
    
    def _authenticate(self, credentials_dict: Optional[dict]):
        """Authenticate with YouTube API"""
        creds = None
        
        # 1. Try DB credentials first (SaaS mode)
        if credentials_dict:
            logger.info("🔑 Using provided SaaS user credentials...")
            creds = Credentials.from_authorized_user_info(credentials_dict, SCOPES)
            
        # 2. Fallback to local files (Standalone mode)
        elif YOUTUBE_CREDENTIALS.exists():
            logger.info("🔑 Using local standalone credentials...")
            with open(YOUTUBE_CREDENTIALS, 'rb') as token:
                creds = pickle.load(token)
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("🔄 Refreshing YouTube credentials...")
                creds.refresh(Request())
            elif credentials_dict:
                # In SaaS mode, if creds are invalid and can't refresh, fail loudly.
                raise Exception("❌ Provided DB credentials are invalid and cannot be refreshed. User must reconnect YouTube.")
            else:
                logger.info("🔐 Authenticating with YouTube via Local Server...")
                if not YOUTUBE_CLIENT_SECRETS.exists():
                    raise Exception(
                        f"\n❌ MISSING: {YOUTUBE_CLIENT_SECRETS}\n\n"
                        f"Please download OAuth 2.0 credentials:\n"
                        f"1. Go to: https://console.cloud.google.com/\n"
                        f"2. Create a project\n"
                        f"3. Enable YouTube Data API v3\n"
                        f"4. Create OAuth 2.0 credentials (Desktop app)\n"
                        f"5. Download as 'client_secrets.json'\n"
                        f"6. Place in: {YOUTUBE_CLIENT_SECRETS.parent}\n"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(YOUTUBE_CLIENT_SECRETS), SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save local credentials ONLY if not using SaaS dict
            if not credentials_dict:
                with open(YOUTUBE_CREDENTIALS, 'wb') as token:
                    pickle.dump(creds, token)
        
        # Build service
        self.service = build('youtube', 'v3', credentials=creds)
        logger.info("✅ YouTube API authenticated")
    
    def upload_video(self, 
                     video_path: Path, 
                     metadata: Dict[str, str],
                     schedule_time: Optional[datetime] = None,
                     video_number: int = 1) -> str:
        """
        Upload video to YouTube
        
        Args:
            video_path: Path to video file
            metadata: Dict with 'title', 'description', 'tags'
            schedule_time: If provided, schedule for this time (must be >1hr future)
            video_number: Video number in batch (for logging)
        
        Returns:
            video_id of uploaded video
        """
        
        # Determine privacy status
        if schedule_time:
            # Scheduled videos must be private first, then become public at schedule time
            privacy_status = "private"
            upload_type = f"SCHEDULED (#{video_number}/7)"
        else:
            # Immediate upload goes public
            privacy_status = UPLOAD_PRIVACY
            upload_type = f"IMMEDIATE (#{video_number}/7)"
        
        logger.info(f"📤 Uploading video {upload_type}: {video_path.name}")
        
        # Prepare metadata
        body = {
            'snippet': {
                'title': metadata['title'],
                'description': metadata['description'],
                'tags': [tag.strip() for tag in metadata['tags'].split(',') if tag.strip()],
                'categoryId': '22'  # People & Blogs
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False,
                'madeForKids': False
            }
        }
        
        # Add scheduling if specified
        if schedule_time:
            # YouTube requires ISO 8601 format with Z timezone
            publish_time = schedule_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            body['status']['publishAt'] = publish_time
            body['status']['privacyStatus'] = 'private'  # Must be private when scheduling
            logger.info(f"   📅 Scheduled for: {schedule_time.strftime('%Y-%m-%d at %I:%M %p')}")
        else:
            logger.info(f"   🔴 LIVE: Uploading as PUBLIC now")
        
        # Prepare upload
        media = MediaFileUpload(
            str(video_path),
            chunksize=-1,  # Upload in single request for speed
            resumable=True,
            mimetype='video/mp4'
        )
        
        try:
            # Execute upload
            request = self.service.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            response = None
            last_progress = 0
            
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    if progress != last_progress and progress % 10 == 0:
                        logger.info(f"   Upload progress: {progress}%")
                        last_progress = progress
            
            video_id = response['id']
            video_url = f"https://youtube.com/shorts/{video_id}"
            
            logger.info(f"✅ Upload successful!")
            logger.info(f"   Video ID: {video_id}")
            logger.info(f"   URL: {video_url}")
            
            if schedule_time:
                logger.info(f"   Status: Scheduled for {schedule_time.strftime('%Y-%m-%d %I:%M %p')}")
            else:
                logger.info(f"   Status: PUBLIC and LIVE now")
            
            return video_id
            
        except HttpError as e:
            error_content = e.content.decode() if e.content else str(e)
            logger.error(f"❌ YouTube API error: {error_content}")
            
            # Provide helpful error messages
            if "quotaExceeded" in error_content:
                logger.error("   Quota exceeded. Wait 24 hours or request quota increase.")
            elif "forbidden" in error_content.lower():
                logger.error("   Permission denied. Check OAuth scopes and API is enabled.")
            
            raise
        except Exception as e:
            logger.error(f"❌ Upload error: {e}")
            raise
    
    def calculate_schedule_times(self, start_date: Optional[datetime] = None) -> list[datetime]:
        """
        Calculate upload times for the next 6 days
        Returns list of 6 datetime objects
        """
        if start_date is None:
            start_date = datetime.now()
        
        schedule_times = []
        
        for day in range(1, 7):  # Days 1-6 (today's video uploads immediately)
            next_day = start_date + timedelta(days=day)
            scheduled_time = next_day.replace(
                hour=UPLOAD_TIME_HOUR,
                minute=UPLOAD_TIME_MINUTE,
                second=0,
                microsecond=0
            )
            schedule_times.append(scheduled_time)
        
        return schedule_times
    
    def get_channel_info(self) -> Dict:
        """Get info about authenticated channel"""
        try:
            request = self.service.channels().list(
                part='snippet,statistics',
                mine=True
            )
            response = request.execute()
            
            if response['items']:
                channel = response['items'][0]
                info = {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'subscribers': channel['statistics'].get('subscriberCount', 'Hidden'),
                    'views': channel['statistics']['viewCount'],
                    'videos': channel['statistics']['videoCount']
                }
                return info
            else:
                raise Exception("No channel found")
                
        except Exception as e:
            logger.error(f"Error getting channel info: {e}")
            return {}
    
    def upload_batch(self, videos_with_metadata: list) -> list[str]:
        """
        Upload a batch of 7 videos:
        - Video 1: Immediate public upload
        - Videos 2-7: Scheduled for next 6 days
        
        Args:
            videos_with_metadata: List of (video_path, metadata) tuples
        
        Returns:
            List of video IDs
        """
        logger.info("\n" + "="*80)
        logger.info("📦 STARTING BATCH UPLOAD: 7 VIDEOS")
        logger.info("="*80 + "\n")
        
        if len(videos_with_metadata) != 7:
            raise ValueError(f"Expected 7 videos, got {len(videos_with_metadata)}")
        
        video_ids = []
        schedule_times = self.calculate_schedule_times()
        
        # Upload first video immediately
        video_path, metadata = videos_with_metadata[0]
        logger.info("🎬 VIDEO 1/7: Uploading immediately as PUBLIC")
        video_id = self.upload_video(video_path, metadata, schedule_time=None, video_number=1)
        video_ids.append(video_id)
        
        logger.info("\n" + "-"*80 + "\n")
        
        # Upload remaining 6 videos as scheduled
        for i, (video_path, metadata) in enumerate(videos_with_metadata[1:], start=2):
            schedule_time = schedule_times[i-2]
            logger.info(f"📅 VIDEO {i}/7: Scheduling for {schedule_time.strftime('%a, %b %d at %I:%M %p')}")
            video_id = self.upload_video(
                video_path, 
                metadata, 
                schedule_time=schedule_time,
                video_number=i
            )
            video_ids.append(video_id)
            
            if i < 7:
                logger.info("\n" + "-"*80 + "\n")
        
        logger.info("\n" + "="*80)
        logger.info("✅ BATCH UPLOAD COMPLETE!")
        logger.info(f"   Total videos: {len(video_ids)}")
        logger.info(f"   Live now: 1")
        logger.info(f"   Scheduled: 6")
        logger.info("="*80 + "\n")
        
        return video_ids


if __name__ == "__main__":
    # Test
    agent = YouTubeAgent()
    
    # Get channel info
    channel_info = agent.get_channel_info()
    print(f"\n📺 Channel: {channel_info.get('title', 'Unknown')}")
    print(f"📊 Videos: {channel_info.get('videos', 0)}")
    print(f"👥 Subscribers: {channel_info.get('subscribers', 'Hidden')}")
    
    # Show schedule times
    schedule_times = agent.calculate_schedule_times()
    print(f"\n📅 Next 6 scheduled upload times:")
    for i, time in enumerate(schedule_times, start=1):
        print(f"   Day {i}: {time.strftime('%A, %B %d at %I:%M %p')}")