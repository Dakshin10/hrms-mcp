from langgraph.graph import StateGraph, END
from src.agent.state import AgentState
from src.agent.nodes import discover_tools_node, select_tool_node, execute_tool_node, generate_response_node
from src.agent.router import route_next

def create_agent_graph():
    # Define the graph with AgentState schema
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("discover", discover_tools_node)
    workflow.add_node("select", select_tool_node)
    workflow.add_node("execute", execute_tool_node)
    workflow.add_node("respond", generate_response_node)
    
    # Set entry point
    workflow.set_entry_point("discover")
    
    # Define transitions
    workflow.add_edge("discover", "select")
    
    # Add conditional transition
    workflow.add_conditional_edges(
        "select",
        route_next,
        {
            "execute": "execute",
            "respond": "respond"
        }
    )
    
    # Edge back from execute to select to support chaining
    workflow.add_edge("execute", "select")
    
    # Edge from respond to END
    workflow.add_edge("respond", END)
    
    return workflow.compile()

# Precompiled singleton workflow
agent_workflow = create_agent_graph()
