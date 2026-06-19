import sqlglot
from sqlglot import exp
from src.core.exceptions.errors import SQLValidationError
from src.core.logging.logger import logger

FORBIDDEN_AST_TYPES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop,
    exp.Alter, exp.Create, exp.TruncateTable, exp.Command
)


class SQLValidator:
    def validate(
        self,
        sql: str,
        known_schema: dict[str, list[dict]] | None = None
    ) -> str:
        """
        Validates a SQL query using sqlglot AST parsing.
        Ensures the query is read-only, checks table/column existence,
        prevents stacked queries, and caps query complexity.
        """
        if not sql or not sql.strip():
            raise SQLValidationError("Empty SQL query")

        try:
            statements = sqlglot.parse(sql, dialect="sqlite")
        except Exception as e:
            logger.error(f"SQL parsing failed: {e}")
            raise SQLValidationError(f"SQL parse error: {e}")

        if not statements:
            raise SQLValidationError("No executable SQL statements found")

        if len(statements) > 1:
            raise SQLValidationError("Stacked queries/multiple statements are not allowed")

        stmt = statements[0]

        # 1. Check for modifying statement types in the AST
        statement_type = type(stmt).__name__
        BLOCKED_STATEMENT_TYPES = {
            "Update", "Delete", "Drop", "Insert", "Create", 
            "AlterTable", "TruncateTable", "Alter"
        }

        if statement_type in BLOCKED_STATEMENT_TYPES:
            raise SQLValidationError(f"Statement type {statement_type} is not permitted")

        # 2. Root statement must be SELECT or WITH
        if not isinstance(stmt, (exp.Select, exp.With)):
            raise SQLValidationError(
                f"Only SELECT or WITH queries are allowed, got: {type(stmt).__name__}"
            )

        # 3. Schema validation (tables and columns)
        if known_schema:
            schema_lower = {
                t_name.lower(): [c["name"].lower() for c in cols]
                for t_name, cols in known_schema.items()
            }
            known_tables = set(schema_lower.keys())

            # Gather all CTE names to exclude them from table existence checks
            cte_aliases = set()
            for cte in stmt.find_all(exp.CTE):
                if cte.alias:
                    cte_aliases.add(cte.alias.lower())

            # Verify table existence
            referenced_tables = []
            for table in stmt.find_all(exp.Table):
                table_name = table.name.lower() if table.name else ""
                if table_name and table_name not in cte_aliases:
                    if table_name not in known_tables:
                        raise SQLValidationError(f"Unknown table referenced: '{table.name}'")
                    referenced_tables.append(table_name)

            # Verify column existence if tables are referenced
            if referenced_tables:
                valid_cols = set()
                for t in referenced_tables:
                    valid_cols.update(schema_lower[t])

                # Allow query-defined select aliases to be referenced elsewhere (e.g. ORDER BY)
                for alias in stmt.find_all(exp.Alias):
                    if alias.alias:
                        valid_cols.add(alias.alias.lower())

                valid_cols.update(cte_aliases)

                # Check each Column node
                for col in stmt.find_all(exp.Column):
                    col_name = col.name.lower()
                    if not col_name or col_name == "*":
                        continue

                    # If qualified, verify against that specific table's schema
                    if col.table:
                        qualifier = col.table.lower()
                        if qualifier in cte_aliases:
                            continue

                        # Resolve table alias to physical table name
                        resolved_table = qualifier
                        parent_select = col.find_ancestor(exp.Select)
                        if parent_select:
                            for source in parent_select.find_all((exp.Table, exp.Join)):
                                if source.alias and source.alias.lower() == qualifier:
                                    if isinstance(source, exp.Table):
                                        resolved_table = source.name.lower()
                                    elif isinstance(source, exp.Join) and isinstance(source.this, exp.Table):
                                        resolved_table = source.this.name.lower()
                                    break

                        if resolved_table in schema_lower:
                            if col_name not in schema_lower[resolved_table]:
                                raise SQLValidationError(
                                    f"Column '{col.name}' does not exist in table '{resolved_table}'"
                                )
                        else:
                            if col_name not in valid_cols:
                                raise SQLValidationError(
                                    f"Column '{col.name}' qualified with '{col.table}' not found in schema"
                                )
                    else:
                        # Unqualified, check if it exists in any referenced table/alias
                        if col_name not in valid_cols:
                            raise SQLValidationError(
                                f"Column '{col.name}' not found in referenced tables: {', '.join(referenced_tables)}"
                            )

        # 4. Complexity checks
        join_count = len(list(stmt.find_all(exp.Join)))
        if join_count > 5:
            raise SQLValidationError(f"Query rejected: {join_count} JOINs detected (limit is 5)")

        all_selects = list(stmt.find_all((exp.Select, exp.Subquery)))
        subquery_count = max(0, len(all_selects) - 1)
        if subquery_count > 3:
            raise SQLValidationError(
                f"Query rejected: {subquery_count} nested queries detected (limit is 3)"
            )

        return sql.strip()
