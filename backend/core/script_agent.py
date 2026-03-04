"""
Script Agent: Generates ULTRA-REALISTIC human-like YouTube Shorts scripts
40-60 seconds, conversational, engaging
"""

import logging
import re
from model_manager import model_manager
from config import SCRIPT_MIN_DURATION, SCRIPT_MAX_DURATION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScriptAgent:
    def __init__(self, video_format="short", channel_style="narration", tone="serious"):
        self.video_format = video_format
        self.channel_style = channel_style
        self.tone = tone
        self.primary_provider = "Cloud LLM (Gemini)"
        self.fallback_mode = "Survival Templates"
        self.failure_behavior = "LOG_ERROR_AND_FALLBACK"
        
        # Format-specific settings
        if video_format == "long":
            self.target_duration = "180-300"  # 3-5 minutes
            self.target_scenes = "12-18"
            self.insights_count = "8-12"
        else:
            self.target_duration = f"{SCRIPT_MIN_DURATION}-{SCRIPT_MAX_DURATION}"
            self.target_scenes = "4-5"
            self.insights_count = "3-5"
    
    def parse_scenes(self, raw_script: str) -> list[dict]:
        """Parse raw script into a list of scene dictionaries"""
        scenes = []
        
        # Remove potential markdown formatting from markers
        clean_script = raw_script.replace("**[SCENE]**", "[SCENE]").replace("**[/SCENE]**", "[/SCENE]")
        clean_script = clean_script.replace("**SPEECH:**", "SPEECH:").replace("**VISUAL:**", "VISUAL:")
        
        raw_scenes = clean_script.split("[SCENE]")
        
        for raw_scene in raw_scenes:
            if "[/SCENE]" not in raw_scene:
                continue
                
            scene_content = raw_scene.split("[/SCENE]")[0].strip()
            
            speech = ""
            visual = ""
            
            for line in scene_content.split("\n"):
                line = line.strip()
                # Remove potential markdown bolding from prefixes
                clean_line = line.replace("**", "")
                
                if clean_line.upper().startswith("SPEECH:"):
                    speech = clean_line[7:].strip()
                elif clean_line.upper().startswith("VISUAL:"):
                    visual = clean_line[7:].strip()
            
            if speech and visual:
                scenes.append({"speech": speech, "visual": visual})
        
        return scenes

    def generate_script(self, topic: str) -> dict:
        """
        Generate a highly realistic YouTube Short script using semantic chunking
        for faster inference and higher quality.
        """
        logger.info(f"📝 [CHUNKED_MODE] Starting multi-phase generation for: {topic}")
        
        try:
            # Phase 1: The Hook (5-8s)
            logger.info("🔗 [PHASE 1/3] Generating Hook...")
            hook_raw = model_manager.generate_content(self._get_hook_prompt(topic), task="script_hook")
            
            # Phase 2: The Insights (30-40s)
            logger.info("🧠 [PHASE 2/3] Generating Core Insights...")
            insights_raw = model_manager.generate_content(self._get_insights_prompt(topic, hook_raw), task="script_insights")
            
            # Phase 3: The Outro (5-7s)
            logger.info("🎬 [PHASE 3/3] Generating Outro & CTA...")
            outro_raw = model_manager.generate_content(self._get_outro_prompt(topic), task="script_outro")
            
            # Combine and parse
            raw_script = f"{hook_raw}\n{insights_raw}\n{outro_raw}"
            scenes = self.parse_scenes(raw_script)
            
            if not scenes:
                raise Exception("FAILED_TO_PARSE_CHUNKS")

            full_text = " ".join([s["speech"] for s in scenes])
            word_count = len(full_text.split())
            estimated_duration = word_count / 2.5
            
            logger.info(f"✅ [QUALITY_MODE: FULL] Chunked script ready: {len(scenes)} scenes ({estimated_duration:.1f}s)")
            
            return {
                "full_text": full_text,
                "scenes": scenes,
                "word_count": word_count,
                "estimated_duration": estimated_duration
            }

        except Exception as e:
            if "SURVIVAL_MODE_TRIGGER" in str(e):
                logger.warning(f"🏁 [QUALITY_MODE: FALLBACK] {self.primary_provider} unreachable. Using {self.fallback_mode}.")
            else:
                logger.error(f"❌ [CHUNK_FAILURE] Error during generation: {e}")
            return self._get_fallback_script(topic)

    def _get_style_instruction(self) -> str:
        """Build style instruction from channel_style and tone settings."""
        style_map = {
            "narration": "narrate in a calm, storytelling voice as if documenting a fascinating discovery",
            "what_if": "frame everything as hypothetical 'What if' scenarios, exploring alternate possibilities",
            "explainer": "explain complex concepts simply, like a patient teacher breaking things down step by step",
            "listicle": "present information as a numbered list of facts, tips, or reasons",
            "documentary": "speak like a cinematic documentary narrator — authoritative, dramatic, captivating",
        }
        tone_map = {
            "serious": "Keep the tone serious, measured and intellectual.",
            "casual": "Keep the tone casual, friendly and relatable — like talking to a friend.",
            "dramatic": "Use dramatic pauses, tension-building and suspenseful delivery.",
            "educational": "Focus on teaching and clarity — make the viewer learn something new.",
            "humorous": "Add subtle wit and humor — keep it clever, not silly.",
        }
        style = style_map.get(self.channel_style, style_map["narration"])
        tone = tone_map.get(self.tone, tone_map["serious"])
        return f"Channel style: {style}. {tone}"

    def _get_hook_prompt(self, topic: str) -> str:
        style_inst = self._get_style_instruction()
        duration = "5-8" if self.video_format == "short" else "10-15"
        return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a master {'Shorts' if self.video_format == 'short' else 'YouTube video'} creator. 
