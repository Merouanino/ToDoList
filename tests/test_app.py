from unittest.mock import patch

import pytest
import redis
from prometheus_client import REGISTRY

import app as app_module

KEYS = ("todos", "todo:next_id")


@pytest.fixture
def client():
    try:
        app_module.r.ping()
    except redis.RedisError:
        pytest.fail("Redis injoignable sur localhost:6379 Conteneur Redis non lancé ?")
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
    {"title": 42},
    {"title": "x" * 201},
    ["pas", "un", "objet"],
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


def sample(name, labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_requests_are_counted_by_endpoint_and_code(client):
    ok = {"method": "GET", "endpoint": "/todos", "code": "200"}
    bad = {"method": "POST", "endpoint": "/todos", "code": "400"}
    ok_before = sample("http_requests_total", ok)
    bad_before = sample("http_requests_total", bad)

    client.get("/todos")
    client.post("/todos", json={})

    assert sample("http_requests_total", ok) == ok_before + 1
    assert sample("http_requests_total", bad) == bad_before + 1


def test_latency_is_observed_per_route(client):
    labels = {"method": "DELETE", "endpoint": "/todos/<int:todo_id>"}
    before = sample("http_request_duration_seconds_count", labels)

    client.delete("/todos/42")
    client.delete("/todos/43")

    assert sample("http_request_duration_seconds_count", labels) == before + 2


def test_metrics_endpoint_exposes_prometheus_format(client):
    client.get("/metrics")
    resp = client.get("/metrics")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert resp.content_type.startswith("text/plain")
    assert "http_request_duration_seconds_bucket" in body
    assert 'endpoint="/metrics"' not in body
    info = {"version": app_module.APP_VERSION, "commit": app_module.COMMIT_SHA}
    assert sample("app_build_info", info) == 1.0


def test_version_exposes_version_and_commit(client):
    resp = client.get("/version")
    assert resp.status_code == 200
    assert resp.get_json() == {"version": app_module.APP_VERSION, "commit": app_module.COMMIT_SHA}
