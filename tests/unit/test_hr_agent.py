import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.agent.hr_agent import HRAgent
from src.agent.memory import ConversationSession, memory_store


class TestHRAgent(unittest.TestCase):
    def setUp(self):
        from src.core.config.settings import settings
        self._orig_enable = settings.enable_langgraph
        settings.enable_langgraph = True
        memory_store._sessions.clear()

    def tearDown(self):
        from src.core.config.settings import settings
        settings.enable_langgraph = self._orig_enable

    @patch("src.agent.hr_agent.agent_workflow.ainvoke")
    def test_ask_single_tool_call(self, mock_ainvoke):
        # Setup mock return state
        mock_ainvoke.return_value = {
            "final_response": "Final agent answer",
            "steps": [
                {"node": "Discovery Node", "message": "Discovered tools", "timestamp": "2026-06-23T20:00:00Z"},
                {"node": "Tool Execution Node", "message": "Invoking tool 'list_tables'", "timestamp": "2026-06-23T20:00:01Z"}
            ],
            "history": [
                {"role": "user", "content": "What is the employee count?"},
                {"role": "tool", "content": "Tool output", "toolName": "list_tables", "toolInput": {}},
                {"role": "assistant", "content": "Final agent answer"}
            ]
        }

        agent = HRAgent()
        import asyncio
        result = asyncio.run(agent.ask("What is the employee count?"))

        self.assertEqual(result["answer"], "Final agent answer")
        self.assertEqual(result["steps_count"], 1)
        self.assertEqual(result["tools_used"], ["list_tables"])

    @patch("src.agent.hr_agent.agent_workflow.ainvoke")
    def test_history_passed_correctly(self, mock_ainvoke):
        mock_ainvoke.return_value = {
            "final_response": "Hello again",
            "steps": [],
            "history": []
        }

        agent = HRAgent()
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"}
        ]
        
        import asyncio
        asyncio.run(agent.ask("how are you?", history=history))

        # Inspect what messages were passed to ainvoke
        called_args = mock_ainvoke.call_args[0][0]
        self.assertEqual(len(called_args["history"]), 3)
        self.assertEqual(called_args["history"][0]["content"], "hello")
        self.assertEqual(called_args["history"][1]["content"], "hi")
        self.assertEqual(called_args["history"][2]["content"], "how are you?")

    @patch("src.agent.hr_agent.agent_workflow.ainvoke")
    def test_agent_error_graceful_fallback(self, mock_ainvoke):
        mock_ainvoke.side_effect = Exception("LangGraph execution crashed")

        agent = HRAgent()
        import asyncio
        result = asyncio.run(agent.ask("Hello"))

        self.assertIn("error processing your request", result["answer"])
        self.assertEqual(result["steps_count"], 0)
        self.assertEqual(result["tools_used"], [])

    def test_conversation_session_history_cap(self):
        session = ConversationSession(session_id="test_cap")
        # Add 10 turns (20 messages)
        for i in range(10):
            session.add_turn(f"Q{i}", f"A{i}")

        history = session.get_history(last_n_turns=5)
        # 5 turns means at most 10 messages
        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]["content"], "Q5")
        self.assertEqual(history[-1]["content"], "A9")

    def test_memory_store_singleton(self):
        session1 = memory_store.get_or_create("session_123")
        session2 = memory_store.get_or_create("session_123")
        self.assertIs(session1, session2)
        self.assertEqual(memory_store.active_sessions(), 1)

    def test_clear_session(self):
        memory_store.get_or_create("session_abc")
        self.assertEqual(memory_store.active_sessions(), 1)
        memory_store.clear_session("session_abc")
        self.assertEqual(memory_store.active_sessions(), 0)


if __name__ == "__main__":
    unittest.main()
