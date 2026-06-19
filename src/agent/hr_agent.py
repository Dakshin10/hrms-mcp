from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.config.settings import settings
from src.core.logging.logger import logger

SYSTEM_PROMPT = """
You are an intelligent HR Analytics Assistant for Minori HRMS.
You have access to tools that query employee, KPI, timesheet, 
FTR, ETA, and performance data.

Guidelines:
- For complex questions, break them into multiple tool calls
- Always use hr_insights() for performance/KPI questions
- Use ask_database() for specific SQL-level questions
- Combine results across tool calls to give a complete answer
- Be concise and business-focused in your final answer
- Never expose raw SQL or JSON to the user
- If data is unavailable, say so clearly

You understand these HR terms:
- FTR (First Time Right): task quality metric, higher is better
- ETA adherence: how well employees meet time estimates
- Achievement %: overall KPI score per employee
- Rework: tasks returned for correction, lower is better
"""

class HRAgent:
    def __init__(self):
        self.model = ChatGroq(
            model=settings.groq_model or "llama-3.3-70b-versatile",
            api_key=settings.groq_api_key,
            temperature=0
        )
        self.mcp_config = {
            "hrms": {
                "command": "venv/Scripts/python",   
                # Windows: venv/Scripts/python
                # Linux/Mac: venv/bin/python
                "args": ["-m", "src.mcp_server.server"],
                "transport": "stdio"
            }
        }
        self._agent = None

    async def _get_agent(self):
        """Lazy-initialize agent with live MCP tools."""
        if self._agent is None:
            async with MultiServerMCPClient(self.mcp_config) as client:
                tools = await client.get_tools()
                logger.info(f"Loaded {len(tools)} MCP tools into agent")
                self._agent = create_react_agent(
                    self.model,
                    tools,
                    state_modifier=SYSTEM_PROMPT
                )
        return self._agent

    async def ask(
        self, 
        question: str, 
        history: list[dict] | None = None
    ) -> dict:
        """
        Run the agent with optional conversation history.
        
        Args:
            question: User's natural language question
            history: List of {"role": "user"/"assistant", 
                              "content": str} dicts
        
        Returns:
            {
              "answer": str,
              "steps": int,       # number of tool calls made
              "tools_used": list  # which tools were called
            }
        """
        messages = []
        
        # Inject conversation history
        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(
                        SystemMessage(content=msg["content"])
                    )
        
        messages.append(HumanMessage(content=question))

        try:
            async with MultiServerMCPClient(self.mcp_config) as client:
                tools = await client.get_tools()
                agent = create_react_agent(
                    self.model,
                    tools,
                    state_modifier=SYSTEM_PROMPT
                )
                
                result = await agent.ainvoke({"messages": messages})
                
                # Extract final answer
                final_message = result["messages"][-1]
                answer = final_message.content
                
                # Count tool calls made
                tool_calls = [
                    m for m in result["messages"]
                    if hasattr(m, "name") and m.name is not None
                ]
                tools_used = list({m.name for m in tool_calls})
                
                logger.info({
                    "event": "agent_response",
                    "question": question,
                    "steps": len(tool_calls),
                    "tools_used": tools_used
                })
                
                return {
                    "answer": answer,
                    "steps": len(tool_calls),
                    "tools_used": tools_used
                }

        except Exception as e:
            logger.error(f"Agent error: {e}")
            return {
                "answer": "I encountered an error processing your request. Please try rephrasing.",
                "steps": 0,
                "tools_used": []
            }
