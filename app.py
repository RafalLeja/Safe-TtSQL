from flask import Flask, redirect, render_template, request, url_for

from src.agent import ask_agent, create_ai_agent
from src.db_sqllite import (
    create_conversation,
    get_conversations,
    get_messages,
    init_db,
    save_message,
)

app = Flask(__name__)
agent = create_ai_agent()


@app.route("/", methods=["GET"])
def index():
    conversations = get_conversations()
    return render_template("index.html", conversations=conversations)


@app.route("/new_chat", methods=["POST"])
def new_chat():
    user_query = request.form.get("query")
    if not user_query:
        return redirect(url_for("index"))

    words = user_query.split()
    title = " ".join(words[:5])
    if len(words) > 5:
        title += "..."

    conv_id = create_conversation(title)

    ai_response = ask_agent(agent, user_query)
    save_message(conv_id, user_query, ai_response)

    return redirect(url_for("chat", conv_id=conv_id))


@app.route("/chat/<int:conv_id>", methods=["GET", "POST"])
def chat(conv_id):
    if request.method == "POST":
        user_query = request.form.get("query")
        if user_query:
            context_messages = get_messages(conv_id)
            ai_response = ask_agent(agent, user_query, context=context_messages)
            save_message(conv_id, user_query, ai_response)
        return redirect(url_for("chat", conv_id=conv_id))

    messages = get_messages(conv_id)
    return render_template("chat.html", conv_id=conv_id, messages=messages)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
