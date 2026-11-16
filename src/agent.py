from collections.abc import Iterator
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
                message, _metadata = chunk
                if isinstance(message, AIMessageChunk):
                    print(message.text, end="", flush=True)
        except Exception as e:
            print(f"Error while agent execution: {e}")


def _build_messages(
    query: str, context: list[tuple[str, str]] | None = None
) -> list[dict]:
    """Build the message list sent to the agent (history + current query)."""
    messages: list[dict] = []
    if context is not None:
        for prompt, response in context:
            messages.append({"role": "user", "content": prompt})
            messages.append({"role": "assistant", "content": response})
    messages.append({"role": "user", "content": query})
    return messages


def _format_answer(answer: str, sql_queries: list[str]) -> str:
    """Append executed SQL queries to the answer, matching the app's format.

    Queries already present in the answer text are skipped, so the SQL
    is not duplicated.
    """
    missing = [q for q in sql_queries if q.strip() and q.strip() not in answer]
    if missing:
        formatted_sql = "\n\n".join(f"```sql\n{q.strip()}\n```" for q in missing)
        return f"{answer}\n\n---\n**Wykonane zapytanie SQL:**\n{formatted_sql}"
    return answer


def ask_agent(
    agent_executor, query: str, context: list[tuple[str, str]] | None = None
) -> str:
    messages = _build_messages(query, context)
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
            return _format_answer(answer, sql_queries)

        return result["messages"][-1].content

    except Exception as e:
        return f"Error: {e}"


def _update_messages(update) -> list:
    """Messages produced by a finished node, per LangGraph updates mode."""
    if isinstance(update, dict):
        return update.get("messages", [])
    return []


def _status_event(tool_call: dict, sql_queries: list[str]) -> dict:
    """Build a status event for a finished tool call, recording any
    executed SQL query along the way (deduplicated)."""
    sql = tool_call["args"].get("query")
    if tool_call["name"] == "execute_sql" and sql and sql not in sql_queries:
        sql_queries.append(sql)
    detail = sql or ", ".join(f"{k}={v}" for k, v in tool_call["args"].items())
    return {
        "type": "status",
        "tool": tool_call["name"],
        "detail": str(detail)[:200],
    }


def ask_agent_stream(
    agent_executor, query: str, context: list[tuple[str, str]] | None = None
) -> Iterator[dict]:
    """Run the agent, yielding streaming events:

    - {"type": "token",  "text": "..."}                  - answer token
    - {"type": "status", "tool": "...", "detail": "..."} - tool call started
    - {"type": "error",  "text": "..."}
    - {"type": "done",   "answer": "..."}                 - final full answer
    """
    messages = _build_messages(query, context)
    inputs = {"messages": messages}

    # Tokens grouped per LLM call. Intermediate calls (before tool
    # execution) also stream text; only the LAST call is the final answer,
    # so its text is what gets saved / rendered in the done event.
    token_groups: list[list[str]] = []
    current_key: tuple | None = None
    sql_queries: list[str] = []

    try:
        for mode, payload in agent_executor.stream(
            inputs, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                chunk, metadata = payload
                if isinstance(chunk, AIMessageChunk) and chunk.text:
                    key = (
                        metadata.get("langgraph_step"),
                        metadata.get("langgraph_node"),
                    )
                    if key != current_key:
                        current_key = key
                        token_groups.append([])
                    token_groups[-1].append(chunk.text)
                    yield {"type": "token", "text": chunk.text}
            elif mode == "updates":
                # Node finished; surface tool calls as status events.
                for update in payload.values():
                    for msg in _update_messages(update):
                        for tc in getattr(msg, "tool_calls", None) or []:
                            yield _status_event(tc, sql_queries)
    except Exception as e:
        yield {"type": "error", "text": f"Error: {e}"}
        return

    final_text = next(
        (text for group in reversed(token_groups) if (text := "".join(group))),
        "",
    )
    yield {"type": "done", "answer": _format_answer(final_text, sql_queries)}
