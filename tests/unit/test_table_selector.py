import unittest
from src.services.ai.table_selector import TableSelector, TABLE_TOPICS


class TestTableSelector(unittest.TestCase):
    def setUp(self):
        self.selector = TableSelector()

    def test_employee_keywords(self):
        tables = self.selector.select_tables("Find the staff in salary department")
        self.assertIn("employees", tables)
        self.assertEqual(tables[0], "employees")

    def test_timesheet_keywords(self):
        tables = self.selector.select_tables("What is the average workload or utilization?")
        self.assertIn("timesheet_summary", tables)
        self.assertEqual(tables[0], "timesheet_summary")

    def test_task_keywords(self):
        tables = self.selector.select_tables("Show tasks breakdown and actual effort")
        self.assertIn("task_logs", tables)
        self.assertEqual(tables[0], "task_logs")

    def test_multiple_tables_matched(self):
        # Mentions both employees and timesheet summary keywords
        tables = self.selector.select_tables("Get employee names and their workload hours")
        # Both should be present
        self.assertIn("employees", tables)
        self.assertIn("timesheet_summary", tables)

    def test_fallback_no_match(self):
        # Query with no keywords matching the TABLE_TOPICS
        tables = self.selector.select_tables("Some random query about coffee and tea")
        self.assertEqual(sorted(tables), sorted(list(TABLE_TOPICS.keys())))


if __name__ == "__main__":
    unittest.main()
