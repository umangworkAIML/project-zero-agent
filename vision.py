"""
Vision Module for Project ZERO
Provides webcam capture and Gemini 1.5 Flash image analysis.
"""

import os
import time
import base64
import logging
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

import cv2
from PIL import Image
import google.generativeai as genai
from langchain_core.tools import tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
GEMINI_MODEL = "gemini-1.5-flash"
COOLDOWN_SECONDS = 5  # Minimum time between vision calls

# --- STATE ---
_last_vision_call = 0  # Timestamp of last vision call

# --- GEMINI SETUP ---
def _get_gemini_client():
    """Initialize and return Gemini client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL)


def _capture_frame() -> Image.Image:
    """
    Capture a single frame from the webcam.
    Returns: PIL Image object
    Raises: RuntimeError if webcam is unavailable
    """
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        raise RuntimeError("Cannot access webcam. Please check if camera is connected.")
    
    try:
        # Allow camera to warm up
        time.sleep(0.3)
        
        # Capture frame
        ret, frame = cap.read()
        
        if not ret or frame is None:
            raise RuntimeError("Failed to capture frame from webcam")
        
        # Convert BGR (OpenCV) to RGB (PIL)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        pil_image = Image.fromarray(frame_rgb)
        
        return pil_image
        
    finally:
        cap.release()


def analyze_view(query: str) -> str:
    """
    Capture a frame from webcam and analyze it using Gemini 1.5 Flash.
    
    Args:
        query: Natural language instruction for what to analyze
               (e.g., "Describe the scene", "What objects are visible?")
    
    Returns:
        Textual description from the vision model
    """
    global _last_vision_call
    
    # --- COOLDOWN CHECK ---
    current_time = time.time()
    time_since_last = current_time - _last_vision_call
    
    if time_since_last < COOLDOWN_SECONDS:
        wait_time = COOLDOWN_SECONDS - time_since_last
        logger.info(f"Vision cooldown active. Waiting {wait_time:.1f}s...")
        time.sleep(wait_time)
    
    _last_vision_call = time.time()
    
    try:
        # --- CAPTURE FRAME ---
        logger.info("📸 Capturing frame from webcam...")
        image = _capture_frame()
        logger.info("✅ Frame captured successfully")
        
        # --- SEND TO GEMINI ---
        logger.info("🧠 Sending to Gemini for analysis...")
        model = _get_gemini_client()
        
        # Construct prompt
        prompt = f"""Analyze this image and respond to the following query:
Query: {query}

Provide a clear, concise description. Focus only on what's visible in the image.
Do not make assumptions about things outside the frame."""
        
        # Generate response
        response = model.generate_content([prompt, image])
        
        if response and response.text:
            logger.info("✅ Gemini analysis complete")
            return response.text
        else:
            return "Vision analysis returned no results. Please try again."
            
    except RuntimeError as e:
        # Webcam issues
        logger.error(f"Webcam error: {e}")
        return f"⚠️ Vision unavailable: {str(e)}"
        
    except Exception as e:
        # Gemini API issues or other errors
        logger.error(f"Vision analysis failed: {e}")
        return "⚠️ Vision is temporarily unavailable. Please try again later."


# --- LANGCHAIN TOOL WRAPPER ---
@tool
def analyze_view_tool(query: str) -> str:
    """
    Use this tool to see through the webcam and analyze what's visible.
    
    Use this when the user asks:
    - "What do you see?"
    - "Look at this"
    - "Can you see me?"
    - "Describe what's in front of you"
    - Any question about the physical environment
    
    Args:
        query: What to look for or describe (e.g., "Describe the scene", 
               "What objects are on the desk?", "Is anyone there?")
    
    Returns:
        A textual description of what the webcam sees.
    """
    return analyze_view(query)


# --- TEST ---
if __name__ == "__main__":
    print("🔬 Testing Vision Module...")
    print("-" * 40)
    
    result = analyze_view("Describe everything you see in this image in detail.")
    print(f"\n📝 Result:\n{result}")
