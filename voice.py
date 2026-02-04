"""
Voice Module for Project ZERO
Provides Speech-to-Text (Google Speech Recognition) and Text-to-Speech (Edge-TTS).

Architecture:
- LAYER 1: Internal Agent Processing (silent, debug-only)
- LAYER 2: Spoken Response Generator (ActionContext → Hinglish)
- LAYER 3: TTS Output (Edge-TTS)
"""

import os
import sys
import asyncio
import threading
import tempfile
import logging
import queue
import time
import re
from typing import Optional, Callable
from dataclasses import dataclass, field

import speech_recognition as sr
import edge_tts
import pygame

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# ACTION CONTEXT: Structured data for spoken response generation
# ============================================================
@dataclass
class ActionContext:
    """
    Structured context extracted from agent execution.
    This is passed to the spoken response generator instead of raw text.
    """
    user_request: str
    tools_executed: list = field(default_factory=list)
    files_created: list = field(default_factory=list)
    files_executed: list = field(default_factory=list)
    execution_success: bool = True
    error_summary: str = ""
    search_performed: bool = False
    vision_used: bool = False
    final_ai_intent: str = ""  # What the AI intended to do (not verbatim output)

# --- CONFIGURATION ---
# Indian English male voice - handles Hinglish better than pure Hindi voice
# Avoids mispronunciation like "band" → "bend"
EDGE_TTS_VOICE = "en-IN-PrabhatNeural"  # English (India) - Male, natural Hinglish

# Shutdown keywords
SHUTDOWN_KEYWORDS = ["exit", "stop listening", "goodbye", "quit", "stop"]


def clean_for_speech(text: str) -> str:
    """
    Clean AI response for speech output.
    Removes code blocks, markdown, and technical content.
    """
    if not text:
        return ""
    
    # Remove code blocks (```...```)
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # Remove inline code (`...`)
    text = re.sub(r'`[^`]+`', '', text)
    
    # Remove markdown headers (# ## ###)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove markdown bold/italic (**text** or *text*)
    text = re.sub(r'\*+([^*]+)\*+', r'\1', text)
    
    # Remove markdown links [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Remove file paths (anything with / or \ and file extensions)
    text = re.sub(r'[A-Za-z]?:?[\\/][^\s]+\.\w+', '', text)
    
    # Remove URLs
    text = re.sub(r'https?://[^\s]+', '', text)
    
    # Remove bullet points and list markers
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove extra whitespace and newlines
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Trim
    text = text.strip()
    
    # If nothing left, return a default
    if not text or len(text) < 3:
        return "Ho gaya."
    
    return text


