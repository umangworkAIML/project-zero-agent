# 🧬 Project Zero: Autonomous Coding Agent (with Memory)

**Project Zero** is an elite autonomous AI agent capable of writing, executing, debugging, and fixing Python code without human intervention. 

Now upgraded with **Persistent Memory**, allowing it to remember context, user details, and past tasks even after the system is restarted—just like Jarvis.

## 🚀 Key Capabilities

### 🧠 Persistent Memory (New!)
- **Long-Term Recall:** Uses SQLite to store conversation history locally.
- **Context Awareness:** Remembers previous scripts, user preferences, and errors across different sessions.
- **Zero Hallucination:** Checks its own database before answering "Who am I?" or "What did we do yesterday?".

### 🛠️ Self-Healing Code Architecture
- **Recursive Debugging:** If a script fails, the Agent enters a "Black Hole Loop":
  1. Reads the error traceback.
  2. Searches the web (Tavily API) for solutions.
  3. Rewrites the code.
  4. Retries execution until success.
- **Environment Control:** Can install libraries (`pip install`) and manage the file system autonomously.

## 🏗️ Tech Stack
- **Brain:** Llama-3.3-70B (via Groq Cloud)
- **Memory:** SQLite + LangGraph Checkpoint
- **Orchestration:** LangGraph (State Machine)
- **Tools:** Python `subprocess`, Tavily Search API

## ⚡ How to Run
1. Clone the repo.
2. Install dependencies: `pip install -r requirements.txt`
3. Add API Keys in `.env`.
4. Run: `python main.py`

---
*Built with ❤️ by UMANG*