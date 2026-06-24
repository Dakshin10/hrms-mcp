import unittest
from unittest.mock import AsyncMock, patch
from src.services.router.query_router import route_query, resolve_table_name


class TestQueryRouter(unittest.TestCase):

    def test_table_alias_resolver(self):
        self.assertEqual(resolve_table_name("employee"), "employees")
        self.assertEqual(resolve_table_name("employee table"), "employees")
        self.assertEqual(resolve_table_name("kpi"), "employee_kpis")
        self.assertEqual(resolve_table_name("timesheets"), "timesheets")
        self.assertIsNone(resolve_table_name("unknown_table"))

    @patch("src.services.router.query_router.list_tables", new_callable=AsyncMock)
    def test_list_tables_routing(self, mock_list):
        mock_list.return_value = [{"name": "employees"}, {"name": "timesheets"}]
        import asyncio
        res = asyncio.run(route_query("list tables"))
        self.assertIsNotNone(res)
        self.assertIn("Database Tables", res["answer"])
        self.assertEqual(res["tools_used"], ["list_tables"])
        mock_list.assert_called_once()

    @patch("src.services.router.query_router.describe_table", new_callable=AsyncMock)
    @patch("src.services.router.query_router.list_tables", new_callable=AsyncMock)
    def test_describe_table_routing(self, mock_list, mock_describe):
        mock_list.return_value = [{"name": "employees"}]
        mock_describe.return_value = [{"cid": 0, "name": "employee_id", "type": "TEXT"}]
        import asyncio
        res = asyncio.run(route_query("describe table employee"))
        self.assertIsNotNone(res)
        self.assertIn("Table Schema: employees", res["answer"])
        self.assertEqual(res["tools_used"], ["describe_table"])
        mock_describe.assert_called_once_with(table_name="employees")

    @patch("src.services.router.query_router.get_employee_by_id", new_callable=AsyncMock)
    def test_get_employee_by_id_routing(self, mock_get):
        mock_get.return_value = {"employee_id": "EMP0001", "first_name": "John", "last_name": "Doe"}
        import asyncio
        res = asyncio.run(route_query("find EMP0001"))
        self.assertIsNotNone(res)
        self.assertIn("Employee Details for EMP0001", res["answer"])
        self.assertEqual(res["tools_used"], ["get_employee_by_id"])
        mock_get.assert_called_once_with(employee_id="EMP0001")

    @patch("src.services.router.query_router.get_employees_by_department", new_callable=AsyncMock)
    def test_get_employees_by_department_routing(self, mock_dept):
        mock_dept.return_value = [{"employee_id": "EMP0001", "first_name": "John", "department": "Engineering"}]
        import asyncio
        res = asyncio.run(route_query("employees in Engineering department"))
        self.assertIsNotNone(res)
        self.assertIn("Employees in Engineering Department", res["answer"])
        self.assertEqual(res["tools_used"], ["get_employees_by_department"])
        mock_dept.assert_called_once_with(department="Engineering")

    @patch("src.services.router.query_router.execute_sql", new_callable=AsyncMock)
    @patch("src.services.router.query_router.list_tables", new_callable=AsyncMock)
    def test_smart_sql_routing(self, mock_list, mock_exec):
        mock_list.return_value = [{"name": "employee_kpis"}]
        mock_exec.return_value = [{"kpi_id": 1, "employee_id": "EMP0001"}]
        import asyncio
        res = asyncio.run(route_query("display all data from employee_kpis"))
        self.assertIsNotNone(res)
        self.assertIn("Query Result", res["answer"])
        self.assertEqual(res["tools_used"], ["execute_sql"])
        mock_exec.assert_called_once_with(sql="SELECT * FROM employee_kpis LIMIT 100;")

    @patch("src.services.router.query_router.execute_sql", new_callable=AsyncMock)
    def test_query_template_avg_salary(self, mock_exec):
        mock_exec.return_value = [{"avg_salary": 500000}]
        import asyncio
        res = asyncio.run(route_query("what is the average salary?"))
        self.assertIsNotNone(res)
        self.assertEqual(res["tools_used"], ["execute_sql"])
        mock_exec.assert_called_once_with(sql="SELECT AVG(annual_salary_inr) as avg_salary FROM employees;")

    @patch("src.services.router.query_router.execute_sql", new_callable=AsyncMock)
    @patch("src.services.router.query_router.list_tables", new_callable=AsyncMock)
    def test_query_template_top_n(self, mock_list, mock_exec):
        mock_list.return_value = [{"name": "employees"}]
        mock_exec.return_value = [{"employee_id": "EMP1", "annual_salary_inr": 1000000}]
        import asyncio
        res = asyncio.run(route_query("top 10 employees by salary"))
        self.assertIsNotNone(res)
        self.assertEqual(res["tools_used"], ["execute_sql"])
        mock_exec.assert_called_once_with(sql="SELECT * FROM employees ORDER BY annual_salary_inr DESC LIMIT 10;")

    @patch("src.services.router.query_router.ask_database", new_callable=AsyncMock)
    def test_unmatched_fallback(self, mock_ask):
        mock_ask.return_value = "Result from Groq pipeline"
        import asyncio
        res = asyncio.run(route_query("what is the department with the highest average kpi score in 2025?"))
        self.assertIsNotNone(res)
        self.assertEqual(res["tools_used"], ["ask_database"])
        mock_ask.assert_called_once_with(question="what is the department with the highest average kpi score in 2025?")


if __name__ == "__main__":
    unittest.main()
