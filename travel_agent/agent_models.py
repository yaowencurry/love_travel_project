from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from travel_agent.models import MockBooking, QuoteOption, TripPlanResult, TripRequest


AgentStage = Literal[
    "requirements_review",
    "plan_draft",
    "budget_tradeoff",
    "final_confirmation",
    "completed",
    "error",
]


class AgentAction(StrEnum):
    ADVISE = "advise"
    ACCEPT = "accept"
    REVISE = "revise"
    CONFIRM = "confirm"


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:10]}")
    role: Literal["user", "assistant", "system"] = "user"
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionCard(BaseModel):
    id: str = Field(default_factory=lambda: f"decision_{uuid4().hex[:10]}")
    stage: AgentStage
    title: str
    summary: str
    recommended_action: str
    options: list[str] = Field(default_factory=list)
    requires_user_input: bool = True


class AgentSnapshot(BaseModel):
    stage: AgentStage
    summary: str
    itinerary: list[dict] = Field(default_factory=list)
    transport_options: list[QuoteOption] = Field(default_factory=list)
    hotel_options: list[QuoteOption] = Field(default_factory=list)
    attraction_options: list[QuoteOption] = Field(default_factory=list)
    selected_quote_ids: list[str] = Field(default_factory=list)
    bookings: list[MockBooking] = Field(default_factory=list)


class AgentEvent(BaseModel):
    event: str
    session_id: str
    data: dict
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentSession(BaseModel):
    id: str = Field(default_factory=lambda: f"agent_{uuid4().hex[:12]}")
    stage: AgentStage = "requirements_review"
    messages: list[ChatMessage] = Field(default_factory=list)
    pending_decision: DecisionCard | None = None
    snapshots: list[AgentSnapshot] = Field(default_factory=list)
    result: TripPlanResult | None = None
    trip_request: TripRequest | None = None
    events: list[AgentEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModelDecision(BaseModel):
    stage: AgentStage
    message: str
    summary: str
    extracted_request: TripRequest | None = None
    itinerary: list[dict] = Field(default_factory=list)
    selected_quote_ids: list[str] = Field(default_factory=list)
    decision_required: bool = True
    decision_title: str = "需要确认"
    recommended_action: str = "确认继续"
    options: list[str] = Field(default_factory=lambda: ["确认继续", "补充建议"])


class CreateSessionRequest(BaseModel):
    message: str = Field(min_length=1)


class AddMessageRequest(BaseModel):
    message: str = Field(default="")
    decision_id: str | None = None
    action: AgentAction | None = None
