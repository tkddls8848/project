from fastapi.testclient import TestClient

from app.main import app


def test_root_serves_poc_front_page():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Nara Hermes Lab" in response.text
    assert "서비스 설계 요청" in response.text


def test_static_assets_are_served():
    client = TestClient(app)

    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_favicon_is_handled_without_not_found():
    response = TestClient(app).get("/favicon.ico")

    assert response.status_code == 204
