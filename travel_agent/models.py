from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


Stage = Literal[
    "collect_requirements",
    "generate_itinerary",
    "quote_transport",
    "quote_hotels",
    "quote_attractions",
    "optimize_budget",
    "awaiting_confirmation",
    "mock_booking",
    "completed",
]


class TravelerProfile(BaseModel):
    travelers: int = Field(default=1, ge=1, le=20)
    interests: list[str] = Field(default_factory=list)
    pace: Literal["relaxed", "balanced", "intensive"] = "balanced"


class TripRequest(BaseModel):
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    days: int = Field(ge=1, le=30)
    travelers: int = Field(default=1, ge=1, le=20)
    budget_cny: int = Field(default=3000, ge=1)
    interests: list[str] = Field(default_factory=list)
    confirmed: bool = False

    @field_validator("origin", "destination")
    @classmethod
    def strip_city(cls, value: str) -> str:
        return value.strip()


class TripSession(BaseModel):
    id: str = Field(default_factory=lambda: f"trip_{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request: TripRequest


class DayPlan(BaseModel):
    day: int
    title: str
    morning: str
    afternoon: str
    evening: str


class ItineraryPlan(BaseModel):
    destination: str
    days: list[DayPlan]


class QuoteOption(BaseModel):
    id: str
    kind: Literal["transport", "hotel", "attraction"]
    name: str
    provider: str
    price_cny: int = Field(ge=0)
    refundable: bool = True
    requires_confirmation: bool = False
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)


class BudgetSummary(BaseModel):
    total_cny: int = Field(ge=0)
    budget_cny: int = Field(ge=1)
    status: Literal["within_budget", "over_budget"]
    savings_hint: str | None = None


class MockBooking(BaseModel):
    id: str = Field(default_factory=lambda: f"mock_{uuid4().hex[:10]}")
    quote_id: str
    kind: Literal["transport", "hotel", "attraction"]
    status: Literal["mock_confirmed", "blocked"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str


class AgentEvent(BaseModel):
    stage: Stage
    message: str
    skill: str | None = None
    tool: str | None = None


class TripPlanResult(BaseModel):
    session_id: str
    stage: Stage
    requires_confirmation: bool
    profile: TravelerProfile
    itinerary: ItineraryPlan
    transport_options: list[QuoteOption]
    hotel_options: list[QuoteOption]
    attraction_options: list[QuoteOption]
    budget: BudgetSummary
    bookings: list[MockBooking]
    events: list[AgentEvent]
    summary: str

