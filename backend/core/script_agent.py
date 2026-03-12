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
            self.target_scenes = "5-7"
            self.insights_count = "5-7"
    
    def parse_scenes(self, raw_script: str) -> list[dict]:
        """Parse raw script into scenes using dead-simple line-by-line matching. No regex."""
        scenes = []
        
        # Strip markdown bolding
        text = raw_script.replace("**", "").replace("*", "")
        
        current_speech = ""
        current_visual = ""
        mode = None  # 'speech' or 'visual'
        
        for line in text.split("\n"):
            stripped = line.strip()
            upper = stripped.upper()
            
            # Skip scene tags entirely
            if upper.startswith("[SCENE") or upper.startswith("[/SCENE"):
                # When we hit a new [SCENE tag and we have a complete pair, save it
                if upper.startswith("[SCENE") and not upper.startswith("[/SCENE"):
                    if current_speech.strip() and current_visual.strip():
                        scenes.append({"speech": current_speech.strip(), "visual": current_visual.strip()})
                        current_speech = ""
                        current_visual = ""
                        mode = None
                continue
            
            # Detect SPEECH: line
            if upper.startswith("SPEECH:") or upper.startswith("SPEECH :"):
                # Save previous pair if exists
                if current_speech.strip() and current_visual.strip():
                    scenes.append({"speech": current_speech.strip(), "visual": current_visual.strip()})
                    current_speech = ""
                    current_visual = ""
                
                mode = "speech"
                # Extract content after "SPEECH:"
                idx = stripped.find(":")
                if idx >= 0:
                    current_speech = stripped[idx+1:].strip() + " "
                continue
            
            # Detect VISUAL: line
            if upper.startswith("VISUAL:") or upper.startswith("VISUAL :"):
                mode = "visual"
                idx = stripped.find(":")
                if idx >= 0:
                    current_visual = stripped[idx+1:].strip() + " "
                continue
            
            # Continuation line — append to current mode
            if stripped and mode == "speech":
                current_speech += stripped + " "
            elif stripped and mode == "visual":
                current_visual += stripped + " "
        
        # Don't forget the last pair
        if current_speech.strip() and current_visual.strip():
            scenes.append({"speech": current_speech.strip(), "visual": current_visual.strip()})
        
        return scenes

    def generate_script(self, topic: str) -> dict:
        """
        Generate a YouTube Short script using semantic chunking.
        ENFORCES minimum duration (55-60s) programmatically — never trusts the LLM to count words.
        Falls back to guaranteed 58-second hardcoded script if all else fails.
        """
        logger.info(f"📝 [CHUNKED_MODE] Starting multi-phase generation for: {topic}")
        
        try:
            # Phase 1: The Hook (5-8s)
            logger.info("🔗 [PHASE 1/3] Generating Hook...")
            hook_raw = model_manager.generate_content(self._get_hook_prompt(topic), task="script_hook")
            
            # Phase 2: The Insights — this is where the bulk of the duration comes from
            logger.info("🧠 [PHASE 2/3] Generating Core Insights...")
            insights_raw = model_manager.generate_content(self._get_insights_prompt(topic, hook_raw), task="script_insights")
            
            # Phase 3: The Outro (5-7s)
            logger.info("🎬 [PHASE 3/3] Generating Outro & CTA...")
            outro_raw = model_manager.generate_content(self._get_outro_prompt(topic), task="script_outro")
            
            # Combine and parse
            raw_script = f"{hook_raw}\n{insights_raw}\n{outro_raw}"
            logger.info(f"📄 Raw LLM output ({len(raw_script)} chars):\n{raw_script[:500]}")
            
            try:
                scenes = self.parse_scenes(raw_script)
            except Exception as e:
                logger.error(f"Error parsing scenes: {e}")
                scenes = []
            
            if not scenes:
                logger.error(f"Raw script that failed parsing:\n{raw_script}")
                raise Exception("FAILED_TO_PARSE_CHUNKS")

            # ===== DURATION ENFORCEMENT LOOP =====
            full_text = " ".join([s["speech"] for s in scenes])
            word_count = len(full_text.split())
            estimated_duration = word_count / 2.5
            min_duration = SCRIPT_MIN_DURATION  # 55s from config.yml
            
            max_retries = 3
            retry = 0
            while estimated_duration < min_duration and retry < max_retries:
                deficit_seconds = min_duration - estimated_duration
                deficit_words = int(deficit_seconds * 2.5)
                logger.info(f"⚠️ Script too short ({estimated_duration:.1f}s). Need ~{deficit_words} more words. Requesting extra scenes (attempt {retry+1}/{max_retries})...")
                
                extra_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a script writer. Continue adding MORE scenes to a video about: {topic}.
