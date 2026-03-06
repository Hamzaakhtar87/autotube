"""
YouTube Service
Handles interactions with YouTube Data API for analytics and channel management.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.models.models import User, YouTubeAccount, ChannelStats, Video, VideoStats

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']


class YouTubeService:
    def __init__(self, credentials_json: dict):
        self.credentials = Credentials.from_authorized_user_info(credentials_json, SCOPES)
        self.youtube = build('youtube', 'v3', credentials=self.credentials)


    def get_channel_stats(self) -> Dict:
        """Fetch channel statistics."""
        request = self.youtube.channels().list(
            part="statistics,snippet,contentDetails",
            mine=True
        )
        response = request.execute()
        
        if not response['items']:
            return {}
            
        item = response['items'][0]
        stats = item['statistics']
        snippet = item['snippet']
        
        return {
            "channel_id": item['id'],
            "title": snippet['title'],
            "view_count": int(stats['viewCount']),
            "subscriber_count": int(stats['subscriberCount']),
            "video_count": int(stats['videoCount']),
            "thumbnail_url": snippet['thumbnails']['default']['url']
        }


    def get_video_stats(self, video_ids: List[str]) -> List[Dict]:
        """Fetch statistics for a list of videos."""
        if not video_ids:
            return []
            
        # YouTube API allows max 50 ids per request
        stats_list = []
        
        # Chunk into batches of 50
        chunks = [video_ids[i:i + 50] for i in range(0, len(video_ids), 50)]
        
        for chunk in chunks:
            request = self.youtube.videos().list(
                part="statistics,snippet",
                id=",".join(chunk)
            )
            response = request.execute()
            
            for item in response.get('items', []):
                stats = item['statistics']
                snippet = item['snippet']
                
                stats_list.append({
                    "id": item['id'],
                    "title": snippet['title'],
                    "view_count": int(stats.get('viewCount', 0)),
                    "like_count": int(stats.get('likeCount', 0)),
                    "comment_count": int(stats.get('commentCount', 0)),
                    "published_at": snippet['publishedAt']
                })
                
        return stats_list


def sync_channel_stats(db: Session, user: User):
    """Sync analytics for all user's connected channels."""
    accounts = db.query(YouTubeAccount).filter(YouTubeAccount.user_id == user.id).all()
    
    for account in accounts:
        if not account.credentials_json:
            continue
            
        try:
            from app.core.security import decrypt_dict
            creds = decrypt_dict(account.credentials_json)
            service = YouTubeService(creds)
            stats = service.get_channel_stats()
            
            if not stats:
                continue
                
            # Update Account Info
            account.channel_id = stats['channel_id']
            account.channel_name = stats['title']
            account.subscribers = stats['subscriber_count']
            account.views = stats['view_count']
            
            # Record History
            history = ChannelStats(
                youtube_account_id=account.id,
                subscribers=stats['subscriber_count'],
                total_views=stats['view_count'],
                video_count=stats['video_count']
            )
            db.add(history)
            
            # Sync Video Stats
            sync_video_stats(db, user, service, account)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to sync stats for user {user.id}: {str(e)}")


def sync_video_stats(db: Session, user: User, service: YouTubeService, account: YouTubeAccount):
    """Sync stats for videos associated with this account (that we know of)."""
    # Find videos in DB that have a youtube_id and belong to this user via jobs
    videos = db.query(Video).join(Video.job).filter(
        Video.job.has(user_id=user.id),
        Video.youtube_id.isnot(None)
    ).all()
    
    video_ids = [v.youtube_id for v in videos]
    if not video_ids:
        return
        
    stats_data = service.get_video_stats(video_ids)
    
    for data in stats_data:
        # Update Video record
        video = next((v for v in videos if v.youtube_id == data['id']), None)
        if video:
            video.title = data['title']
            
            # Record History
            v_stats = VideoStats(
                video_id=video.id,
                views=data['view_count'],
                likes=data['like_count'],
                comments=data['comment_count']
            )
            db.add(v_stats)

