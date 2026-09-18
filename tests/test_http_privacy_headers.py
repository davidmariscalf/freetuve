from fastapi.testclient import TestClient

from app.main import app


def test_lesson_api_responses_are_not_cacheable():
    with TestClient(app) as client:
        response = client.get("/api/lessons/not-a-valid-uuid")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