class VoiceListener:
    """
    Handles Speech-to-Text using Google Speech Recognition.
    Runs in a separate thread to avoid blocking.
    """
    
    def __init__(self, on_transcription: Callable[[str], None]):
        """
        Args:
            on_transcription: Callback function called with transcribed text
        """
        self.on_transcription = on_transcription
        self._running = False
        self._paused = False  # NEW: Pause flag to prevent feedback loop
        self._thread: Optional[threading.Thread] = None
        
        # Initialize recognizer
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Adjust recognizer settings for better accuracy
        self.recognizer.energy_threshold = 300  # Minimum audio energy to consider
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8  # Seconds of silence before phrase is complete
        
        # Calibrate for ambient noise
        logger.info("🎙️ Calibrating microphone...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
        logger.info("✅ Microphone ready")
        
    def pause(self):
        """Pause listening (used while AI is speaking to prevent feedback)."""
        self._paused = True
        logger.debug("🔇 Listener paused")
        
    def resume(self):
        """Resume listening after a short delay."""
        time.sleep(0.5)  # Small delay to let audio finish
        self._paused = False
        logger.debug("🔊 Listener resumed")
        
    def start(self):
        """Start the listening loop in a background thread."""
        if self._running:
            logger.warning("Listener is already running")
            return
            
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("🎤 Voice listener started")
        
    def stop(self):
        """Stop the listening loop gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("🛑 Voice listener stopped")
        
    def _listen_loop(self):
        """Main listening loop - records and transcribes audio."""
        while self._running:
            try:
                # Skip if paused (AI is speaking)
                if self._paused:
                    time.sleep(0.1)
                    continue
                    
                with self.microphone as source:
                    logger.info("🎤 Listening... (speak now)")
                    try:
                        # Listen with timeout
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
                    except sr.WaitTimeoutError:
                        continue  # No speech detected, keep listening
                
                # Skip transcription if paused during recording
                if self._paused:
                    continue
                
                # Transcribe using Google Speech Recognition (free)
                try:
                    text = self.recognizer.recognize_google(audio)
                    if text and text.strip():
                        # Filter out very short or likely noise
                        if len(text.strip()) > 2:
                            logger.info(f"📝 Transcribed: {text}")
                            self.on_transcription(text.strip())
                except sr.UnknownValueError:
                    logger.debug("Could not understand audio")
                except sr.RequestError as e:
                    logger.error(f"Speech recognition service error: {e}")
                    
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                time.sleep(1)  # Prevent rapid error loops


async def speak(text: str) -> None:
    """
    Convert text to speech using Edge-TTS and play it.
    
    Args:
        text: The text to speak
    """
    if not text or not text.strip():
        return
    
    # Truncate very long responses for speech
    if len(text) > 500:
        text = text[:500] + "... I'll stop there for brevity."
        
    logger.info(f"🔊 Speaking: {text[:50]}...")
    
    try:
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name
        
        # Generate speech
        communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
        await communicate.save(temp_path)
        
        # Play audio using pygame
        pygame.mixer.init()
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        
        # Wait for playback to complete
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
            
        pygame.mixer.quit()
        
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass
            
        logger.info("✅ Speech complete")
        
    except Exception as e:
        logger.error(f"TTS error: {e}")


def speak_sync(text: str) -> None:
    """Synchronous wrapper for speak()."""
    asyncio.run(speak(text))


class VoiceAssistant:
    """
    Main voice assistant with 3-layer architecture:
    1. INTERNAL LAYER - Agent reasoning (silent)
    2. SPOKEN RESPONSE LAYER - Generate human-friendly Hinglish summary
    3. TTS LAYER - Speak only the generated response
    """
    
    # ============================================================
    # SPOKEN RESPONSE PROMPT: Converts ActionContext to Hinglish
    # ============================================================
    SPOKEN_RESPONSE_PROMPT = """Tu ek voice assistant hai. Tujhe sirf BOLNE WALA response generate karna hai.

⚠️ STRICT RULES:
1. SIRF Hinglish mein bolo (Hindi + English mix)
2. Maximum 1-2 chhote sentences
3. KABHI code, file paths, ya technical output mat bolo
4. KABHI "INTERNAL_RESULT" ya logs verbatim mat padhna
5. Natural, friendly, polite tone
6. Context ke hisaab se bolo - kya kiya gaya

📋 CONTEXT (do NOT read this aloud, just understand):
- User ne kaha: {user_request}
- Tools used: {tools_used}
- Files created: {files_created}
- Execution: {execution_status}
- Vision used: {vision_used}
- Search done: {search_done}
- AI intent: {ai_intent}

✅ GOOD RESPONSES (copy this style):
- Code likha: "Ho gaya bhai, script ready hai. Chalaun kya?"
- Code chala: "Run kar diya, sab theek chal gaya."
- Error aaya: "Ek chhoti dikkat aayi, fix kar raha hoon."
- Search kiya: "Search kar liya, batata hoon kya mila."
- Vision dekha: "Haan dekh liya, samne [jo dikha wo]."
- General: "Ho gaya, dekhlo ek baar."

❌ BAD RESPONSES (NEVER say these):
- "The code has been executed successfully"
- "File written to calculator.py"
- "Tool execution completed"
- Any English-only formal response
- Reading code or technical output

Generate ONLY the spoken response (1-2 sentences, Hinglish):"""
    
    def __init__(self, agent_app, agent_config: dict):
        """
        Args:
            agent_app: The compiled LangGraph agent
            agent_config: Configuration dict with thread_id etc.
        """
        self.agent_app = agent_app
        self.agent_config = agent_config
        self._running = False
        self._response_queue = queue.Queue()
        self._listener: Optional[VoiceListener] = None
        
        # Initialize LLM for spoken response generation
        self._init_speech_llm()
        
    def _init_speech_llm(self):
        """Initialize a lightweight LLM for generating spoken responses."""
        import os
        from langchain_groq import ChatGroq
        
        self.speech_llm = ChatGroq(
            temperature=0.7,  # Slightly creative for natural speech
            model_name="llama-3.1-8b-instant",  # Fast, lightweight model
            groq_api_key=os.getenv("GROQ_API_KEY")
        )
        logger.info("🗣️ Speech LLM initialized")
        
    def _handle_transcription(self, text: str):
        """Callback for when speech is transcribed."""
        # Check for shutdown keywords
        text_lower = text.lower().strip()
        for keyword in SHUTDOWN_KEYWORDS:
            if keyword in text_lower:
                logger.info(f"🛑 Shutdown keyword detected: '{keyword}'")
                self._running = False
                self._safe_speak("Chalo, band kar raha hoon. Bye bye!")
                return
                
        # Queue the transcription for processing
        self._response_queue.put(text)
        
    def _safe_speak(self, text: str):
        """Speak while pausing the listener to prevent feedback."""
        if self._listener:
            self._listener.pause()
        speak_sync(text)
        if self._listener:
            self._listener.resume()
    
    def _generate_spoken_response(self, context: ActionContext) -> str:
        """
        LAYER 2: Generate a human-friendly spoken response from ActionContext.
        Uses structured context (NOT raw text) to generate natural Hinglish.
        """
        try:
            from langchain_core.messages import HumanMessage
            
            # Format context for prompt (structured, not raw)
            tools_str = ", ".join(context.tools_executed) if context.tools_executed else "none"
            files_created_str = ", ".join(context.files_created) if context.files_created else "none"
            execution_status = "success" if context.execution_success else f"error: {context.error_summary[:50]}"
            
            # Create prompt with structured context
            prompt = self.SPOKEN_RESPONSE_PROMPT.format(
                user_request=context.user_request,
                tools_used=tools_str,
                files_created=files_created_str,
                execution_status=execution_status,
                vision_used="yes" if context.vision_used else "no",
                search_done="yes" if context.search_performed else "no",
                ai_intent=context.final_ai_intent[:100] if context.final_ai_intent else "task completed"
            )
            
            # Generate spoken response
            response = self.speech_llm.invoke([HumanMessage(content=prompt)])
            spoken = response.content.strip()
            
            # Clean any remaining technical artifacts
            spoken = clean_for_speech(spoken)
            
            # Validate: if still too technical, use fallback
            if self._is_too_technical(spoken):
                spoken = self._get_fallback_response(context)
            
            logger.info(f"🗣️ Generated spoken response: {spoken[:50]}...")
            return spoken
            
        except Exception as e:
            logger.error(f"Speech generation error: {e}")
            return self._get_fallback_response(context)
    
    def _is_too_technical(self, text: str) -> bool:
        """Check if response contains technical content that shouldn't be spoken."""
        bad_patterns = [
            r'```',  # Code blocks
            r'\bdef\s+\w+\(',  # Function definitions
            r'\bclass\s+\w+',  # Class definitions
            r'\bimport\s+\w+',  # Import statements
            r'\.(py|js|txt|json)\b',  # File extensions
            r'[A-Z]:\\',  # Windows paths
            r'/home/',  # Linux paths
            r'error:|Error:|ERROR:',  # Error messages
            r'successfully executed',  # Robotic phrases
            r'execution complete',
        ]
        for pattern in bad_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _get_fallback_response(self, context: ActionContext) -> str:
        """Get a safe fallback response based on context."""
        if context.vision_used:
            return "Haan dekh liya, samne kya hai wo samajh gaya."
        elif context.search_performed:
            return "Search kar liya, jo mila wo batata hoon."
        elif context.files_created:
            return "Ho gaya bhai, file ready hai."
        elif not context.execution_success:
            return "Ek chhoti si dikkat aayi, dekh raha hoon."
        else:
            return "Ho gaya, sab theek hai."
        
    def _process_with_agent(self, user_input: str) -> tuple[ActionContext, str]:
        """
        LAYER 1: Send input to agent and extract ActionContext.
        Returns tuple of (ActionContext, raw_internal_for_debug)
        """
        from langchain_core.messages import HumanMessage
        
        # Initialize context
        context = ActionContext(user_request=user_input)
        raw_internal = ""  # For terminal debugging only
        
        try:
            input_message = HumanMessage(content=user_input)
            
            for event in self.agent_app.stream(
                {"messages": [input_message]}, 
                config=self.agent_config
            ):
                for key, value in event.items():
                    if key == "reasoner":
                        last_msg = value["messages"][-1]
                        if last_msg.content:
                            raw_internal = last_msg.content
                            # Extract intent (first line, stripped of code)
                            context.final_ai_intent = self._extract_intent(last_msg.content)
                        
                        # Track tool calls
                        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                tool_name = tc.get('name', 'unknown')
                                context.tools_executed.append(tool_name)
                                
                                # Extract file info from tool args
                                args = tc.get('args', {})
                                if tool_name == 'write_file' and 'file_path' in args:
                                    context.files_created.append(args['file_path'])
                                elif tool_name == 'execute_python_file' and 'file_path' in args:
                                    context.files_executed.append(args['file_path'])
                                elif tool_name == 'analyze_view_tool':
                                    context.vision_used = True
                                elif tool_name == 'tavily_search_results_json':
                                    context.search_performed = True
                                    
                    elif key == "tools":
                        # Check tool output for errors
                        last_msg = value["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            tool_output = str(last_msg.content)
                            if '❌' in tool_output or 'Error' in tool_output:
                                context.execution_success = False
                                context.error_summary = tool_output[:100]
                            logger.debug(f"Tool output: {tool_output[:100]}")
                            
            return context, raw_internal
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            context.execution_success = False
            context.error_summary = str(e)
            return context, f"Error: {str(e)}"
    
    def _extract_intent(self, raw_content: str) -> str:
        """
        Extract the AI's intent from raw content (first meaningful line).
        Strips code blocks and technical content.
        """
        # Remove code blocks
        cleaned = re.sub(r'```[\s\S]*?```', '', raw_content)
        # Get first non-empty line
        lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
        if lines:
            # Take first line, max 100 chars
            return lines[0][:100]
        return "task completed"
            
    def run(self):
        """Main voice interaction loop."""
        print("\n" + "=" * 50)
        print("🎤 PROJECT ZERO VOICE MODE ACTIVATED")
        print("=" * 50)
        print("Say 'exit', 'stop listening', or 'goodbye' to quit")
        print("Press Ctrl+C at any time to force shutdown")
        print("-" * 50 + "\n")
        
        self._running = True
        
        # Start listener
        self._listener = VoiceListener(self._handle_transcription)
        self._listener.start()
        
        # Greeting (pause listener during speech)
        self._safe_speak("Haan ji, main ready hoon. Bolo kya karna hai?")
        
        try:
            while self._running:
                try:
                    # Wait for transcription with timeout
                    user_text = self._response_queue.get(timeout=1.0)
                    
                    if not self._running:
                        break
                        
                    print(f"\n👤 You: {user_text}")
                    print("⚙️  Processing... (internal)\n")
                    
                    # Pause listener while processing and speaking
                    self._listener.pause()
                    
                    # ========================================
                    # LAYER 1: INTERNAL AGENT PROCESSING
                    # ========================================
                    # This is SILENT - user NEVER hears this
                    context, raw_internal = self._process_with_agent(user_text)
                    
                    # Terminal output (for developer debugging ONLY)
                    print(f"📋 [Internal - DEBUG ONLY]: {raw_internal[:200]}..." if len(raw_internal) > 200 else f"📋 [Internal - DEBUG ONLY]: {raw_internal}")
                    print(f"🔧 [Tools]: {context.tools_executed}")
                    print(f"📁 [Files created]: {context.files_created}")
                    print(f"✅ [Success]: {context.execution_success}")
                    
                    # ========================================
                    # LAYER 2: GENERATE SPOKEN RESPONSE
                    # ========================================
                    # Convert ActionContext (NOT raw text) to Hinglish
                    spoken_response = self._generate_spoken_response(context)
                    
                    print(f"\n🗣️ [Spoken - THIS GOES TO TTS]: {spoken_response}\n")
                    
                    # ========================================
                    # LAYER 3: TEXT-TO-SPEECH
                    # ========================================
                    # ONLY the spoken response goes to TTS
                    speak_sync(spoken_response)
                    
                    # Resume listening after speech completes
                    self._listener.resume()
                    
                except queue.Empty:
                    continue  # No transcription yet, keep listening
                    
        except KeyboardInterrupt:
            print("\n\n⚠️  Keyboard interrupt received")
            self._safe_speak("Theek hai, band kar raha hoon. Phir milenge!")
            
        finally:
            self._shutdown()
            
    def _shutdown(self):
        """Clean shutdown of all components."""
        logger.info("🧹 Cleaning up...")
        self._running = False
        
        if self._listener:
            self._listener.stop()
            
        # Ensure pygame is cleaned up
        try:
            pygame.mixer.quit()
        except:
            pass
            
        print("\n" + "=" * 50)
        print("👋 PROJECT ZERO VOICE MODE OFFLINE")
        print("=" * 50 + "\n")


# --- TEST ---
if __name__ == "__main__":
    print("🔬 Testing Voice Module...")
    print("-" * 40)
    
    # Test TTS
    print("\n1. Testing Text-to-Speech...")
    asyncio.run(speak("Hello! Voice module test."))
    
    print("\n✅ Voice module test complete!")
