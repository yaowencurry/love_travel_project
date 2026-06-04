from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

from travel_agent.agent_models import (
    AddMessageRequest,
    AgentAction,
    AgentEvent,
    AgentSession,
    AgentSnapshot,
    AgentStage,
    ChatMessage,
    DecisionCard,
    ModelDecision,
)
from travel_agent.llm import OpenAIChatClient
from travel_agent.models import (
    AgentEvent as WorkflowEvent,
    BudgetSummary,
    ItineraryPlan,
    QuoteOption,
    TravelerProfile,
    TripPlanResult,
    TripRequest,
    TripSession,
)
from travel_agent.tools import TravelMockTools


NEXT_STAGE: dict[AgentStage, AgentStage] = {
    "requirements_review": "plan_draft",
    "plan_draft": "budget_tradeoff",
    "budget_tradeoff": "final_confirmation",
    "final_confirmation": "completed",
}


class AgentService:
    def __init__(
        self,
        model_client: OpenAIChatClient | None = None,
        tools: TravelMockTools | None = None,
    ) -> None:
        self.model_client = model_client or OpenAIChatClient()
        self.tools = tools or TravelMockTools()
        self.sessions: dict[str, AgentSession] = {}
        self.subscribers: dict[str, list[asyncio.Queue[AgentEvent]]] = {}

    async def create_session(self, message: str) -> AgentSession:
        session = AgentSession(messages=[ChatMessage(role="user", content=message)])
        self.sessions[session.id] = session
        self._emit(session, "session.created", {"session_id": session.id})
        await self._run_stage(session, "requirements_review", user_message=message)
        return deepcopy(session)

    def get_session(self, session_id: str) -> AgentSession:
        return deepcopy(self._require_session(session_id))

    async def add_message(
        self,
        session_id: str,
        *,
        message: str,
        action: AgentAction | None = None,
        decision_id: str | None = None,
    ) -> AgentSession:
        session = self._require_session(session_id)
        if decision_id and (session.pending_decision is None or decision_id != session.pending_decision.id):
            raise ValueError("决策项已过期，请刷新会话后重试。")

        user_text = message or self._action_label(action)
        session.messages.append(ChatMessage(role="user", content=user_text))
        self._emit(session, "agent.message", {"role": "user", "content": user_text})

        if action in {AgentAction.CONFIRM, AgentAction.ACCEPT}:
            next_stage = NEXT_STAGE.get(session.stage)
            if next_stage == "completed":
                self._complete_session(session)
            elif next_stage:
                await self._run_stage(session, next_stage, user_message=user_text)
        else:
            await self._run_stage(session, session.stage, user_message=user_text)

        return deepcopy(session)

    async def subscribe(self, session_id: str):
        session = self._require_session(session_id)
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self.subscribers.setdefault(session_id, []).append(queue)
        for event in session.events:
            await queue.put(event)
        try:
            while True:
                yield await queue.get()
        finally:
            self.subscribers.get(session_id, []).remove(queue)

    async def _run_stage(self, session: AgentSession, stage: AgentStage, *, user_message: str) -> None:
        session.stage = stage
        session.pending_decision = None
        self._touch(session)
        self._emit(session, "agent.stage", {"stage": stage})

        payload = self._payload_for_stage(session, stage=stage, user_message=user_message)
        decision = await self.model_client.decide(stage=stage, payload=payload)
        self._apply_decision(session, decision)

    def _apply_decision(self, session: AgentSession, decision: ModelDecision) -> None:
        session.stage = decision.stage
        if decision.extracted_request:
            session.trip_request = decision.extracted_request
        session.messages.append(ChatMessage(role="assistant", content=decision.message))
        snapshot = self._snapshot_from_decision(session, decision)
        session.snapshots.append(snapshot)
        session.pending_decision = (
            DecisionCard(
                stage=decision.stage,
                title=decision.decision_title,
                summary=decision.summary,
                recommended_action=decision.recommended_action,
                options=decision.options,
            )
            if decision.decision_required
            else None
        )
        self._touch(session)
        self._emit(session, "agent.message", {"role": "assistant", "content": decision.message})
        self._emit(session, "agent.snapshot", snapshot.model_dump(mode="json"))
        if session.pending_decision:
            self._emit(session, "agent.decision_required", session.pending_decision.model_dump(mode="json"))

    def _payload_for_stage(self, session: AgentSession, *, stage: AgentStage, user_message: str) -> dict:
        payload = {
            "user_message": user_message,
            "messages": [message.model_dump(mode="json") for message in session.messages],
            "latest_snapshot": session.snapshots[-1].model_dump(mode="json") if session.snapshots else None,
        }
        trip_request = self._trip_request_from_session(session)
        if trip_request and stage in {"budget_tradeoff", "final_confirmation"}:
            payload["quotes"] = self._quote_payload(trip_request)
        return payload

    def _snapshot_from_decision(self, session: AgentSession, decision: ModelDecision) -> AgentSnapshot:
        previous = session.snapshots[-1] if session.snapshots else None
        transport_options = previous.transport_options if previous else []
        hotel_options = previous.hotel_options if previous else []
        attraction_options = previous.attraction_options if previous else []

        trip_request = self._trip_request_from_session(session, decision)
        if trip_request and decision.stage in {"budget_tradeoff", "final_confirmation"}:
            quotes = self._quote_payload(trip_request)
            transport_options = [QuoteOption.model_validate(item) for item in quotes["transport_options"]]
            hotel_options = [QuoteOption.model_validate(item) for item in quotes["hotel_options"]]
            attraction_options = [QuoteOption.model_validate(item) for item in quotes["attraction_options"]]

        return AgentSnapshot(
            stage=decision.stage,
            summary=decision.summary,
            itinerary=decision.itinerary or (previous.itinerary if previous else []),
            transport_options=transport_options,
            hotel_options=hotel_options,
            attraction_options=attraction_options,
            selected_quote_ids=decision.selected_quote_ids or (previous.selected_quote_ids if previous else []),
            bookings=previous.bookings if previous else [],
        )

    def _complete_session(self, session: AgentSession) -> None:
        latest = session.snapshots[-1]
        request = self._trip_request_from_session(session)
        if request is None:
            raise RuntimeError("缺少已确认的旅行需求，无法完成方案。")
        selected_quotes = self._selected_quotes(latest)
        bookings = [self.tools.create_mock_booking(quote, confirmed=True) for quote in selected_quotes]
        total = sum(quote.price_cny for quote in selected_quotes)
        budget_status = "within_budget" if total <= request.budget_cny else "over_budget"
        final_snapshot = latest.model_copy(
            update={
                "stage": "completed",
                "bookings": bookings,
                "summary": f"方案已确认，总预算 {total} 元，已生成 {len(bookings)} 个 mock 订单。",
            }
        )
        session.stage = "completed"
        session.pending_decision = None
        session.snapshots.append(final_snapshot)
        session.result = TripPlanResult(
            session_id=TripSession(request=request).id,
            stage="completed",
            requires_confirmation=False,
            profile=TravelerProfile(travelers=request.travelers, interests=request.interests),
            itinerary=ItineraryPlan(destination=request.destination, days=latest.itinerary),
            transport_options=latest.transport_options,
            hotel_options=latest.hotel_options,
            attraction_options=latest.attraction_options,
            budget=BudgetSummary(
                total_cny=total,
                budget_cny=request.budget_cny,
                status=budget_status,
                savings_hint=None if budget_status == "within_budget" else "预算偏低，建议调整方案。",
            ),
            bookings=bookings,
            events=[WorkflowEvent(stage="completed", message=final_snapshot.summary)],
            summary=final_snapshot.summary,
        )
        session.messages.append(ChatMessage(role="assistant", content=final_snapshot.summary))
        self._touch(session)
        self._emit(session, "agent.snapshot", final_snapshot.model_dump(mode="json"))
        self._emit(session, "agent.completed", session.result.model_dump(mode="json"))

    def _trip_request_from_session(
        self,
        session: AgentSession,
        decision: ModelDecision | None = None,
    ) -> TripRequest | None:
        if decision and decision.extracted_request:
            return decision.extracted_request
        return session.trip_request

    def _quote_payload(self, request: TripRequest) -> dict:
        return {
            "transport_options": [item.model_dump(mode="json") for item in self.tools.quote_transport(request)],
            "hotel_options": [item.model_dump(mode="json") for item in self.tools.quote_hotels(request)],
            "attraction_options": [item.model_dump(mode="json") for item in self.tools.quote_attractions(request)],
        }

    def _selected_quotes(self, snapshot: AgentSnapshot) -> list[QuoteOption]:
        all_quotes = [*snapshot.transport_options, *snapshot.hotel_options, *snapshot.attraction_options]
        by_id = {quote.id: quote for quote in all_quotes}
        selected = [by_id[quote_id] for quote_id in snapshot.selected_quote_ids if quote_id in by_id]
        return selected or all_quotes[:3]

    def _emit(self, session: AgentSession, event: str, data: dict) -> None:
        agent_event = AgentEvent(event=event, session_id=session.id, data=data)
        session.events.append(agent_event)
        for queue in self.subscribers.get(session.id, []):
            queue.put_nowait(agent_event)

    def _require_session(self, session_id: str) -> AgentSession:
        if session_id not in self.sessions:
            raise KeyError("会话不存在。")
        return self.sessions[session_id]

    @staticmethod
    def _touch(session: AgentSession) -> None:
        session.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _action_label(action: AgentAction | None) -> str:
        if action == AgentAction.CONFIRM:
            return "确认继续"
        if action == AgentAction.ACCEPT:
            return "采纳推荐"
        if action == AgentAction.REVISE:
            return "要求调整"
        return "补充建议"
