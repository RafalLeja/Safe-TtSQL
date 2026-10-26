import psycopg
import pprint
import os
from dotenv import load_dotenv

load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def main():
    conn_string = (
        f"host=localhost dbname=northwind user={DB_USER} password={DB_PASSWORD}"
    )
    conn = psycopg.connect(conn_string)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers")
    records = cursor.fetchall()
    pprint.pprint(records)


if __name__ == "__main__":
    main()
