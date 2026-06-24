from src.agent.state import AgentState

def route_next(state: AgentState) -> str:
    """
    Route based on tool selection: if a tool name is set in selected_tool,
    go to execution node; otherwise, go to response generation.
    """
    if state.get("selected_tool"):
        return "execute"
    return "respond"
