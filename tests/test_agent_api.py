from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from travel_agent.agent import AgentService
from travel_agent.agent_models import AgentStage, ModelDecision
from travel_agent.api import app


class ApiFakeModelClient:
    async def decide(self, *, stage: AgentStage, payload: dict) -> ModelDecision:
        return ModelDecision(
            stage=stage,
            message=f"{stage} 消息",
            summary=f"{stage} 摘要",
            extracted_request={
                "origin": "上海",
                "destination": "杭州",
                "days": 2,
                "travelers": 2,
                "budget_cny": 3000,
                "interests": ["亲子"],
            },
            decision_title="需要确认",
            recommended_action="确认继续",
            options=["确认继续", "补充建议"],
        )


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import travel_agent.api as api

    monkeypatch.setattr(api, "agent_service", AgentService(model_client=ApiFakeModelClient()))
    return TestClient(app)


def test_create_agent_session_endpoint_returns_conversation_state(client: TestClient) -> None:
    response = client.post("/api/agent/sessions", json={"message": "上海到杭州两天亲子游"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"].startswith("agent_")
    assert payload["stage"] == "requirements_review"
    assert payload["pending_decision"]["stage"] == "requirements_review"
    assert payload["messages"][0]["role"] == "user"


def test_add_agent_message_continues_same_session(client: TestClient) -> None:
    created = client.post("/api/agent/sessions", json={"message": "上海到杭州两天亲子游"}).json()

    response = client.post(
        f"/api/agent/sessions/{created['id']}/messages",
        json={
            "message": "确认继续",
            "decision_id": created["pending_decision"]["id"],
            "action": "confirm",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == created["id"]
    assert payload["stage"] == "plan_draft"
    assert any(message["content"] == "确认继续" for message in payload["messages"])


def test_agent_event_stream_replays_existing_events(client: TestClient) -> None:
    created = client.post("/api/agent/sessions", json={"message": "上海到杭州两天亲子游"}).json()

    response = client.get(f"/api/agent/sessions/{created['id']}/events?replay=true")

    assert response.status_code == 200
    lines = response.text.splitlines()
    assert "event: session.created" in lines
    assert "event: agent.decision_required" in lines