Generate a {duration} second magnetic, human-sounding hook about: {topic}
{style_inst}
<|eot_id|><|start_header_id|>user<|end_header_id|>
Use exactly this format:
[SCENE]
SPEECH: [Your hook]
VISUAL: [Visual descriptor]
[/SCENE]
<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    def _get_insights_prompt(self, topic: str, hook: str) -> str:
        style_inst = self._get_style_instruction()
        if self.video_format == "long":
            scene_inst = f"Generate {self.insights_count} scenes of detailed insights (150-250 seconds total)."
        else:
            scene_inst = f"Generate {self.insights_count} scenes of NEW core insights ONLY (30-40s total)."
        
        return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a script writer. Continue this {'short' if self.video_format == 'short' else 'video'} about {topic}.
The hook has ALREADY BEEN WRITTEN and will play first. DO NOT repeat it or paraphrase it.
Hook (already recorded, do NOT include): "{hook[:100]}..."
{style_inst}
<|eot_id|><|start_header_id|>user<|end_header_id|>
{scene_inst}
START with a completely new point — NOT a restatement of the hook.
Use contractions. Varied sentence lengths. 
Format:
[SCENE]
SPEECH: [Insight]
VISUAL: [Visual]
[/SCENE]
<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    def _get_outro_prompt(self, topic: str) -> str:
        style_inst = self._get_style_instruction()
        duration = "5-7" if self.video_format == "short" else "10-15"
        return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
