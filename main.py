import os
import argparse
from dotenv import load_dotenv
# 1. Environment Load
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

# --- NEW IMPORTS FOR MEMORY ---
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Import our custom tools
from tools import tools

# --- SETUP: DATABASE CONNECTION ---
# Ye 'memory.db' file banayega jahan sab save hoga
db_path = "memory.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
memory = SqliteSaver(conn)
print(f"🧠 Memory connected to {db_path}")

# --- SETUP: THE BRAIN ---
llm = ChatGroq(
    temperature=0, 
    model_name="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("GROQ_API_KEY")
)
llm_with_tools = llm.bind_tools(tools)

# --- SYSTEM PROMPT ---
sys_msg = """You are 'Project Zero', an autonomous AI engineer with a voice interface.

━━━━━━━━━━━━━━━━━━━━━━
CORE AUTONOMOUS CODING (INTERNAL, SILENT)
━━━━━━━━━━━━━━━━━━━━━━
Your Goal: Solve the user's task completely.
You can browse the web, write files, execute code, and debug.

RULES:
1. Remember past errors and attempts.
2. If execution fails → analyze error → fix → RUN AGAIN.
3. Always execute code to verify it works.
4. Loop: Write → Execute → Debug → Fix → Repeat until success.

This happens INTERNALLY. Never speak these steps.

━━━━━━━━━━━━━━━━━━━━━━
VISION CAPABILITY
━━━━━━━━━━━━━━━━━━━━━━
You have webcam access via 'analyze_view_tool'.
- Triggers: "What do you see?", "Kya dikh raha hai?", "Look at this"
- Use silently. Never announce tool usage.

━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━
Your response will be SPOKEN ALOUD via Text-to-Speech.

NEVER include in your response:
- Code blocks (```python ... ```)
- Technical logs or stack traces
- Tool names or function calls
- Markdown formatting
- File paths or terminal commands

If you wrote code, DON'T show it. Just say:
- "Ho gaya, code likh diya aur run bhi kar diya."
- "Script ready hai, chal bhi gaya."

If user ASKS to see the code, tell them:
- "Code file mein save kar diya hai, dekh lo."

━━━━━━━━━━━━━━━━━━━━━━
SPEAKING STYLE (HINGLISH)
━━━━━━━━━━━━━━━━━━━━━━
Speak in casual Hinglish (Hindi + English mix).
Sound like a real friend talking.

GOOD:
- "Haan, dekh raha hoon."
- "Ruk, ek second."
- "Ho gaya bhai, sab theek hai."
- "Isme thoda bug tha, fix kar diya."

BAD (NEVER SAY):
- "The code has been executed successfully."
- "According to the analysis..."
- "Tool invocation completed."
- Any code or technical output.

━━━━━━━━━━━━━━━━━━━━━━
TOOL USAGE
━━━━━━━━━━━━━━━━━━━━━━
- Use tools SILENTLY. Never announce them.
- If tool fails: "Abhi ye kaam nahi kar raha, dekh raha hoon."
- Give results naturally, not technically.

Your response is for a HUMAN to HEAR. Keep it short, friendly, natural.
"""



# --- STATE MANAGEMENT ---
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- NODE 1: THE REASONER ---
def reasoner(state: AgentState):
    return {"messages": [llm_with_tools.invoke([SystemMessage(content=sys_msg)] + state["messages"])]}

# --- GRAPH CONSTRUCTION ---
builder = StateGraph(AgentState)
builder.add_node("reasoner", reasoner)
builder.add_node("tools", ToolNode(tools))
builder.set_entry_point("reasoner")
builder.add_conditional_edges("reasoner", tools_condition)
builder.add_edge("tools", "reasoner")

# --- COMPILE WITH MEMORY ---
# Yahan humne graph ko memory (checkpointer) de di
app = builder.compile(checkpointer=memory)

# --- MAIN EXECUTION LOOP ---
if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Project Zero - Autonomous Coding Agent")
    parser.add_argument(
        "--voice", 
        action="store_true", 
        help="Enable voice mode (listen with mic, speak responses)"
    )
    args = parser.parse_args()
    
    # Thread ID: Ye is conversation ki unique ID hai. 
    # Jab tak ye ID same rahegi, Agent ko sab yaad rahega.
    config = {"configurable": {"thread_id": "main_conversation"}}
    
    if args.voice:
        # === VOICE MODE ===
        # Listen (Whisper) → Text → Agent (Groq) → Response → Speak (Edge-TTS)
        from voice import VoiceAssistant
        
        print("🎤 Initializing Voice Mode...")
        assistant = VoiceAssistant(app, config)
        assistant.run()
        
    else:
        # === TEXT MODE (Original) ===
        print("🤖 PROJECT ZERO (with Memory): ONLINE (Type 'quit' to exit)")
        print("---------------------------------------------------------")
        
        while True:
            user_input = input("You: ")
            if user_input.lower() in ["quit", "exit"]:
                break
            
            # Notice: Hum purani state nahi bhej rahe, sirf naya message bhej rahe hain.
            # Baaki sab wo database se utha lega.
            input_message = HumanMessage(content=user_input)
            print("\n⚙️  Processing... \n")
            
            for event in app.stream({"messages": [input_message]}, config=config):
                for key, value in event.items():
                    if key == "reasoner":
                        last_msg = value["messages"][-1]
                        print(f"🧠 AI: {last_msg.content}")
                        if last_msg.tool_calls:
                            print(f"🔧 Tool Call: {last_msg.tool_calls[0]['name']}")
                    elif key == "tools":
                        last_msg = value["messages"][-1]
                        print(f"⚡ Tool Output: {last_msg.content[:200]}...")
            
            print("\n" + "-"*40 + "\n")