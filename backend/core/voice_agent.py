"""
Voice Agent: Converts script to speech using Edge TTS
"""

import asyncio
import logging
import edge_tts
from pathlib import Path
from config import VOICE_NAME, VOICE_RATE, TEMP_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceAgent:
    def __init__(self, voice_name: str = None):
        self.voice = voice_name or VOICE_NAME
        self.rate = VOICE_RATE
    
    async def _generate_audio_async(self, script: str, output_path: Path):
        """Async audio generation with precise word-level subtitle timings"""
        communicate = edge_tts.Communicate(script, self.voice, rate=self.rate)
        
        word_boundaries = []
        
        with open(str(output_path), "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # chunk contains: offset, duration, text
                    word_boundaries.append({
                        "text": chunk["text"],
                        "offset": chunk["offset"],
                        "duration": chunk["duration"]
                    })
        
        # Save precise timing data for the video agent to use
        import json
        timing_path = output_path.with_suffix(".json")
        with open(timing_path, "w") as f:
            json.dump(word_boundaries, f)
    
    def generate_audio(self, script: str, output_filename: str = "audio.mp3") -> Path:
        """
        Generate audio from script
        Returns path to generated MP3 file
        """
        logger.info(f"🎤 Generating audio with voice: {self.voice}")
        
        output_path = TEMP_DIR / output_filename
        
        try:
            # Run async function
            asyncio.run(self._generate_audio_async(script, output_path))
            
            if output_path.exists():
                file_size = output_path.stat().st_size
                logger.info(f"✅ Audio generated: {output_path} ({file_size / 1024:.1f} KB)")
                return output_path
            else:
                raise Exception("Audio file not created")
                
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            raise
    
    def get_audio_duration(self, audio_path: Path) -> float:
        """Get duration of audio file in seconds"""
        try:
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 
                 'format=duration', '-of', 
                 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            duration = float(result.stdout)
            logger.info(f"Audio duration: {duration:.2f}s")
            return duration
        except Exception as e:
            logger.error(f"Error getting audio duration: {e}")
            return 30.0  # Default fallback


if __name__ == "__main__":
    # Test
    agent = VoiceAgent()
    test_script = "This is a test. YouTube Shorts are vertical videos. They can be up to 60 seconds long."
    audio_path = agent.generate_audio(test_script, "test_audio.mp3")
    duration = agent.get_audio_duration(audio_path)
    print(f"Generated audio: {audio_path}")
    print(f"Duration: {duration}s")