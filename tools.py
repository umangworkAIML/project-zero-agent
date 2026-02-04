import os
from dotenv import load_dotenv
# Sabse pehle khazana (Keys) load karo, import hone se pehle yaga pe gadbad hona matlab dot env me hamari api kharab nikal na
load_dotenv()
# hanbe yaha pe api keys ko insert kiya fir uske baaad hamne usko langchain se connect kiya
import subprocess
from langchain_community.tools.tavily_search import TavilySearchResults
# abhi ham langchain ke core tools ka use karne wale h jisse hame hamara main jo h hamne main python engine create kiya h wo load hoke uska usse kar sake
from langchain_core.tools import tool

# --- TOOL 0: VISION (Webcam + Gemini) ---
# Import the vision tool for multimodal capabilities
from vision import analyze_view_tool

# --- TOOL 1: THE EYES (Web Search) ---
# Ab isse key mil jayegi kyunki load_dotenv() upar run ho chuka hai agar run nahi hogi to new key laani padegi jabki hamari free trail khatam ho chuka h hame new key kharidni padegi iss agar new model aata h to future me me updation milega
search_tool = TavilySearchResults(max_results=2)

# --- TOOL 2: THE HANDS (File Writer) ---
# ye hamara main hands h jo ki files me codes likhenge, run  karenge and sahi karenge
@tool
def write_file(file_path: str, content: str):
    """Writes content to a file. Useful for saving Python code."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ File written successfully to {file_path}"
    except Exception as e:
        return f"❌ Error writing file: {e}"

# --- TOOL 3: THE ACTION (Code Executor) -z--
# hamne jo hath banaye the wo yaha pe kaam karenge and jo hath se bhul hui usko sudharenge and boom hamara automation create ho gaya
@tool
def execute_python_file(file_path: str):
    """Executes a Python file and returns the output or error."""
    try:
        # Safety Timeout: 10 seconds
        result = subprocess.run(
            ["python", file_path],
            capture_output=True,
            text=True,
            timeout=10 
        )
        
        if result.returncode == 0:
            return f"✅ Execution Success:\n{result.stdout}"
        else:
            return f"❌ Execution Failed:\nError: {result.stderr}\nOutput: {result.stdout}"
            
    except subprocess.TimeoutExpired:
        return "❌ Error: Code took too long to run (Timeout > 10s)."
    except Exception as e:
        return f"❌ System Error: {e}"
    
# abhi ham hamare saare tools ki list bana denge jisse file handling me koi kami naa rahe and kamm complete ho ae
# List of tools - Now includes vision capability!
tools = [analyze_view_tool, search_tool, write_file, execute_python_file]