import unittest
from src.services.ai.prompt_builder import PromptBuilder


class TestPromptBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = PromptBuilder()

    def test_system_prompt_contains_rules(self):
        sys_prompt = self.builder.get_system_prompt()
        self.assertIn("STRICT RULES:", sys_prompt)
        self.assertIn("SQLite-compatible", sys_prompt)
        self.assertIn("utilization_percentage", sys_prompt)
        self.assertIn("rework_tasks", sys_prompt)

    def test_user_prompt_formatting(self):
        schema_str = "Table: employees\nColumns:\n  - employee_id (TEXT)"
        question = "List all employees"
        
        user_prompt = self.builder.build_user_prompt(question, schema_str)
        self.assertIn("## Available Schema (ONLY use these tables and columns):", user_prompt)
        self.assertIn(schema_str, user_prompt)
        self.assertIn("## User Question:", user_prompt)
        self.assertIn(question, user_prompt)


if __name__ == "__main__":
    unittest.main()
