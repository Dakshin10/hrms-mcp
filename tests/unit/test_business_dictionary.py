import unittest
from src.services.ai.business_dictionary import get_term_definitions, resolve_aliases


class TestBusinessDictionary(unittest.TestCase):
    def test_get_term_definitions_matched(self):
        result = get_term_definitions("What is the ftr of each department?")
        self.assertIn("First Time Right", result)

    def test_get_term_definitions_unmatched(self):
        result = get_term_definitions("Show me all employees")
        self.assertEqual(result, "")

    def test_resolve_aliases(self):
        result = resolve_aliases("Who are the top performers?")
        self.assertIn("achievement_percentage", result)

    def test_get_term_definitions_multiple(self):
        result = get_term_definitions("Show eta and ftr breakdown")
        self.assertIn("First Time Right", result)
        self.assertIn("Estimated Time of Arrival", result)


if __name__ == "__main__":
    unittest.main()
