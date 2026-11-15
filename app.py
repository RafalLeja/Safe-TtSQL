import json
import time
from html import escape

import nh3
from flask import (
    Flask,
    Response,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from markdown_it import MarkdownIt
from markupsafe import Markup
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from src.agent import ask_agent, ask_agent_stream, create_ai_agent
from src.db_sqllite import (
    create_conversation,
    delete_conversation,
    get_conversations,
    get_messages,
    init_db,
    save_message,
    toggle_pin_conversation,
)

app = Flask(__name__)
agent = create_ai_agent()


def _conversation_title(query: str) -> str:
    """Derive a short conversation title from the first words of a query."""
    words = query.split()
    title = " ".join(words[:5])
    if len(words) > 5:
        title += "..."
    return title


def _sse_response(generator) -> Response:
    return Response(
        stream_with_context(generator),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _stream_agent_events(conv_id: int, user_query: str, context_messages: list):
    """SSE generator shared by /chat/<id>/stream and /new_chat/stream:
    streams agent events, saves the message on completion."""
    buffer: list[str] = []
    answer = None
    last_beat = time.time()
    try:
        for event in ask_agent_stream(agent, user_query, context=context_messages):
            if event.get("type") == "token":
                buffer.append(event["text"])
            elif event.get("type") == "done":
                answer = event["answer"]
                # Reuse the safe server-side markdown pipeline
                # (markdown-it + nh3 + Pygments) for the final render.
                event["html"] = str(render_markdown(answer))
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            # Comment-line heartbeat keeps proxies from closing idle
            # connections during long tool executions.
            now = time.time()
            if now - last_beat >= 15:
                yield ": keep-alive\n\n"
                last_beat = now
        if answer is None:
            answer = "".join(buffer)
        save_message(conv_id, user_query, answer)
    except Exception as e:  # generator-level safety net
        yield f"data: {json.dumps({'type': 'error', 'text': f'Error: {e}'}, ensure_ascii=False)}\n\n"


_pygments_formatter = HtmlFormatter(nowrap=True, noclasses=False, style="github-dark")


def _highlight_code(code: str, lang: str, attrs: str) -> str:
    """Server-side syntax highlighting for fenced code blocks."""
    try:
        lexer = get_lexer_by_name(lang or "text")
    except ClassNotFound:
        return escape(code)
    return pygments_highlight(code, lexer, _pygments_formatter)


md = MarkdownIt("commonmark", options_update={"highlight": _highlight_code}).enable(
    "table"
)


def render_markdown(text: str) -> Markup:
    """Convert markdown to sanitized HTML safe to insert into the template."""
    return Markup(
        nh3.clean(
            md.render(text),
            attributes={"code": {"class"}, "span": {"class"}},
        )
    )


@app.route("/", methods=["GET"])
def index():
    conversations = get_conversations()
    return render_template("index.html", conversations=conversations)


@app.route("/new_chat", methods=["POST"])
def new_chat():
    user_query = request.form.get("query")
    if not user_query:
        return redirect(url_for("index"))

    conv_id = create_conversation(_conversation_title(user_query))

    ai_response = ask_agent(agent, user_query)
    save_message(conv_id, user_query, ai_response)

    return redirect(url_for("chat", conv_id=conv_id))


@app.route("/new_chat/stream", methods=["POST"])
def new_chat_stream():
    """SSE variant of new_chat: creates the conversation immediately,
    then streams the first answer."""
    user_query = (request.form.get("query") or "").strip()
    if not user_query:
        return redirect(url_for("index"))

    conv_id = create_conversation(_conversation_title(user_query))

    def generate():
        # Tell the frontend where this conversation lives so it can
        # redirect once the answer is done.
        yield f"data: {json.dumps({'type': 'start', 'conv_id': conv_id}, ensure_ascii=False)}\n\n"
        yield from _stream_agent_events(conv_id, user_query, [])

    return _sse_response(generate())


@app.route("/chat/<int:conv_id>", methods=["GET", "POST"])
def chat(conv_id):
    if request.method == "POST":
        user_query = request.form.get("query")
        if user_query:
            context_messages = get_messages(conv_id)
            ai_response = ask_agent(agent, user_query, context=context_messages)
            save_message(conv_id, user_query, ai_response)
        return redirect(url_for("chat", conv_id=conv_id))

    conversations = get_conversations()
    messages = [
        (prompt, render_markdown(response))
        for prompt, response in get_messages(conv_id)
    ]
    title = next(
        (row[1] for row in conversations if row[0] == conv_id),
        f"Konwersacja #{conv_id}",
    )
    return render_template(
        "chat.html",
        conv_id=conv_id,
        messages=messages,
        conversations=conversations,
        title=title,
    )


@app.route("/chat/<int:conv_id>/stream", methods=["POST"])
def chat_stream(conv_id):
    """SSE endpoint: streams agent answer tokens to the UI.

    The frontend POSTs here with the same form data as /chat/<id>.
    """
    user_query = (request.form.get("query") or "").strip()
    if not user_query:
        return redirect(url_for("chat", conv_id=conv_id))

    context_messages = get_messages(conv_id)
    return _sse_response(_stream_agent_events(conv_id, user_query, context_messages))


@app.route("/pin/<int:conv_id>", methods=["POST"])
def pin_chat(conv_id):
    toggle_pin_conversation(conv_id)
    return redirect(request.referrer or url_for("index"))


@app.route("/delete/<int:conv_id>", methods=["POST"])
def delete_chat(conv_id):
    delete_conversation(conv_id)
    if request.referrer and f"/chat/{conv_id}" in request.referrer:
        return redirect(url_for("index"))
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
