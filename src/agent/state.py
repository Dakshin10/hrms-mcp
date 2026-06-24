from typing import TypedDict, List, Dict, Any, Optional

class AgentStep(TypedDict, total=False):
    node: str
    message: str
    timestamp: str
    data: Optional[Dict[str, Any]]

class AgentState(TypedDict, total=False):
    user_query: str
    available_tools: List[Dict[str, Any]]
    selected_tool: Optional[str]
    tool_input: Optional[Dict[str, Any]]
    tool_result: Optional[Any]
    final_response: Optional[str]
    steps: List[AgentStep]
    history: List[Dict[str, Any]]
