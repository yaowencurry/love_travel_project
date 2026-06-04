from __future__ import annotations

import pytest

from travel_agent.agent import AgentService
from travel_agent.agent_models import AgentAction, AgentStage, ModelDecision
from travel_agent.llm import LLMConfig, MissingLLMConfigError, OpenAIChatClient
from travel_agent.prompts import SYSTEM_PROMPT


class FakeModelClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def decide(self, *, stage: AgentStage, payload: dict) -> ModelDecision:
        self.calls.append({"stage": stage, "payload": payload})
        return ModelDecision(
            stage=stage,
            message=f"{stage} 阶段完成",
            summary="阶段摘要",
            extracted_request={
                "origin": "上海",
                "destination": "杭州",
                "days": 2,
                "travelers": 2,
                "budget_cny": 3000,
                "interests": ["亲子", "西湖"],
            },
            itinerary=[
                {
                    "day": 1,
                    "title": "杭州第 1 天",
                    "morning": "西湖",
                    "afternoon": "亲子体验",
                    "evening": "本地餐饮",
                },
                {
                    "day": 2,
                    "title": "杭州第 2 天",
                    "morning": "博物馆",
                    "afternoon": "城市漫游",
                    "evening": "返程准备",
                },
            ],
            selected_quote_ids=["transport_train_1", "hotel_budget_1", "attraction_pass_1"],
            decision_required=stage
            in {"requirements_review", "plan_draft", "budget_tradeoff", "final_confirmation"},
            decision_title=f"{stage} 决策",
            recommended_action="建议继续",
            options=["采纳推荐", "补充建议"],
        )


def test_llm_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIROUTER_API_KEY", raising=False)

    with pytest.raises(MissingLLMConfigError):
        LLMConfig.from_env()


def test_openai_client_uses_config_and_system_prompt() -> None:
    config = LLMConfig(api_key="test-key", base_url="https://example.test/v1", model="gpt-5.5")
    client = OpenAIChatClient(config=config)

    request = client.build_chat_request(stage="requirements_review", payload={"user_message": "去杭州玩"})

    assert request["model"] == "gpt-5.5"
    assert request["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert "requirements_review" in request["messages"][1]["content"]
    assert request["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_agent_session_starts_with_decision_required() -> None:
    service = AgentService(model_client=FakeModelClient())

    session = await service.create_session("上海到杭州两天亲子游，预算 3000")

    assert session.stage == "requirements_review"
    assert session.pending_decision is not None
    assert session.pending_decision.stage == "requirements_review"
    assert session.messages[-1].role == "assistant"
    assert session.snapshots[-1].stage == "requirements_review"


@pytest.mark.asyncio
async def test_agent_accepting_key_decisions_advances_to_completed_with_bookings() -> None:
    service = AgentService(model_client=FakeModelClient())
    session = await service.create_session("上海到杭州两天亲子游，预算 3000")

    for _ in range(4):
        session = await service.add_message(
            session.id,
            message="确认继续",
            action=AgentAction.CONFIRM,
            decision_id=session.pending_decision.id if session.pending_decision else None,
        )

    assert session.stage == "completed"
    assert session.pending_decision is None
    assert session.result is not None
    assert session.result.bookings
    assert all(booking.status == "mock_confirmed" for booking in session.result.bookings)


@pytest.mark.asyncio
async def test_budget_stage_passes_tool_quotes_to_model() -> None:
    model = FakeModelClient()
    service = AgentService(model_client=model)
    session = await service.create_session("上海到杭州两天亲子游，预算 3000")
    await service.add_message(session.id, message="确认需求", action=AgentAction.CONFIRM, decision_id=session.pending_decision.id)
    await service.add_message(session.id, message="确认行程", action=AgentAction.CONFIRM, decision_id=service.get_session(session.id).pending_decision.id)

    budget_call = model.calls[-1]

    assert budget_call["stage"] == "budget_tradeoff"
    assert budget_call["payload"]["quotes"]["transport_options"]
    assert budget_call["payload"]["quotes"]["hotel_options"]
    assert budget_call["payload"]["quotes"]["attraction_options"]

