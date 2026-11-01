import psycopg
from psycopg import sql
from src.config import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

CONN_STRING = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"


def get_table_counts() -> dict[str, int]:
    counts = {}
    with psycopg.connect(CONN_STRING) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            table_names = [row[0] for row in cursor.fetchall()]

            for table_name in table_names:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier(table_name)
                    )
                )
                counts[table_name] = cursor.fetchone()[0]

    return counts


def get_top_expensive_products(limit: int = 5) -> list[tuple[str, float]]:
    with psycopg.connect(CONN_STRING) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT product_name, unit_price
                FROM products
                ORDER BY unit_price DESC
                LIMIT %s;
                """,
                (limit,),
            )
            return cursor.fetchall()


def get_customers_count_by_city(city: str = "London") -> int:
    with psycopg.connect(CONN_STRING) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM customers
                WHERE city = %s;
                """,
                (city,),
            )
            return cursor.fetchone()[0]
