from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_calc_ok():
    assert client.get("/calc", params={"expr": "2+2*3"}).json()["result"] == 8


def test_calc_rejects_code():
    assert client.get("/calc", params={"expr": "__import__('os').system('id')"}).status_code == 422


def test_ping_rejects_injection():
    assert client.get("/ping", params={"host": "8.8.8.8; id"}).status_code == 422


def test_user_sqli_is_harmless():
    assert client.get("/user", params={"name": "x' OR '1'='1"}).status_code == 422
    assert client.get("/user", params={"name": "admin"}).json()["rows"] == [["admin", "root"]]


def test_fetch_rejects_localhost():
    assert client.post("/fetch", json={"url": "https://localhost/"}).status_code == 400
