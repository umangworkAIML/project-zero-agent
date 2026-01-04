import os
from dotenv import load_dotenv
# Sabse pehle khazana (Keys) load karo, import hone se pehle
load_dotenv()

import subprocess
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool

# --- TOOL 1: THE EYES (Web Search) ---
# Ab isse key mil jayegi kyunki load_dotenv() upar run ho chuka hai
search_tool = TavilySearchResults(max_results=2)

# --- TOOL 2: THE HANDS (File Writer) ---
@tool
def write_file(file_path: str, content: str):
    """Writes content to a file. Useful for saving Python code."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ File written successfully to {file_path}"
    except Exception as e:
        return f"❌ Error writing file: {e}"

# --- TOOL 3: THE ACTION (Code Executor) ---
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

# List of tools
tools = [search_tool, write_file, execute_python_file]