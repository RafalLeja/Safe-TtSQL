from urllib.parse import quote_plus
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from src.config import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME, OPENAI_API_KEY


def get_db_uri() -> str:
    encoded_user = quote_plus(DB_USER)
    encoded_password = quote_plus(DB_PASSWORD)
    return f"postgresql+psycopg://{encoded_user}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def create_ai_agent():
    db = SQLDatabase.from_uri(get_db_uri())

    llm = ChatOpenAI(
        base_url="https://services.clarin-pl.eu/api/v1/oapi",
        api_key=OPENAI_API_KEY,
        model="or-deepseek-v4-flash",
        temperature=0,
    )

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    agent_executor = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        agent_type="openai-tools",
        verbose=False,
    )

    return agent_executor


def run_queries(agent_executor, queries: list[str]):
    for query in queries:
        print(f"\nQuestion: {query}")
        try:
            response = agent_executor.invoke({"input": query})
            print(response.get("output", "No answer."))
        except Exception as e:
            print(f"Error while agent execution: {e}")
