import asyncio
from flask import Flask, request, jsonify, render_template
from agent import run_query

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Please enter a question"}), 400
    answer = asyncio.run(run_query(question))
    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
