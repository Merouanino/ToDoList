import os

import redis
from flask import Flask, jsonify, request

app = Flask(__name__)

APP_VERSION = os.getenv("APP_VERSION", "dev")
COMMIT_SHA = os.getenv("COMMIT_SHA", "unknown")
MAX_TITLE_LENGTH = 200

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    socket_timeout=1,
    socket_connect_timeout=1,
    decode_responses=True,
)


@app.errorhandler(redis.RedisError)
def storage_unavailable(err):
    return jsonify(error="Indisponible"), 503


@app.get("/health")
def health():
    try:
        r.ping()
        return jsonify(status="ok", redis="up"), 200
    except redis.RedisError:
        return jsonify(status="degraded", redis="down"), 503


@app.get("/version")
def version():
    return jsonify(version=APP_VERSION, commit=COMMIT_SHA)


@app.post("/todos")
def create_todo():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE_LENGTH:
        return jsonify(error=f"'title' requis : texte non vide, {MAX_TITLE_LENGTH} car. max"), 400
    todo_id = r.incr("todo:next_id")
    r.hset("todos", todo_id, title.strip())
    return jsonify(id=todo_id, title=title.strip()), 201


@app.get("/todos")
def list_todos():
    items = r.hgetall("todos")
    todos = [{"id": int(k), "title": v} for k, v in items.items()]
    return jsonify(sorted(todos, key=lambda t: t["id"]))


@app.delete("/todos/<int:todo_id>")
def delete_todo(todo_id):
    if r.hdel("todos", todo_id) == 0:
        return jsonify(error="tache introuvable"), 404
    return "", 204
