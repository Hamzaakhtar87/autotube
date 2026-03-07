"""
Video Agent: Creates PREMIUM QUALITY vertical 9:16 videos
High-quality visuals, karaoke-style subtitles, professional look
Supports multi-clip assembly with AI media and stock visuals
"""

import logging
import subprocess
import os
import random
from pathlib import Path
import requests
from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, TEMP_DIR, OUTPUT_DIR,
    BACKGROUND_VIDEO_PATH, VIDEO_BITRATE, AUDIO_BITRATE,
    VIDEO_PRESET, VIDEO_CRF, SUBTITLE_FONT, SUBTITLE_SIZE,
    SUBTITLE_COLOR, SUBTITLE_SECONDARY_COLOR, SUBTITLE_OUTLINE_COLOR, SUBTITLE_OUTLINE_WIDTH,
    SUBTITLE_SHADOW, SUBTITLE_MARGIN_V
)
from visual_engine import VisualEngine, UserTier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Background music assets
MUSIC_DIR = Path(__file__).parent / "assets" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)


class VideoAgent:
    def __init__(self, user_tier: str = UserTier.FREE, bg_music: str = "random", bg_music_volume: float = 0.15, video_format: str = "short"):
        self.video_format = video_format
        
        # Set dimensions based on format
        if video_format == "long":
            self.width = 1920   # 16:9 landscape
            self.height = 1080
        else:
            self.width = VIDEO_WIDTH   # 9:16 portrait (default)
            self.height = VIDEO_HEIGHT
        
        self.fps = VIDEO_FPS
        self.bg_music_setting = bg_music
        self.bg_music_volume = bg_music_volume
        self.visual_engine = VisualEngine(user_tier=user_tier)
        self._ensure_background()
    
    def _ensure_background(self):
        """Create or download premium background video"""
        is_valid = (
            BACKGROUND_VIDEO_PATH.exists() and 
            BACKGROUND_VIDEO_PATH.stat().st_size > 5000
        )
        
        if not is_valid:
            if BACKGROUND_VIDEO_PATH.exists():
                logger.warning("Existing background appears corrupted, re-creating...")
                BACKGROUND_VIDEO_PATH.unlink()
            
            logger.info("🎨 Creating premium background video...")
            self._create_premium_background()
    
    def _create_premium_background(self):
        """Create a simple solid background as fallback"""
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'color=c=0x0f0f23:s={self.width}x{self.height}:d=1',
            '-vf', "format=yuv420p",
            '-t', '1',
            '-r', str(self.fps),
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '35',
            '-y', str(BACKGROUND_VIDEO_PATH)
        ]
        try:
            subprocess.run(cmd, check=True)
            logger.info(f"✅ Premium background created")
        except:
            self._create_simple_background()
    
    def _create_simple_background(self):
        """Fallback: Create simple solid background"""
        cmd = [
            'ffmpeg', '-f', 'lavfi',
            '-i', f'color=c=0x1a1a2e:s={self.width}x{self.height}:d=1',
            '-vf', "format=yuv420p",
            '-r', str(self.fps),
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '35',
            '-y', str(BACKGROUND_VIDEO_PATH)
        ]
        subprocess.run(cmd, check=True)

    def _create_karaoke_subtitles(self, script: str, duration: float, audio_path: Path = None) -> Path:
        """
        Create dynamic '.ass' subtitles with word highlighting (Karaoke style)
        Uses exact TTS timing info if available for perfect sync.
        """
        ass_path = TEMP_DIR / "subtitles.ass"
        
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.width}
PlayResY: {self.height}
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUBTITLE_FONT},{SUBTITLE_SIZE},{SUBTITLE_COLOR},{SUBTITLE_SECONDARY_COLOR},{SUBTITLE_OUTLINE_COLOR},&H00000000,1,0,0,0,100,100,0,0,1,{SUBTITLE_OUTLINE_WIDTH},{SUBTITLE_SHADOW},2,10,10,{SUBTITLE_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        timing_path = None
        
        if audio_path:
            timing_path = audio_path.with_suffix(".json")
            
        import json
        if timing_path and timing_path.exists():
            # Perfect sync via Edge-TTS word boundaries
            try:
                with open(timing_path, "r") as f:
                    boundaries = json.load(f)
                
                # Group words (excluding spaces) into lines of 4
                words_per_line = 4
                current_line_idx = 0
                lines = [[]]
                
                for b in boundaries:
                    text = b["text"]
                    if not text.strip():  # Skip raw spaces, just add them to the previous word if needed
                        if lines[-1]:
                            lines[-1][-1]["text"] += text
                            lines[-1][-1]["duration"] += b["duration"]
                        continue
                        
                    lines[-1].append(b)
                    
                    if len(lines[-1]) >= words_per_line:
                        lines.append([])
                        
                for line in lines:
                    if not line: continue
                    # offset is in 100-ns units. 1 sec = 10,000,000
                    line_start_sec = line[0]["offset"] / 10_000_000.0
                    line_end_sec = (line[-1]["offset"] + line[-1]["duration"]) / 10_000_000.0
                    
                    line_text = ""
                    for w in line:
                        word_dur_cs = w["duration"] / 100_000.0
                        line_text += f"{{\\k{int(word_dur_cs)}}}{w['text']}"
                        
                    start_fmt = self._format_ass_time(line_start_sec)
                    end_fmt = self._format_ass_time(line_end_sec)
                    events.append(f"Dialogue: 0,{start_fmt},{end_fmt},Default,,0,0,0,,{line_text.strip()}")
            except Exception as e:
                logger.warning(f"Failed to load precise timings, falling back to estimations: {e}")
                events = []
                
        if not events:
            # Fallback mathematical estimation
            words = script.split()
            total_chars = sum(len(w) for w in words)
            time_per_char = duration / max(total_chars, 1)
            
            current_time = 0.0
            words_per_line = 3
            for i in range(0, len(words), words_per_line):
                line_words = words[i:i+words_per_line]
                line_start = current_time
                
                line_text = ""
                for word in line_words:
                    word_dur = len(word) * time_per_char
                    line_text += f"{{\\k{int(word_dur * 100)}}}{word} "
                    current_time += word_dur
                
                line_end = current_time
                start_formatted = self._format_ass_time(line_start)
                end_formatted = self._format_ass_time(line_end)
                events.append(f"Dialogue: 0,{start_formatted},{end_formatted},Default,,0,0,0,,{line_text.strip()}")

        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(header)
            f.write("\n".join(events))
            
        logger.info(f"✅ Karaoke subtitles created: {len(events)} lines")
        return ass_path

    def _format_ass_time(self, seconds: float) -> str:
        """Format time for ASS file (H:MM:SS.cc) where cc is centiseconds"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        cents = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{cents:02d}"

    def _prepare_scene_clips(self, scenes: list[dict], total_duration: float) -> list[Path]:
        """Download and prepare clips for each scene in PARALLEL with optimized effects"""
        import concurrent.futures
        
        clips = [None] * len(scenes)
        total_words = sum(len(s["speech"].split()) for s in scenes)
        
        def process_scene(i, scene):
            try:
                scene_words = len(scene["speech"].split())
                scene_duration = (scene_words / max(total_words, 1)) * total_duration
                
                logger.info(f"🎬 [Parallel] Preparing scene {i+1}/{len(scenes)}: {scene['visual']} ({scene_duration:.1f}s)")
                
                result = self.visual_engine.get_visual(scene["visual"], scene_duration)
                asset_path = result.path
                is_image = result.is_image
                
                if asset_path:
                    processed_clip = TEMP_DIR / f"processed_scene_{i}.mp4"
                    
                    if is_image:
                        # Optimized Ken Burns: Smoother zoom using a combination of scale and crop
                        cmd = [
                            'ffmpeg', '-loop', '1', '-i', str(asset_path),
                            '-vf', (
                                f"scale={self.width}:{self.height}:flags=fast_bilinear,setsar=1,"
                                f"zoompan=z='zoom+0.0015':d={int(scene_duration * self.fps)}:s={self.width}x{self.height}:fps={self.fps},"
                                "format=yuv420p"
                            ),
                            '-t', str(scene_duration),
                            '-c:v', 'libx264',
                            '-preset', 'ultrafast',
                            '-threads', '1',
                            '-an', '-y', str(processed_clip)
                        ]
                    else:
                        cmd = [
                            'ffmpeg', '-i', str(asset_path),
                            '-vf', (
                                f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase:flags=fast_bilinear,"
                                f"crop={self.width}:{self.height},"
                                f"setsar=1,fps={self.fps},format=yuv420p"
                            ),
                            '-t', str(scene_duration),
                            '-c:v', 'libx264',
                            '-preset', 'ultrafast',
                            '-threads', '1',
                            '-an', '-y', str(processed_clip)
                        ]
                    
                    subprocess.run(cmd, check=True, capture_output=True)
                    return i, processed_clip
                return i, None
            except Exception as e:
                logger.warning(f"Failed to process scene {i+1}: {e}")
                return i, None

        logger.info(f"⚡ Starting sequential visual processing for {len(scenes)} scenes (optimized for 512MB RAM)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            futures = [executor.submit(process_scene, i, scene) for i, scene in enumerate(scenes)]
            for future in concurrent.futures.as_completed(futures):
                idx, clip_path = future.result()
                if clip_path:
                    clips[idx] = clip_path
                    
        return [c for c in clips if c is not None]

    def create_video(self, audio_path: Path, duration: float, script: str, 
                     output_filename: str = "video.mp4", scenes: list = None, niche: str = "mixed") -> Path:
        """
        Create PREMIUM QUALITY video with karaoke-style highlighting
        """
        logger.info(f"🎬 Creating high-retention video (Karaoke)...")
        
        output_path = OUTPUT_DIR / output_filename
        subtitle_path = self._create_karaoke_subtitles(script, duration, audio_path)
        
        # 1. Prepare visual background
        bg_input = []
        filter_complex = ""
        
        if scenes:
            clips = self._prepare_scene_clips(scenes, duration)
            if clips:
                # Concatenate clips
                for i, clip in enumerate(clips):
                    bg_input.extend(['-i', str(clip)])
                
                filter_complex = "".join([f"[{i}:v]" for i in range(len(clips))])
                filter_complex += f"concat=n={len(clips)}:v=1:a=0[bg];"
            else:
                bg_input = ['-stream_loop', '-1', '-i', str(BACKGROUND_VIDEO_PATH)]
                filter_complex = "[0:v]copy[bg];"
        else:
            bg_input = ['-stream_loop', '-1', '-i', str(BACKGROUND_VIDEO_PATH)]
            filter_complex = "[0:v]copy[bg];"

        # 2. Add audio (voiceover + background music)
        input_count = bg_input.count('-i')
        audio_idx = input_count
        bg_input.extend(['-i', str(audio_path)])

        # 3. Add background music track (looped to cover full video)
        music_track = self._select_background_music(niche)
        music_idx = None
        if music_track:
            music_idx = audio_idx + 1
            bg_input.extend(['-stream_loop', '-1', '-i', str(music_track)])
            logger.info(f"🎵 Background music: {music_track.name}")
        else:
            logger.info("🔇 Background music disabled by user preference or not found")

        # 4. Build filter: video + subtitles + audio mix
        ass_filter_path = str(subtitle_path).replace(':', '\\:')
        final_filter = filter_complex + f"[bg]ass={ass_filter_path}[final]"

        # Audio: mix voiceover (full volume) + background music (subtle)
        if music_idx is not None:
            audio_filter = (
                f"[{audio_idx}:a]volume=1.0[voice];"
                f"[{music_idx}:a]volume={self.bg_music_volume},"
                f"afade=t=in:d=2,afade=t=out:st={max(0, duration-3)}:d=3[music];"
                f"[voice][music]amix=inputs=2:duration=first:dropout_transition=3:normalize=false[aout]"
            )
            final_filter += f";{audio_filter}"
            audio_map = ['-map', '[aout]']
        else:
            audio_map = ['-map', f'{audio_idx}:a']

        cmd = [
            'ffmpeg', *bg_input,
            '-filter_complex', final_filter,
            '-map', '[final]',
            *audio_map,
            '-t', str(duration),
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', str(VIDEO_CRF),
            '-b:v', VIDEO_BITRATE, '-c:a', 'aac', '-b:a', AUDIO_BITRATE,
            '-threads', '1',
            '-pix_fmt', 'yuv420p', '-y', str(output_path)
        ]

        try:
            logger.info("🎬 Rendering final video with background music + subtitles...")
            subprocess.run(cmd, check=True)
            
            # --- CLEANUP PHASE ---
            logger.info("🧹 Sweeping temporary visual files to free up disk space...")
            try:
                if subtitle_path and subtitle_path.exists():
                    subtitle_path.unlink()
                if scenes and clips:
                    for clip in clips:
                        if Path(clip).exists():
                            Path(clip).unlink()
                        
                        # Alsom delete the original downloaded asset (before scale/crop)
                        # We can derive the original from the processed clip filename
                        orig_clip = Path(clip).with_name(Path(clip).name.replace("processed_", ""))
                        if orig_clip.exists():
                            orig_clip.unlink()
                logger.info("🧹 Visual cache cleared successfully.")
            except Exception as e:
                logger.warning(f"Failed to cleanup some temp files: {e}")
                
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg render error: {e}")
            raise

    def _select_background_music(self, niche: str = "mixed") -> str:
        """Pick background music based on user setting and video niche."""
        if str(self.bg_music_setting).lower() in ("none", "false", ""):
            return None

        # Specific track requested
        if self.bg_music_setting and self.bg_music_setting != "random" and str(self.bg_music_setting).lower() != "true":
            track_path = MUSIC_DIR / self.bg_music_setting
            if track_path.exists():
                logger.info(f"🎵 Selected specific background music: {track_path.name}")
                return track_path
            else:
                logger.warning(f"⚠️ Requested track {self.bg_music_setting} not found, falling back to random.")

        # Map niches to musical moods
        niche_moods = {
            "psychology": "ambient",
            "science": "electronic",
            "finance": "corporate",
            "self_improvement": "inspirational",
            "history": "epic",
            "health": "meditation",
            "mixed": "lofi"
        }
        
        mood = niche_moods.get(niche.lower(), "lofi")

        # If random, pull from Archive.org open database API
        try:
            logger.info(f"🎵 Fetching random copyright-free {mood} beat from Archive.org API...")
            
            # 1. Search for public domain / FMA tracks matching the mood
            search_url = "https://archive.org/advancedsearch.php"
            params = {
                "q": f"mediatype:audio AND subject:{mood} AND format:mp3",
                "fl[]": "identifier",
                "sort[]": "downloads desc",
                "output": "json",
                "rows": 50
            }
            res = requests.get(search_url, params=params, timeout=10)
            res.raise_for_status()
            docs = res.json().get("response", {}).get("docs", [])
            
            if docs:
                chosen = random.choice(docs[:20]) # Top 20
                identifier = chosen.get("identifier")
                
                # 2. Get file URL for this identifier
                meta_url = f"https://archive.org/metadata/{identifier}"
                meta_res = requests.get(meta_url, timeout=10)
                meta_res.raise_for_status()
                
                # Find an mp3 from the response files
                files = meta_res.json().get("files", [])
                mp3s = [f for f in files if f.get("name", "").endswith(".mp3")]
                
                if mp3s:
                    mp3_name = mp3s[0]["name"]
                    download_url = f"https://archive.org/download/{identifier}/{mp3_name}"
                    
                    # 3. Download the track temporarily
                    random_track_path = MUSIC_DIR / f"{identifier}.mp3"
                    if not random_track_path.exists():
                        logger.info(f"Downloading track from API -> {random_track_path.name}")
                        mp3_bytes = requests.get(download_url, timeout=30).content
                        with open(random_track_path, "wb") as f:
                            f.write(mp3_bytes)
                    else:
                        logger.info(f"🎵 Using locally cached API track: {random_track_path.name}")

                    return random_track_path
                else:
                    logger.warning("No MP3 file inside the chosen API archive item.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch background music from API: {e}")

        # Final Fallback to local files if API fails
        tracks = [t for t in MUSIC_DIR.glob("*.mp3") if t.stat().st_size > 50_000]
        if not tracks:
            logger.warning("⚠️ No valid background music tracks found locally")
            return None

        track = random.choice(tracks)
        logger.info(f"🎵 Selected background music: {track.name} ({track.stat().st_size/1024:.0f}KB)")
        return track


if __name__ == "__main__":
    # Test stub
    pass