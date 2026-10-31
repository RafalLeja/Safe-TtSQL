from urllib.parse import quote_plus

import psycopg
from psycopg import sql
import pprint
import os
from dotenv import load_dotenv

from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

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


def ai_agent():
    encoded_user = quote_plus(DB_USER)
    encoded_password = quote_plus(DB_PASSWORD)
    db_uri = f"postgresql+psycopg://{encoded_user}:{encoded_password}@localhost:5432/northwind"
    db = SQLDatabase.from_uri(db_uri)

    llm = ChatOpenAI(
        base_url="https://services.clarin-pl.eu/api/v1/oapi",
        api_key=os.getenv("OPENAI_API_KEY"),
        model="or-deepseek-v4-flash",
        temperature=0,
    )

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    system_message = f"""
    You are an agent designed to interact with a SQL database.

    The database dialect is {db.dialect}.

    Follow these rules:
    1. First, examine the database structure using the available tools.
    2. Generate correct SQL queries based on the user's question.
    3. Execute the queries using the available SQL tools.
    4. Never execute INSERT, UPDATE, DELETE, DROP or other data-modifying statements.
    5. If a query fails, analyze the error and try to correct it.
    6. Provide the final answer in the same language as the user's question.
    7. Be concise and explain the results clearly.
    """

    agent_executor = create_agent(
        model=llm, tools=toolkit.get_tools(), system_prompt=system_message
    )

    example_queries = [
        "Ile mamy rekordów w bazie?",
        "Wypisz nazwy i ceny 5 najdroższych produktów.",
        "Ilu klientów ma swoją siedzibę w Londynie?",
    ]

    for query in example_queries:
        print(f"\nQuestion: {query} ---")
        events = agent_executor.stream(
            {"messages": [("user", query)]}, stream_mode="values"
        )

        for event in events:
            message = event["messages"][-1]
            if hasattr(message, "content") and message.content:
                print(message.content)


if __name__ == "__main__":
    main()

    ai_agent()

# SQL QUERIES AND CORRECT ANSWERS:

# 1. Ile mamy rekordów w bazie?

# SELECT
#     (SELECT COUNT(*) FROM categories) +
#     (SELECT COUNT(*) FROM customer_customer_demo) +
#     (SELECT COUNT(*) FROM customer_demographics) +
#     (SELECT COUNT(*) FROM customers) +
#     (SELECT COUNT(*) FROM employee_territories) +
#     (SELECT COUNT(*) FROM employees) +
#     (SELECT COUNT(*) FROM order_details) +
#     (SELECT COUNT(*) FROM orders) +
#     (SELECT COUNT(*) FROM products) +
#     (SELECT COUNT(*) FROM region) +
#     (SELECT COUNT(*) FROM shippers) +
#     (SELECT COUNT(*) FROM suppliers) +
#     (SELECT COUNT(*) FROM territories) +
#     (SELECT COUNT(*) FROM us_states) AS wszystkie_rekordy;

# 3362


# 2. Wypisz nazwy i ceny 5 najdroższych produktów.

# SELECT product_name, unit_price
# FROM products
# ORDER BY unit_price DESC
# LIMIT 5;

#       product_name       | unit_price
# -------------------------+------------
#  Côte de Blaye           |      263.5
#  Thüringer Rostbratwurst |     123.79
#  Mishi Kobe Niku         |         97
#  Sir Rodney's Marmalade  |         81
#  Carnarvon Tigers        |       62.5

# 3. Ilu klientów ma swoją siedzibę w Londynie?

# SELECT COUNT(*)
# FROM customers
# WHERE city = 'London';

# 6
