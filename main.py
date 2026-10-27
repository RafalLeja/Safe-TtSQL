import psycopg
from psycopg import sql
import pprint
import os
from dotenv import load_dotenv

load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# TODO:
# 1. Połączyć model z bazą
# 2. Wymyślić 3 przykładowe zapytania do bazy danych
# 3. (opcjonalnie) Walidacja wygenerowanego SQL-a


def main():
    conn_string = (
        f"host=localhost dbname=northwind user={DB_USER} password={DB_PASSWORD}"
    )
    conn = psycopg.connect(conn_string)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    table_names = [row[0] for row in cursor.fetchall()]

    counts = {}
    for table_name in table_names:
        cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name))
        )
        counts[table_name] = cursor.fetchone()[0]

    pprint.pprint(counts)


if __name__ == "__main__":
    main()
