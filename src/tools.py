from langchain.tools import tool

from src.database import get_connection
from src.validator import validate_sql_query


@tool
def list_tables() -> list[str]:
    """List tables in the public schema."""
    print("\n")
    print("Listing tables in the public schema...")
    with get_connection().cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return [row[0] for row in cur.fetchall()]


@tool
def get_schema(table_names: list[str]) -> dict:
    """Get columns and data types for the specified tables."""
    print("\n")
    print(f"Getting schema for tables: {table_names}")
    schema = {}

    with get_connection().cursor() as cur:
        for table in table_names:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position
            """,
                (table,),
            )

            schema[table] = [
                {
                    "column": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                }
                for row in cur.fetchall()
            ]

    return schema


@tool
def execute_sql(query: str) -> dict:
    """Execute a read-only SQL query and return at most 100 rows."""
    print("\n")
    print(f"Executing query: \n{query}")

    validation_result = validate_sql_query(query)
    if "error" in validation_result:
        return validation_result

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(query)

                columns = [desc.name for desc in cur.description]
                rows = cur.fetchmany(101)

                return {
                    "columns": columns,
                    "rows": [dict(zip(columns, row)) for row in rows[:100]],
                    "truncated": len(rows) > 100,
                }

        except Exception as exc:
            conn.rollback()
            return {"error": str(exc)}
