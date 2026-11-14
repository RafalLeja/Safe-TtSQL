from collections.abc import Generator
from itertools import chain
from urllib.parse import quote_plus

from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI

from src.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, OPENAI_API_KEY
from src.tools import execute_sql, get_schema, list_tables


def get_db_uri() -> str:
    encoded_user = quote_plus(DB_USER)
    encoded_password = quote_plus(DB_PASSWORD)
    return f"postgresql+psycopg://{encoded_user}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def create_ai_agent():
    return create_agent(
        model=ChatOpenAI(
            base_url="https://services.clarin-pl.eu/api/v1/oapi",
            api_key=OPENAI_API_KEY,
            model="or-deepseek-v4-flash",
            temperature=0,
        ),
        tools=[list_tables, get_schema, execute_sql],
        system_prompt="""
        You are a helpful assistant that can answer questions
        about the database. You have access to the following tools:
        list_tables, 
        get_schema, 
        execute_sql. 
        Use them to answer questions.
        """,
        debug=False,
    )


def run_queries(agent_executor, queries: list[str]):
    for query in queries:
        print("\n" + "=" * 80)
        print(f"\nQuestion: {query}")
        try:
            inputs = {"messages": [{"role": "user", "content": query}]}
            for chunk in agent_executor.stream(inputs, stream_mode="messages"):
                message, metadata = chunk
                if isinstance(message, AIMessageChunk):
                    print(message.text, end="", flush=True)
        except Exception as e:
            print(f"Error while agent execution: {e}")


def ask_agent(
    agent_executor, query: str, context: list[tuple[str, str]] | None = None
) -> str:
    messages = (
        list(
            chain.from_iterable(
                [
                    [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response},
                    ]
                    for prompt, response in context
                ]
            )
        )
        if context is not None
        else []
    )

    messages.append({"role": "user", "content": query})

    inputs = {"messages": messages}

    try:
        result = agent_executor.invoke(inputs)

        if "messages" in result:
            sql_queries = []
            for msg in result["messages"][len(messages) :]:
                if getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        if tc["name"] == "execute_sql":
                            sql = tc["args"].get("query")
                            if sql:
                                sql_queries.append(sql)

            answer = result["messages"][-1].content

            if sql_queries:
                formatted_sql = "\n\n".join(
                    f"```sql\n{q.strip()}\n```" for q in sql_queries
                )
                return f"{answer}\n\n---\n**Wykonane zapytanie SQL:**\n{formatted_sql}"

        return answer
    except Exception as e:
        return f"Error: {e}"
