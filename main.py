import os
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
sys_msg = """You are 'Project Zero', an elite autonomous coding agent with PERSISTENT MEMORY.
Your Goal: Solve the user's task completely. 
You have access to a computer. You can browse the web, write files, and execute code.

RULES:
1. **Remember Past Steps:** You can remember previous errors and attempts in this conversation.
2. **Recursive Fixing:** If execution fails, analyze the error, fix it, and RUN IT AGAIN.
3. **Verification:** Always execute the code to prove it works before finishing.

Start by planning, then writing code, then executing.
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
    print("🤖 PROJECT ZERO (with Memory): ONLINE (Type 'quit' to exit)")
    print("---------------------------------------------------------")
    
    # Thread ID: Ye is conversation ki unique ID hai. 
    # Jab tak ye ID same rahegi, Agent ko sab yaad rahega.
    config = {"configurable": {"thread_id": "main_conversation"}}

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