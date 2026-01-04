import os
from dotenv import load_dotenv
# 1. Environment Load (Sabse Pehle)
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

# Import our custom tools
from tools import tools

# --- SETUP: THE BRAIN ---
llm = ChatGroq(
    temperature=0, 
    model_name="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# Brain ko Tools ki jankari do
llm_with_tools = llm.bind_tools(tools)

# --- SYSTEM PROMPT (IDENTITY) ---
# Ye wo "Black Hole Thinking" instruction hai.
sys_msg = """You are 'Project Zero', an elite autonomous coding agent.
Your Goal: Solve the user's coding task completely. 
You have access to a computer. You can browse the web, write files, and execute code.

RULES:
1. **Recursive Fixing:** If execution fails, analyze the error, search for a fix, rewrite the code, and RUN IT AGAIN.
2. **Never Give Up:** Do not ask the user for help unless you are 100% stuck after multiple attempts.
3. **Verification:** Always execute the code to prove it works before finishing.
4. **Environment:** You are running in a Windows environment with Python installed.

Start by planning, then writing code, then executing.
"""

# --- STATE MANAGEMENT ---
# AI ki memory (Chat history store karne ke liye)
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- NODE 1: THE REASONER ---
# Ye function decide karega ki ab kya karna hai
def reasoner(state: AgentState):
    return {"messages": [llm_with_tools.invoke([SystemMessage(content=sys_msg)] + state["messages"])]}

# --- GRAPH CONSTRUCTION (The Loop) ---
builder = StateGraph(AgentState)

# 1. Add Nodes
builder.add_node("reasoner", reasoner)
builder.add_node("tools", ToolNode(tools)) # Ye automatic node hai jo tools run karta hai

# 2. Add Edges (Logic Flow)
builder.set_entry_point("reasoner")

# Logic: Agar LLM ne tool call kiya -> Tool Node pe jao. Nahi to -> End karo.
builder.add_conditional_edges(
    "reasoner",
    tools_condition,
)

# Logic: Tool chalne ke wapas Reasoner ke paas jao (Result dekhne ke liye)
builder.add_edge("tools", "reasoner")

# Compile the Brain
app = builder.compile()

# --- MAIN EXECUTION LOOP ---
if __name__ == "__main__":
    print("🤖 PROJECT ZERO: ONLINE (Type 'quit' to exit)")
    print("---------------------------------------------")
    
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["quit", "exit"]:
            break
        
        # Start the Agent
        initial_state = {"messages": [HumanMessage(content=user_input)]}
        print("\n⚙️  Processing... (This might take time)\n")
        
        # Stream the thought process
        for event in app.stream(initial_state):
            for key, value in event.items():
                if key == "reasoner":
                    # AI ka Last message print karo
                    last_msg = value["messages"][-1]
                    print(f"🧠 AI: {last_msg.content}")
                    # Agar tool call hua hai to wo bhi dikhao
                    if last_msg.tool_calls:
                        print(f"🔧 Tool Call: {last_msg.tool_calls[0]['name']}")
                elif key == "tools":
                    # Tool ka output dikhao
                    last_msg = value["messages"][-1]
                    print(f"⚡ Tool Output: {last_msg.content[:200]}...") # Sirf first 200 chars dikhao
        
        print("\n" + "-"*40 + "\n")