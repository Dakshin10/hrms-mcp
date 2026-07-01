import json
import inspect
from datetime import datetime
from typing import Dict, Any, List, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.core.config.settings import settings
from src.agent.state import AgentState, AgentStep

# Import all analytical and database tools
from src.tools.db_tools import list_tables, describe_table, execute_sql, ask_database, cache_stats
from src.tools.employee_tools import get_all_employees, get_employee_by_id, get_employees_by_department, search_employees
from src.tools.hr_tools import hr_insights
from src.tools.sheet_tools import connect_google_sheet, fetch_sheet_data
from src.tools.timesheet_tools import load_timesheets

TOOL_REGISTRY = {
    "list_tables": list_tables,
    "describe_table": describe_table,
    "execute_sql": execute_sql,
    "ask_database": ask_database,
    "cache_stats": cache_stats,
    "get_all_employees": get_all_employees,
    "get_employee_by_id": get_employee_by_id,
    "get_employees_by_department": get_employees_by_department,
    "search_employees": search_employees,
    "hr_insights": hr_insights,
    "connect_google_sheet": connect_google_sheet,
    "fetch_sheet_data": fetch_sheet_data,
    "load_timesheets": load_timesheets,
}

def get_llm():
    return ChatGroq(
        model=settings.groq_model or "openai/gpt-oss-120b",
        api_key=settings.groq_api_key,
        temperature=0.1
    )

async def discover_tools_node(state: AgentState) -> dict:
    steps = list(state.get("steps", []))
    steps.append({
        "node": "Discovery Node",
        "message": "Initiating tool discovery on python MCP server...",
        "timestamp": datetime.now().isoformat()
    })
    
    discovered = []
    for name, func in TOOL_REGISTRY.items():
        sig = inspect.signature(func)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == dict:
                param_type = "object"
            elif param.annotation == list:
                param_type = "array"
            
            properties[param_name] = {
                "type": param_type,
                "description": f"Argument: {param_name}"
            }
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        discovered.append({
            "name": name,
            "description": func.__doc__.strip() if func.__doc__ else f"Tool: {name}",
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        })
        
    steps.append({
        "node": "Discovery Node",
        "message": f"Discovered {len(discovered)} active Python MCP tools.",
        "timestamp": datetime.now().isoformat(),
        "data": {"count": len(discovered), "tools": [t["name"] for t in discovered]}
    })
    
    return {
        "available_tools": discovered,
        "steps": steps
    }