The video currently has {len(scenes)} scenes but needs more content.
Write 2-3 NEW scenes with fresh facts/insights. Each scene MUST have 2-3 long detailed sentences.
<|eot_id|><|start_header_id|>user<|end_header_id|>
Format:
[SCENE]
SPEECH: [New insight with 2-3 detailed sentences]
VISUAL: [Visual descriptor]
[/SCENE]
<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
                
                try:
                    extra_raw = model_manager.generate_content(extra_prompt, task="script_extend")
                    logger.info(f"📄 Extension LLM output:\n{extra_raw[:300]}")
                    extra_scenes = self.parse_scenes(extra_raw)
                    logger.info(f"📄 Parsed {len(extra_scenes)} extra scenes")
                    if extra_scenes:
                        # Insert extra scenes BEFORE the last scene (outro)
                        outro_scene = scenes[-1]
                        scenes = scenes[:-1] + extra_scenes + [outro_scene]
                        full_text = " ".join([s["speech"] for s in scenes])
                        word_count = len(full_text.split())
                        estimated_duration = word_count / 2.5
                        logger.info(f"✅ Extended script: {len(scenes)} scenes ({estimated_duration:.1f}s)")
                    else:
                        logger.warning(f"⚠️ Extension returned 0 parseable scenes")
                except Exception as ext_e:
                    logger.warning(f"⚠️ Extension attempt failed: {ext_e}")
                
                retry += 1
            
            # ===== GUARANTEED FALLBACK =====
            # If after all retries the script is STILL too short, use the hardcoded 58-second script
            if estimated_duration < min_duration:
                logger.warning(f"⚠️ Script still too short after {max_retries} retries ({estimated_duration:.1f}s). Using guaranteed fallback script.")
                return self._get_fallback_script(topic)
            # ===== END ENFORCEMENT =====
            
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
        words = "max 20 words" if self.video_format == "short" else "max 40 words"
        return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a master {'Shorts' if self.video_format == 'short' else 'YouTube video'} creator. 
Generate a {duration} second magnetic, human-sounding hook about: {topic}
STRICT LIMIT: Keep the speech under {words} total.
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
            scene_inst = f"Generate {self.insights_count} scenes of detailed insights (150-250 seconds total). STRICT LIMIT: Maximum 400 words globally across all scenes."
        else:
            scene_inst = f"Generate EXACTLY {self.insights_count} scenes. STRICT LENGTH REQUIREMENT: You MUST write exactly 2 long, highly detailed sentences of spoken dialogue for EVERY single scene. NEVER use word counts. Just write exactly 2 full sentences per scene. This guarantees the voiceover hits the 55-60 second algorithm mark perfectly."
        
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
        words = "max 15 words" if self.video_format == "short" else "max 30 words"
        return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
Generate a {duration}s outro for {topic}.
STRICT LIMIT: Keep the speech under {words} total.
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
        """Emergency hardcoded script template to prevent job death — sized to hit 55-60s"""
        scenes = [
            {"speech": f"Ever wonder why {topic} is such a big deal? Well, it turns out there's way more to it than most people realize, and today we're going to break it all down.", "visual": f"{topic} overview"},
            {"speech": "Think about it for a second. Most people only see the surface level, but underneath there's a whole hidden layer that changes everything you thought you knew.", "visual": "Deep thinking abstract"},
            {"speech": "Here's what's really fascinating. When researchers actually looked into this, they found patterns that completely contradicted the conventional wisdom we've all been taught.", "visual": "Research data visualization"},
            {"speech": "And it gets even crazier. The deeper you dig, the more you realize it's not about what happened, but about why it happened and what it means for us today.", "visual": "Historical timeline montage"},
            {"speech": "Actually, when you dive into the details and really examine the evidence, you start to see connections that nobody talks about in the mainstream conversation.", "visual": "Behavioral pattern visual"},
            {"speech": "This is the part that blows most people's minds. The implications of all this are massive, and they affect everything from how we think to how we make decisions every single day.", "visual": "Mind-bending concept art"},
            {"speech": "So next time you come across this topic, remember what you learned here. It might just completely change the way you see the world around you.", "visual": "Perspective shift visual"},
            {"speech": "Drop a follow if this made you think. We're diving deeper into stories like this every single day, and trust me, the next one is even wilder.", "visual": "Conclusion and follow CTA"},
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