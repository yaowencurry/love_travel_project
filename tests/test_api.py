from fastapi.testclient import TestClient

from travel_agent.api import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_plan_endpoint_returns_awaiting_confirmation() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/trips/plan",
        json={
            "origin": "上海",
            "destination": "杭州",
            "days": 2,
            "travelers": 2,
            "budget_cny": 2500,
            "interests": ["亲子", "西湖"],
            "confirmed": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "awaiting_confirmation"
    assert payload["bookings"] == []
    assert payload["requires_confirmation"] is True

