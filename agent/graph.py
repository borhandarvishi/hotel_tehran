import json
import os
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from agent.agent_prompt import SYSTEM_PROMPT
from agent.config import ENV_FILE, WELCOME_MESSAGE
from agent.schemas import FindHotelInput
from agent.find_hotel import find_hotel


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


@tool(args_schema=FindHotelInput)
def find_hotel_tool(
    hotel_name: str | None = None,
    facilities_preferences: str | None = None,
    address: str | None = None,
    general_preferences: str | None = None,
    location: str | None = None,
    star: int | None = None,
) -> str:
    """Search Tehran hotels by preferences and return up to 5 recommendations."""
    import json

    params = FindHotelInput(
        hotel_name=hotel_name,
        facilities_preferences=facilities_preferences,
        address=address,
        general_preferences=general_preferences,
        location=location,
        star=star,
    )
    result = find_hotel(params)
    return json.dumps(result, ensure_ascii=False)


def _build_llm() -> ChatOpenAI:
    load_dotenv(ENV_FILE)
    model = os.getenv("GENERATION_MODEL", "gpt-4o")
    return ChatOpenAI(model=model, temperature=0.4)


def _agent_node(state: AgentState):
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    llm = _build_llm().bind_tools([find_hotel_tool])
    response = llm.invoke(messages)
    return {"messages": [response]}


def _should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def build_agent():
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode([find_hotel_tool]))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


def new_session_messages() -> list:
    return [
        SystemMessage(content=SYSTEM_PROMPT),
        AIMessage(content=WELCOME_MESSAGE),
    ]


def extract_recommended_hotel_ids(messages: list) -> list[str]:
    """Return hotel IDs from the latest successful find_hotel tool call."""
    last_payload: dict | None = None
    for message in messages:
        if isinstance(message, ToolMessage) and message.name == "find_hotel_tool":
            try:
                last_payload = json.loads(message.content)
            except (json.JSONDecodeError, TypeError):
                continue
    if not last_payload or not last_payload.get("success"):
        return []
    ids = last_payload.get("selected_hotel_ids") or []
    return [str(hid) for hid in ids if hid]


def chat(agent, thread_id: str, user_text: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_text)]},
        config=config,
    )
    messages = result["messages"]
    last_ai = messages[-1]
    content = last_ai.content if hasattr(last_ai, "content") else str(last_ai)
    return {
        "content": content or "",
        "hotel_ids": extract_recommended_hotel_ids(messages),
    }
