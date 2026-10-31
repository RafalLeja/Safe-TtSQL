import psycopg
from psycopg import sql
import pprint
import os
from dotenv import load_dotenv

from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain.agents import create_react_agent

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
    db_uri = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@localhost:5432/northwind"
    db = SQLDatabase.from_uri(db_uri)

    llm = ChatOpenAI(
        base_url="https://services.clarin-pl.eu/api/v1/oapi",
        api_key=os.getenv("OPENAI_API_KEY"),
        model="deepseek-v4-flash",
        temperature=0
    )

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")
    system_message = prompt_template.format(dialect=db.dialect)

    agent_executor = create_react_agent(
        llm, 
        toolkit.get_tools(), 
        state_modifier=system_message
    )

    example_query = "Ile mamy rekordów w bazie?"
    events = agent_executor.stream(
        {"messages": [("user", example_query)]}, 
        stream_mode="values"
    )

    for event in events:
        message = event["messages"][-1]
        print(message.content)

if __name__ == "__main__":
    main()

    ai_agent()