import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.agent.hr_agent import HRAgent
from src.agent.conversation_memory import ConversationSession, memory_store


class TestHRAgent(unittest.TestCase):
    def setUp(self):
        memory_store._sessions.clear()

    @patch("src.agent.hr_agent.ChatGroq")
    @patch("src.agent.hr_agent.MultiServerMCPClient")
    @patch("src.agent.hr_agent.create_react_agent")
    def test_ask_single_tool_call(self, mock_create_agent, mock_client_cls, mock_chat_groq):
        # Setup mocks
        mock_client = AsyncMock()
        mock_client.get_tools.return_value = ["mock_tool"]
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # Mock the react agent run
        mock_agent = AsyncMock()
        mock_tool_msg = AIMessage(content="Tool output")
        mock_tool_msg.name = "mock_tool"
        
        mock_final_msg = AIMessage(content="Final agent answer")
        
        mock_agent.ainvoke.return_value = {
            "messages": [
                HumanMessage(content="What is the employee count?"),
                mock_tool_msg,
                mock_final_msg
            ]
        }
        mock_create_agent.return_value = mock_agent

        agent = HRAgent()
        import asyncio
        result = asyncio.run(agent.ask("What is the employee count?"))

        self.assertEqual(result["answer"], "Final agent answer")
        self.assertEqual(result["steps"], 1)
        self.assertEqual(result["tools_used"], ["mock_tool"])

    @patch("src.agent.hr_agent.ChatGroq")
    @patch("src.agent.hr_agent.MultiServerMCPClient")
    @patch("src.agent.hr_agent.create_react_agent")
    def test_history_passed_correctly(self, mock_create_agent, mock_client_cls, mock_chat_groq):
        mock_client = AsyncMock()
        mock_client.get_tools.return_value = []
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {
            "messages": [AIMessage(content="Hello again")]
        }
        mock_create_agent.return_value = mock_agent

        agent = HRAgent()
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"}
        ]
        
        import asyncio
        asyncio.run(agent.ask("how are you?", history=history))

        # Inspect what messages were passed to ainvoke
        called_args = mock_agent.ainvoke.call_args[0][0]
        self.assertEqual(len(called_args["messages"]), 3)
        self.assertIsInstance(called_args["messages"][0], HumanMessage)
        self.assertEqual(called_args["messages"][0].content, "hello")
        self.assertIsInstance(called_args["messages"][1], SystemMessage)
        self.assertEqual(called_args["messages"][1].content, "hi")
        self.assertIsInstance(called_args["messages"][2], HumanMessage)
        self.assertEqual(called_args["messages"][2].content, "how are you?")

    @patch("src.agent.hr_agent.ChatGroq")
    @patch("src.agent.hr_agent.MultiServerMCPClient")
    def test_agent_error_graceful_fallback(self, mock_client_cls, mock_chat_groq):
        mock_client_cls.return_value.__aenter__.side_effect = Exception("MCP Connection failed")

        agent = HRAgent()
        import asyncio
        result = asyncio.run(agent.ask("Hello"))

        self.assertIn("error processing your request", result["answer"])
        self.assertEqual(result["steps"], 0)
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
