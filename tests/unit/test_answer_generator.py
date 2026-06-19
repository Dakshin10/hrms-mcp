import unittest
from unittest.mock import AsyncMock, MagicMock
from src.services.ai.answer_generator import AnswerGenerator


class TestAnswerGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = AnswerGenerator()
        # Mock groq client
        self.mock_client = MagicMock()
        self.generator.client = self.mock_client

    async def async_test_empty_results(self):
        res = await self.generator.generate_answer("How many tasks?", "--", [])
        self.assertEqual(res, "No data found for your query.")

    def test_empty_results(self):
        import asyncio
        asyncio.run(self.async_test_empty_results())

    async def async_test_single_count_direct_format(self):
        # Questions with various entities
        test_cases = [
            ("how many employees are active?", [{"total_employees": 75}], "There are currently 75 employees in the system."),
            ("how many departments exist?", [{"avg_dep": 6}], "There are currently 6 departments in the system."),
            ("number of tasks assigned", [{"count(*)": 120}], "There are currently 120 tasks in the system."),
            ("how many hours logged", [{"sum_hours": 160}], "There are currently 160 hours in the system."),
            ("rework tasks logged", [{"reworks": 5}], "There are currently 5 reworks in the system.")
        ]
        
        for q, results, expected in test_cases:
            res = await self.generator.generate_answer(q, "--", results)
            self.assertEqual(res, expected)

    def test_single_count_direct_format(self):
        import asyncio
        asyncio.run(self.async_test_single_count_direct_format())

    async def async_test_multi_row_calls_llm(self):
        results = [
            {"employee_id": "EMP1", "name": "Alice"},
            {"employee_id": "EMP2", "name": "Bob"}
        ]
        
        # Mock client chat completions create
        mock_choice = MagicMock()
        mock_choice.message.content = "Here is the list of top performers: Alice and Bob."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        self.mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        res = await self.generator.generate_answer("Who are the performers?", "--", results)
        self.assertEqual(res, "Here is the list of top performers: Alice and Bob.")
        self.mock_client.chat.completions.create.assert_called_once()

    def test_multi_row_calls_llm(self):
        import asyncio
        asyncio.run(self.async_test_multi_row_calls_llm())

    async def async_test_llm_failure_returns_fallback_table(self):
        results = [
            {"employee_id": "EMP1", "name": "Alice"},
            {"employee_id": "EMP2", "name": "Bob"}
        ]
        
        # Trigger an exception from Groq client
        self.mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API offline"))
        
        res = await self.generator.generate_answer("Who are the performers?", "--", results)
        # Verify it formatted as text table
        self.assertIn("employee_id | name", res)
        self.assertIn("EMP1        | Alice", res)
        self.assertIn("EMP2        | Bob", res)

    def test_llm_failure_returns_fallback_table(self):
        import asyncio
        asyncio.run(self.async_test_llm_failure_returns_fallback_table())

    async def async_test_normalize_empty_answer(self):
        # Empty signal words should map to canonical "No data found for your query."
        mock_choice = MagicMock()
        mock_choice.message.content = "Currently no information is available for month 13."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        self.mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        res = await self.generator.generate_answer("utilization for month 13", "--", [{"metric": "utilization"}])
        self.assertEqual(res, "No data found for your query.")

    def test_normalize_empty_answer(self):
        import asyncio
        asyncio.run(self.async_test_normalize_empty_answer())

    async def async_test_none_value_leakage(self):
        # Single row with None/str("None") value should return "No data found for your query."
        res1 = await self.generator.generate_answer("rework count", "--", [{"reworks": None}])
        self.assertEqual(res1, "No data found for your query.")
        
        res2 = await self.generator.generate_answer("rework count", "--", [{"reworks": "None"}])
        self.assertEqual(res2, "No data found for your query.")

        # Multi-column aggregate results formatting when both are non-None
        res3 = await self.generator.generate_answer("show ftr and rework", "--", [{"ftr_rate": 80.5, "rework_rate": 12.3}])
        self.assertEqual(res3, "Current metrics — FTR rate: 80.5%, Rework rate: 12.3%")

    def test_none_value_leakage(self):
        import asyncio
        asyncio.run(self.async_test_none_value_leakage())

    async def async_test_cannot_answer_security(self):
        # CANNOT_ANSWER error rows in SQL results should format to validation failed message
        results = [{"error": "CANNOT_ANSWER", "reason": "Reason: DELETE operation is not permitted"}]
        res = await self.generator.generate_answer("DELETE all employees", "--", results)
        self.assertEqual(res, "Validation failed: Forbidden action. Reason: DELETE operation is not permitted")

    def test_cannot_answer_security(self):
        import asyncio
        asyncio.run(self.async_test_cannot_answer_security())


if __name__ == "__main__":
    unittest.main()
