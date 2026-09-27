from unittest.mock import patch

import pytest
import redis

import app as app_module

KEYS = ("todos", "todo:next_id")


@pytest.fixture
def client():
    try:
        app_module.r.ping()
    except redis.RedisError:
        pytest.fail("Redis injoignable sur localhost:6379 - conteneur à lancer ?")
    app_module.r.delete(*KEYS)
    with app_module.app.test_client() as c:
        yield c
    app_module.r.delete(*KEYS)


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "redis": "up"}


def test_create_list_delete(client):
    resp = client.post("/todos", json={"title": "  Faire le livrable DevOps ce weekend  "})
    assert resp.status_code == 201
    assert resp.get_json() == {"id": 1, "title": "Faire le livrable DevOps ce weekend"}
    client.post("/todos", json={"title": "Écrire le Dockerfile"})

    assert app_module.r.hget("todos", "2") == "Écrire le Dockerfile"

    assert client.get("/todos").get_json() == [
        {"id": 1, "title": "Faire le livrable DevOps ce weekend"},
        {"id": 2, "title": "Écrire le Dockerfile"},
    ]

    assert client.delete("/todos/1").status_code == 204
    assert client.get("/todos").get_json() == [{"id": 2, "title": "Écrire le Dockerfile"}]
    assert client.delete("/todos/1").status_code == 404


@pytest.mark.parametrize("payload", [
    {},
    {"title": ""},
    {"title": "   "},
    {"title": 213},
    {"title": "x" * 213},
    ["pas", "un", "dict"],
])
def test_create_rejects_invalid_title(client, payload):
    assert client.post("/todos", json=payload).status_code == 400
    assert client.get("/todos").get_json() == []


def test_redis_down_returns_503(client):
    with patch.object(app_module.r, "ping", side_effect=redis.ConnectionError("down")):
        assert client.get("/health").status_code == 503
    with patch.object(app_module.r, "hgetall", side_effect=redis.ConnectionError("down")):
        resp = client.get("/todos")
    assert resp.status_code == 503
    assert resp.get_json() == {"error": "Indisponible"}
