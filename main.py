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

    example_query = "Ile mamy rekordów w bazie?"
    events = agent_executor.stream(
        {"messages": [("user", example_query)]}, stream_mode="values"
    )

    for event in events:
        message = event["messages"][-1]
        print(message.content)


if __name__ == "__main__":
    main()

    ai_agent()
