from src.core.logging.logger import logger
from src.tools.hr.hr_insights_handler import HRInsightsHandler
from src.agent.memory import memory_store

hr_handler = HRInsightsHandler()

async def hr_insights(question: str) -> str | dict:
    """
    Ask natural language HR questions (e.g. top performers, star employees, department rankings, rework rates).
    
    Use this tool when:
    - The question involves HR analytics, performance metrics, department rankings, or timesheet statistics.
    - The question contains keywords related to:
      * top/best/highest/star/performer/leading (top_performers)
      * bottom/low/worst/struggling/underperform/below (bottom_performers)
      * attention/risk/flag/help/needs/concern/problem (employees needing attention)
      * department/team/group/division/which dept/dept rank (department KPI ranking)
      * eta/deadline/late/missed/on time/delay/overdue (timesheet ETA adherence)
      * ftr/rework/first time/quality/redo/correction (First Time Right / rework rates)
      * utilization/billable/hours/capacity/workload (employee utilization)
    
    Routing criteria:
    - Specifically optimized for parsing dates (month/year) and routing to analytical services.
    - Falls back to database ask if no keywords are matched.
    """
    logger.info(f"MCP Tool hr_insights invoked with question: '{question}'")
    try:
        answer = await hr_handler.handle(question)
        return answer
    except Exception as e:
        logger.error(f"Error in hr_insights: {e}")
        return {"error": str(e), "tool": "hr_insights"}


async def hr_agent(question: str, session_id: str) -> dict:
    """
    Multi-step HR agent. Use this for complex questions that require
    combining data from multiple sources or multiple analytical steps.
    
    Examples:
    - Compare all departments and tell me which needs attention
    - Give me a full performance summary for this month  
    - Who should be recognized and who needs coaching?
    - What is the overall health of the organization?
    """
    logger.info(f"MCP Tool hr_agent invoked with question: '{question}', session_id: '{session_id}'")
    try:
        if not session_id or not session_id.strip():
            return {"error": "session_id is required and cannot be empty.", "success": False}

        from src.agent.hr_agent import HRAgent
        session = memory_store.get_or_create(session_id)
        agent = HRAgent()
        
        result = await agent.ask(
            question=question,
            history=session.get_history(last_n_turns=5)
        )
        
        session.add_turn(question, result["answer"])
        
        return {
            "answer": result["answer"],
            "steps": result["steps"],
            "tools_used": result.get("tools_used", [])
        }
    except Exception as e:
        logger.error(f"Error in hr_agent: {e}")
        return {"error": str(e), "success": False}


async def clear_session(session_id: str = "default") -> str | dict:
    """Clears conversation memory for a session."""
    logger.info(f"MCP Tool clear_session invoked for: {session_id}")
    try:
        memory_store.clear_session(session_id)
        return f"Session {session_id} cleared."
    except Exception as e:
        logger.error(f"Error in clear_session: {e}")
        return {"error": str(e), "tool": "clear_session"}


async def health_groq() -> dict:
    """
    Check the health of the Groq LLM service by verifying the API key
    and attempting a lightweight model initialization check.
    """
    import os
    logger.info("MCP Tool health_groq invoked")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "connected": False,
            "message": "GROQ_API_KEY environment variable is not configured."
        }
    
    try:
        from src.services.ai.llm import client
        if not client:
            return {
                "connected": False,
                "message": "Groq client is not initialized."
            }
        
        if hasattr(client, 'api_key') and client.api_key:
            return {
                "connected": True,
                "message": "Groq LLM Service initialized successfully"
            }
        else:
            return {
                "connected": False,
                "message": "Groq client api_key is missing or empty."
            }
    except Exception as e:
        logger.error(f"Groq health check failed: {e}")
        return {
            "connected": False,
            "message": str(e)
        }