async def select_tool_node(state: AgentState) -> dict:
    import time
    from src.core.logging.logger import logger
    
    steps = list(state.get("steps", []))
    steps.append({
        "node": "Tool Selection Node",
        "message": "Analyzing user query and history to determine next tool...",
        "timestamp": datetime.now().isoformat()
    })
    
    # 1. Stop Loop iteration if threshold reached
    exec_steps_count = sum(1 for s in steps if s.get("node") == "Tool Execution Node" and "completed successfully" in s.get("message", ""))
    if exec_steps_count >= 3:
        logger.warning("[Nodes] LangGraph execution limit of 3 tools reached. Ending loop.")
        steps.append({
            "node": "Tool Selection Node",
            "message": "LangGraph execution limit (3 tools) reached. Forcing response generation to prevent loops.",
            "timestamp": datetime.now().isoformat()
        })
        return {
            "selected_tool": None,
            "steps": steps
        }
    
    tools_context = []
    for t in state.get("available_tools", []):
        tools_context.append({
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"]
        })
        
    system_prompt = f"""You are the Tool Selection Node of a LangGraph agent.
Analyze the user's query and history, then determine the best tool to run next.
You can choose to call a tool, or decide that no further tools are needed and go to response generation.

Available MCP Tools:
{json.dumps(tools_context, indent=2)}

Active conversation history so far:
{json.dumps(state.get("history", []), indent=2)}

Query: "{state.get("user_query")}"

Rules:
1. Select the single most relevant tool to call.
2. Carefully parse argument values from the query based on the tool's inputSchema.
3. If no tool is needed (for example, because you already have the tool execution output/result in the history above that fully answers the query), you MUST set "selected_tool" to null.
4. Output a valid JSON object ONLY matching this schema:
{{
  "reasoning": "Detailed agent chain-of-thought explaining why this tool fits, or why no more tools are needed",
  "selected_tool": null or "name_of_tool",
  "tool_input": {{ ...arguments... }}
}}

CRITICAL RULE FOR AVOIDING INFINITE LOOPS:
If a tool has already been executed (its name and result are in the conversation history above) and you have received its output, DO NOT call it again with the same arguments. If the tool execution result is already present in the history, set "selected_tool" to null so that we can proceed to the final response.
"""
    
    messages = [
        SystemMessage(content=system_prompt)
    ]
    
    for msg in state.get("history", []):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "tool":
            tool_name = msg.get("toolName", "unknown")
            messages.append(SystemMessage(content=f"Tool '{tool_name}' execution output: {content}"))
            
    start_groq = time.perf_counter()
    try:
        llm = get_llm()
        structured_llm = llm.bind(response_format={"type": "json_object"})
        response = await structured_llm.ainvoke(messages)
        groq_dur = time.perf_counter() - start_groq
        
        timings = dict(state.get("timings", {}))
        timings["groq"] = timings.get("groq", 0.0) + groq_dur
        
        parsed = json.loads(response.content)
        selected = parsed.get("selected_tool")
        if selected == "null" or not selected:
            selected = None
            
        tool_input = parsed.get("tool_input", {})
        reasoning = parsed.get("reasoning", "No reasoning provided.")
        
        steps.append({
            "node": "Tool Selection Node",
            "message": f"Agent reasoning: {reasoning}",
            "timestamp": datetime.now().isoformat(),
            "data": {"selected_tool": selected, "tool_input": tool_input}
        })
        
        return {
            "selected_tool": selected,
            "tool_input": tool_input,
            "steps": steps,
            "timings": timings
        }
    except Exception as e:
        groq_dur = time.perf_counter() - start_groq
        err_msg = str(e).lower()
        if "429" in err_msg or "rate_limit" in err_msg or "rate limit" in err_msg:
            raise ValueError("Agent currently rate limited. Please retry in 30 seconds.")
            
        steps.append({
            "node": "Tool Selection Node",
            "message": f"LLM tool selection failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })
        return {
            "selected_tool": None,
            "steps": steps
        }

async def execute_tool_node(state: AgentState) -> dict:
    import time
    
    steps = list(state.get("steps", []))
    selected_tool = state.get("selected_tool")
    tool_input = state.get("tool_input", {})
    
    if not selected_tool:
        steps.append({
            "node": "Tool Execution Node",
            "message": "No tool selected. Skipping execution.",
            "timestamp": datetime.now().isoformat()
        })
        return {"steps": steps}
        
    steps.append({
        "node": "Tool Execution Node",
        "message": f"Invoking Python tool '{selected_tool}' with parameters: {json.dumps(tool_input)}",
        "timestamp": datetime.now().isoformat()
    })
    
    start_tool = time.perf_counter()
    try:
        func = TOOL_REGISTRY.get(selected_tool)
        if not func:
            raise ValueError(f"Tool {selected_tool} is not registered in TOOL_REGISTRY")
            
        # Call the Python tool directly
        if inspect.iscoroutinefunction(func):
            result = await func(**tool_input)
        else:
            result = func(**tool_input)
            
        tool_dur = time.perf_counter() - start_tool
        
        timings = dict(state.get("timings", {}))
        timings["tool"] = timings.get("tool", 0.0) + tool_dur
        if selected_tool in ("list_tables", "describe_table", "execute_sql", "ask_database"):
            timings["database"] = timings.get("database", 0.0) + tool_dur
            
        steps.append({
            "node": "Tool Execution Node",
            "message": f"Tool '{selected_tool}' completed successfully. Returning result to context.",
            "timestamp": datetime.now().isoformat(),
            "data": {"success": True}
        })
        
        history = list(state.get("history", []))
        history.append({
            "role": "tool",
            "content": result if isinstance(result, str) else json.dumps(result),
            "toolName": selected_tool,
            "toolInput": tool_input
        })
        
        # Insert assistant thought right before tool result to maintain clean history
        history.insert(-1, {
            "role": "assistant",
            "content": f"I will call tool '{selected_tool}' with arguments {json.dumps(tool_input)}"
        })
        
        return {
            "tool_result": result,
            "history": history,
            "steps": steps,
            "selected_tool": None,
            "timings": timings
        }
    except Exception as e:
        tool_dur = time.perf_counter() - start_tool
        steps.append({
            "node": "Tool Execution Node",
            "message": f"Execution failed for tool '{selected_tool}': {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "data": {"success": False, "error": str(e)}
        })
        return {
            "tool_result": {"error": str(e), "success": False},
            "steps": steps,
            "selected_tool": None
        }

async def generate_response_node(state: AgentState) -> dict:
    import time
    
    steps = list(state.get("steps", []))
    steps.append({
        "node": "Response Generation Node",
        "message": "Formulating final response from analysis history...",
        "timestamp": datetime.now().isoformat()
    })
    
    system_prompt = f"""You are the Response Generation Node of a LangGraph agent.
Review the user's initial query, the log of tools executed, and the results returned.
Formulate a concise, professional, human-readable response that answers the user's request.

Rules:
1. RENDER the result using clean GitHub Markdown formatting.
2. If the data is tabular, display it in a clean markdown table.
3. Be concise and precise. No fluff.
4. If there were errors, explain them clearly.

Analysis History:
{json.dumps(state.get("history", []), indent=2)}
"""
    
    messages = [
        SystemMessage(content=system_prompt)
    ]
    
    # Format conversation history cleanly into message objects
    for msg in state.get("history", []):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "tool":
            tool_name = msg.get("toolName", "unknown")
            messages.append(SystemMessage(content=f"Tool '{tool_name}' execution output: {content}"))
            
    start_groq = time.perf_counter()
    try:
        llm = get_llm()
        response = await llm.ainvoke(messages)
        groq_dur = time.perf_counter() - start_groq
        
        timings = dict(state.get("timings", {}))
        timings["groq"] = timings.get("groq", 0.0) + groq_dur
        
        steps.append({
            "node": "Response Generation Node",
            "message": "Agent reasoning complete. Formulated final response.",
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "final_response": response.content,
            "steps": steps,
            "timings": timings
        }
    except Exception as e:
        groq_dur = time.perf_counter() - start_groq
        err_msg = str(e).lower()
        if "429" in err_msg or "rate_limit" in err_msg or "rate limit" in err_msg:
            raise ValueError("Agent currently rate limited. Please retry in 30 seconds.")
            
        error_msg = f"Failed to generate summary response: {str(e)}"
        steps.append({
            "node": "Response Generation Node",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        })
        return {
            "final_response": f"I executed the required tools, but failed to format the output. Raw data: {json.dumps(state.get('tool_result'))}",
            "steps": steps
        }