Generate a {duration}s outro for {topic}.
{style_inst}
<|eot_id|><|start_header_id|>user<|end_header_id|>
Include "Drop a follow if this made you think."
Format:
[SCENE]
SPEECH: [Outro text]
VISUAL: [Symbolic visual]
[/SCENE]
<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    def _get_fallback_script(self, topic: str) -> dict:
        """Emergency hardcoded script template to prevent job death"""
        scenes = [
            {"speech": f"Ever wonder why {topic} is such a big deal? Well, basically, it's all about perspective.", "visual": f"{topic} overview"},
            {"speech": "Think about it. Here's the thing. Most people look at it one way, but there's a deeper layer most miss.", "visual": "Deep thinking abstract"},
            {"speech": "Actually, when you dive into the details, you know what's interesting? It's more about behavior than facts.", "visual": "Behavioral pattern visual"},
            {"speech": "So, keep this in mind next time you see it. It might just change your mind.", "visual": "Mind shift concept"},
            {"speech": "Right? Drop a follow if this made you think. We're diving deeper every day.", "visual": "Conclusion and follow CTA"}
        ]
        full_text = " ".join([s["speech"] for s in scenes])
        return {
            "full_text": full_text,
            "scenes": scenes,
            "word_count": len(full_text.split()),
            "estimated_duration": len(full_text.split()) / 2.5
        }

    def _get_prompt(self, topic: str) -> str:
        return f"""You are a master YouTube Shorts creator who writes scripts that sound 100% HUMAN and NATURAL.

Create a {SCRIPT_MIN_DURATION}-{SCRIPT_MAX_DURATION} second script about: {topic}

CRITICAL REQUIREMENTS FOR REALISM:

1. CONVERSATIONAL TONE:
   - Talk like you're speaking to a friend over coffee
   - Use contractions (you're, don't, it's, I've)
   - Use filler words occasionally (well, actually, so, basically)
   - Vary sentence length naturally
   - Use rhetorical questions to engage

2. NATURAL PACING:
   - Start with a relatable hook (not shocking, just interesting)
   - Build gradually with 4-5 key points
   - Use transitions that flow naturally (here's the thing, but wait, now...)
   - End with a thoughtful conclusion or call-to-action
   - Include natural pauses (write "..." where someone would pause)

3. HUMAN LANGUAGE PATTERNS:
   - Use "you know what's interesting?"
   - Say "I mean" or "think about it"
   - Use personal anecdotes style ("I've noticed that...")
   - Avoid overly formal or robotic phrasing
   - Sound like a smart friend, not a textbook

4. ENGAGEMENT WITHOUT CLICKBAIT:
   - Be genuinely interesting, not sensational
   - Provide real value and insight
   - Make people think, not just react
   - End with "Drop a follow if this made you think"

5. SCRIPT STRUCTURE (40-60 seconds):
   - Opening hook: 5-8 seconds
   - Main content: 30-45 seconds
   - Closing: 5-7 seconds

TONE: Conversational, thoughtful, genuine, like a knowledgeable friend

OUTPUT FORMAT (STRICT):
Output the script in distinct scenes. Each scene must follow this format:

[SCENE]
SPEECH: Write the conversational speech text here.
VISUAL: A highly specific description of an ABSTRACT, ENVIRONMENTAL, or OBJECT-FOCUSED scene. Change visuals frequently (every 4-6 seconds). NEVER describe human faces, hands, or bodies directly. Instead use: object close-ups, environmental shots, abstract concepts, or kinetic typography.
[/SCENE]

6. SCENE DENSITY:
   - You MUST generate between 8 to 12 distinct scenes.
   - Each scene should be approximately 4-6 seconds long.
   - This ensures high-frequency visual changes to keep viewers engaged.

CRITICAL: Total duration of all scenes combined must be {SCRIPT_MIN_DURATION}-{SCRIPT_MAX_DURATION} seconds.

Generate the script in the above format now:"""

    def validate_script_naturalness(self, script_text: str) -> bool:
        """
        Check if script sounds natural and human-like
        """
        natural_markers = [
            "you know", "i mean", "think about", "here's the thing",
            "actually", "basically", "well", "so", "...", "right?",
            "you're", "don't", "it's", "that's", "there's"
        ]
        
        script_lower = script_text.lower()
        marker_count = sum(1 for marker in natural_markers if marker in script_lower)
        
        is_natural = marker_count >= 3
        if is_natural:
            logger.info(f"✓ Script naturalness: PASS ({marker_count} natural markers)")
        else:
            logger.warning(f"⚠ Script naturalness: LOW ({marker_count} natural markers)")
        
        return is_natural


if __name__ == "__main__":
    # Test
    agent = ScriptAgent()
    topic = "Why people trust confident liars over honest people"
    result = agent.generate_script(topic)
    
    print(f"\n{'='*80}")
    print(f"SCENE-BASED SCRIPT ({result['estimated_duration']:.1f}s):")
    print(f"{'='*80}\n")
    for i, scene in enumerate(result['scenes'], 1):
        print(f"SCENE {i}:")
        print(f"  VISUAL: {scene['visual']}")
        print(f"  SPEECH: {scene['speech']}\n")
    print(f"{'='*80}")
    
    agent.validate_script_naturalness(result['full_text'])