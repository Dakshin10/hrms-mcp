import asyncio
from datetime import datetime
from src.core.logging.logger import logger
from src.agent.graph import agent_workflow

class HRAgent:
    def __init__(self):
        pass

    async def ask(
        self, 
        question: str, 
        history: list[dict] | None = None
    ) -> dict:
        """
        Run the LangGraph workflow agent with conversation history.
        
        Args:
            question: User's natural language question
            history: List of {"role": "user"/"assistant", "content": str} dicts
        
        Returns:
            {
              "answer": str,
              "steps": list[dict],    # Full timeline step log
              "tools_used": list,     # Unique tools called
              "steps_count": int      # Number of tool execution cycles
            }
        """
        import time
        from src.core.config.settings import settings
        from src.services.router.query_router import route_query
        
        if not settings.enable_langgraph:
            logger.info("[Agent] LangGraph is disabled. Routing via QueryRouter.")
            return await route_query(question)

        from src.agent.fast_path import fast_path_router
        
        start_total = time.perf_counter()
        
        # Measure Router latency
        start_router = time.perf_counter()
        fast_path_result = await fast_path_router(question)
        router_dur = time.perf_counter() - start_router
        
        if fast_path_result is not None:
            total_dur = time.perf_counter() - start_total
            t = fast_path_result.get("timings", {})
            t["router"] = router_dur
            t["total"] = total_dur
            
            logger.info("=" * 60)
            logger.info("PERFORMANCE METRICS SUMMARY (FAST PATH ROUTED)")
            logger.info(f"  Router Time:         {t.get('router', 0.0)*1000:.2f} ms")
            logger.info(f"  Tool Execution Time: {t.get('tool', 0.0)*1000:.2f} ms")
            logger.info(f"  Database Time:       {t.get('database', 0.0)*1000:.2f} ms")
            logger.info(f"  Total Request Time:  {t.get('total', 0.0)*1000:.2f} ms")
            logger.info("=" * 60)
            
            # Remove temporary timings key before returning
            fast_path_result.pop("timings", None)
            fast_path_result["steps_count"] = len(fast_path_result.get("tools_used", []))
            return fast_path_result
            
        # Build initial history
        agent_history = []
        if history:
            for msg in history:
                agent_history.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current user query to history
        agent_history.append({
            "role": "user",
            "content": question
        })

        initial_state = {
            "user_query": question,
            "available_tools": [],
            "selected_tool": None,
            "tool_input": None,
            "tool_result": None,
            "final_response": None,
            "steps": [],
            "history": agent_history,
            "timings": {
                "router": router_dur,
                "langgraph": 0.0,
                "groq": 0.0,
                "tool": 0.0,
                "database": 0.0
            }
        }

        try:
            logger.info(f"Running LangGraph agent for query: '{question}'")
            start_graph = time.perf_counter()
            final_state = await agent_workflow.ainvoke(
                initial_state,
                config={"recursion_limit": 25}
            )
            graph_dur = time.perf_counter() - start_graph
            
            answer = final_state.get("final_response") or "I executed the flow but failed to formulate a response."
            steps = final_state.get("steps") or []
            
            # Find unique tools executed
            history_entries = final_state.get("history", [])
            tools_used = list({entry["toolName"] for entry in history_entries if entry.get("role") == "tool" and entry.get("toolName")})
            
            total_dur = time.perf_counter() - start_total
            t = final_state.get("timings", {})
            t["langgraph"] = graph_dur
            t["total"] = total_dur
            
            logger.info("=" * 60)
            logger.info("PERFORMANCE METRICS SUMMARY (LANGGRAPH ROUTED)")
            logger.info(f"  Router Time:         {t.get('router', 0.0)*1000:.2f} ms")
            logger.info(f"  LangGraph Time:      {t.get('langgraph', 0.0)*1000:.2f} ms")
            logger.info(f"  Groq Time:           {t.get('groq', 0.0)*1000:.2f} ms")
            logger.info(f"  Tool Execution Time: {t.get('tool', 0.0)*1000:.2f} ms")
            logger.info(f"  Database Time:       {t.get('database', 0.0)*1000:.2f} ms")
            logger.info(f"  Total Request Time:  {t.get('total', 0.0)*1000:.2f} ms")
            logger.info("=" * 60)
            
            logger.info({
                "event": "agent_execution_complete",
                "tools_used": tools_used,
                "steps_log_count": len(steps)
            })
            
            return {
                "answer": answer,
                "steps": steps,
                "tools_used": tools_used,
                "steps_count": len(tools_used)
            }

        except Exception as e:
            logger.error(f"LangGraph execution exception: {e}", exc_info=True)
            err_msg = str(e)
            if "rate limited" in err_msg.lower():
                answer = "Agent currently rate limited. Please retry in 30 seconds."
            else:
                answer = f"I encountered an error processing your request: {str(e)}. Please try rephrasing."
                
            from datetime import datetime
            return {
                "answer": answer,
                "steps": [
                    {
                        "node": "Error Handler",
                        "message": f"Execution failed: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }
                ],
                "tools_used": [],
                "steps_count": 0
            }
