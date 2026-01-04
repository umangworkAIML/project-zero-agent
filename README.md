# 🧬 Recursive Self-Correcting Coding Agent

**Project Zero** is an autonomous AI agent capable of writing, executing, and fixing Python code without human intervention.

## 🚀 Capabilities
- **Autonomous Coding:** Generates Python scripts based on natural language prompts.
- **Self-Healing:** If execution fails, it reads the error log, debugs the issue, rewrites the code, and retries until success.
- **Live Internet Access:** Uses Tavily API to research missing libraries or documentation.
- **System Control:** Can install pip packages and manipulate files locally.

## 🛠️ Tech Stack
- **Brain:** Llama-3.3-70B (via Groq)
- **Orchestration:** LangGraph (State Machine)
- **Tools:** Python `subprocess`, Tavily Search API

## ⚡ How it Works
1. **Plan:** Analyzing the user request.
2. **Execute:** Writing and running code in a secure sandbox.
3. **Loop:** If error != 0, enter "Black Hole Mode" (Research -> Fix -> Retry).
