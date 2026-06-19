import unittest
from src.services.ai.sql_validator import SQLValidator
from src.core.exceptions.errors import SQLValidationError


class TestSQLValidator(unittest.TestCase):
    def setUp(self):
        self.validator = SQLValidator()
        self.schema = {
            "employees": [
                {"name": "employee_id", "type": "TEXT"},
                {"name": "first_name", "type": "TEXT"},
                {"name": "last_name", "type": "TEXT"},
                {"name": "department", "type": "TEXT"},
                {"name": "salary", "type": "INTEGER"}
            ],
            "timesheet_summary": [
                {"name": "employee_id", "type": "TEXT"},
                {"name": "utilization_percentage", "type": "REAL"},
                {"name": "month", "type": "TEXT"}
            ]
        }

    def test_valid_select(self):
        sql = "SELECT employee_id, first_name FROM employees WHERE salary > 50000"
        result = self.validator.validate(sql, self.schema)
        self.assertEqual(result, sql)

    def test_valid_with_cte(self):
        sql = (
            "WITH high_earners AS ("
            "  SELECT employee_id FROM employees WHERE salary > 80000"
            ") "
            "SELECT * FROM high_earners"
        )
        result = self.validator.validate(sql, self.schema)
        self.assertEqual(result, sql)

    def test_stacked_queries_forbidden(self):
        sql = "SELECT * FROM employees; DROP TABLE employees;"
        with self.assertRaises(SQLValidationError):
            self.validator.validate(sql, self.schema)

    def test_modifying_queries_forbidden(self):
        forbidden_queries = [
            "INSERT INTO employees (employee_id) VALUES ('123')",
            "UPDATE employees SET salary = 100000",
            "DELETE FROM employees WHERE employee_id = '123'",
            "DROP TABLE employees",
            "ALTER TABLE employees ADD COLUMN phone TEXT",
            "CREATE TABLE test (id INT)"
        ]
        for sql in forbidden_queries:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLValidationError):
                    self.validator.validate(sql, self.schema)

    def test_unknown_table_forbidden(self):
        sql = "SELECT * FROM departments"
        with self.assertRaises(SQLValidationError) as ctx:
            self.validator.validate(sql, self.schema)
        self.assertIn("Unknown table referenced", str(ctx.exception))

    def test_unknown_column_forbidden(self):
        sql = "SELECT age FROM employees"
        with self.assertRaises(SQLValidationError) as ctx:
            self.validator.validate(sql, self.schema)
        self.assertIn("Column 'age' not found", str(ctx.exception))

    def test_valid_column_alias(self):
        sql = "SELECT salary * 12 AS annual_salary FROM employees ORDER BY annual_salary DESC"
        result = self.validator.validate(sql, self.schema)
        self.assertEqual(result, sql)

    def test_too_many_joins(self):
        schema = {
            "t1": [{"name": "id"}], "t2": [{"name": "id"}],
            "t3": [{"name": "id"}], "t4": [{"name": "id"}],
            "t5": [{"name": "id"}], "t6": [{"name": "id"}],
            "t7": [{"name": "id"}]
        }
        sql = (
            "SELECT * FROM t1 "
            "JOIN t2 ON t1.id=t2.id "
            "JOIN t3 ON t1.id=t3.id "
            "JOIN t4 ON t1.id=t4.id "
            "JOIN t5 ON t1.id=t5.id "
            "JOIN t6 ON t1.id=t6.id "
            "JOIN t7 ON t1.id=t7.id"
        )
        with self.assertRaises(SQLValidationError) as ctx:
            self.validator.validate(sql, schema)
        self.assertIn("JOINs detected", str(ctx.exception))

    def test_too_many_subqueries(self):
        sql = (
            "SELECT * FROM employees WHERE employee_id IN ("
            "  SELECT employee_id FROM employees WHERE employee_id IN ("
            "    SELECT employee_id FROM employees WHERE employee_id IN ("
            "      SELECT employee_id FROM employees"
            "    )"
            "  )"
            ")"
        )
        with self.assertRaises(SQLValidationError) as ctx:
            self.validator.validate(sql, self.schema)
        self.assertIn("nested queries detected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
