from fastapi import FastAPI

from app.main import app


def test_app_imports() -> None:
    assert isinstance(app, FastAPI)


def test_health_returns_ok(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_returns_login_placeholder(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Вход в AI-редактор статей" in response.text
