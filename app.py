from flask import Flask, redirect, render_template, request, url_for

from src.agent import ask_agent, create_ai_agent
from src.db_sqllite import (
    create_conversation,
    toggle_pin_conversation,
    delete_conversation,
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

    conversations = get_conversations()
    messages = get_messages(conv_id)
    title = next((row[1] for row in conversations if row[0] == conv_id), f"Konwersacja #{conv_id}")
    return render_template("chat.html", conv_id=conv_id, messages=messages, conversations=conversations, title=title)

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
