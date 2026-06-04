from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from travel_agent.models import (
    AgentEvent,
    BudgetSummary,
    DayPlan,
    ItineraryPlan,
    MockBooking,
    QuoteOption,
    Stage,
    TravelerProfile,
    TripPlanResult,
    TripRequest,
    TripSession,
)
from travel_agent.skills import SkillRegistry
from travel_agent.tools import TravelMockTools, choose_lowest


class TravelState(TypedDict, total=False):
    request: TripRequest
    session: TripSession
    profile: TravelerProfile
    itinerary: ItineraryPlan
    transport_options: list[QuoteOption]
    hotel_options: list[QuoteOption]
    attraction_options: list[QuoteOption]
    selected_quotes: list[QuoteOption]
    budget: BudgetSummary
    bookings: list[MockBooking]
    events: list[AgentEvent]
    summary: str
    stage: Stage
    requires_confirmation: bool


class TravelAgentWorkflow:
    def __init__(
        self,
        skills_root: Path | str = "skills",
        tools: TravelMockTools | None = None,
    ) -> None:
        self.skills = SkillRegistry(skills_root)
        self.tools = tools or TravelMockTools()
        self.graph = self._build_graph()

    async def run(self, request: TripRequest) -> TripPlanResult:
        initial: TravelState = {"request": request, "events": []}
        state = await self.graph.ainvoke(initial)
        return self._to_result(state)

    def _build_graph(self):
        graph = StateGraph(TravelState)
        graph.add_node("collect_requirements", self._collect_requirements)
        graph.add_node("generate_itinerary", self._generate_itinerary)
        graph.add_node("quote_transport", self._quote_transport)
        graph.add_node("quote_hotels", self._quote_hotels)
        graph.add_node("quote_attractions", self._quote_attractions)
        graph.add_node("optimize_budget", self._optimize_budget)
        graph.add_node("ask_user_confirmation", self._ask_user_confirmation)
        graph.add_node("mock_booking", self._mock_booking)
        graph.add_node("final_summary", self._final_summary)

        graph.add_edge(START, "collect_requirements")
        graph.add_edge("collect_requirements", "generate_itinerary")
        graph.add_edge("generate_itinerary", "quote_transport")
        graph.add_edge("quote_transport", "quote_hotels")
        graph.add_edge("quote_hotels", "quote_attractions")
        graph.add_edge("quote_attractions", "optimize_budget")
        graph.add_edge("optimize_budget", "ask_user_confirmation")
        graph.add_conditional_edges(
            "ask_user_confirmation",
            lambda state: "mock_booking" if state["request"].confirmed else "final_summary",
            {"mock_booking": "mock_booking", "final_summary": "final_summary"},
        )
        graph.add_edge("mock_booking", "final_summary")
        graph.add_edge("final_summary", END)
        return graph.compile()

    def _collect_requirements(self, state: TravelState) -> TravelState:
        request = state["request"]
        session = TripSession(request=request)
        profile = TravelerProfile(
            travelers=request.travelers,
            interests=request.interests,
            pace="balanced",
        )
        return {
            **state,
            "session": session,
            "profile": profile,
            "stage": "collect_requirements",
            "events": self._event(state, "collect_requirements", "已收集出发地、目的地、天数、预算和兴趣偏好。"),
        }

    def _generate_itinerary(self, state: TravelState) -> TravelState:
        request = state["request"]
        pois = self.tools.search_poi(request)
        days = [
            DayPlan(
                day=day,
                title=f"{request.destination}第 {day} 天",
                morning=pois[(day - 1) % len(pois)],
                afternoon=f"{request.destination}城市漫游与本地餐饮",
                evening="酒店休整" if day < request.days else "返程准备",
            )
            for day in range(1, request.days + 1)
        ]
        return {
            **state,
            "itinerary": ItineraryPlan(destination=request.destination, days=days),
            "stage": "generate_itinerary",
            "events": self._event(state, "generate_itinerary", "已生成按天行程草案。", tool="travel_search_mcp"),
        }

    def _quote_transport(self, state: TravelState) -> TravelState:
        return {
            **state,
            "transport_options": self.tools.quote_transport(state["request"]),
            "stage": "quote_transport",
            "events": self._event(state, "quote_transport", "已获取交通 mock 报价。", tool="travel_search_mcp"),
        }

    def _quote_hotels(self, state: TravelState) -> TravelState:
        return {
            **state,
            "hotel_options": self.tools.quote_hotels(state["request"]),
            "stage": "quote_hotels",
            "events": self._event(state, "quote_hotels", "已获取酒店 mock 报价。", tool="hotel_mock_mcp"),
        }

    def _quote_attractions(self, state: TravelState) -> TravelState:
        return {
            **state,
            "attraction_options": self.tools.quote_attractions(state["request"]),
            "stage": "quote_attractions",
            "events": self._event(state, "quote_attractions", "已获取门票 mock 报价。", tool="ticket_mock_mcp"),
        }

    def _optimize_budget(self, state: TravelState) -> TravelState:
        selected = [
            choose_lowest(state["transport_options"]),
            choose_lowest(state["hotel_options"]),
            choose_lowest(state["attraction_options"]),
        ]
        total = sum(option.price_cny for option in selected)
        budget = state["request"].budget_cny
        status = "within_budget" if total <= budget else "over_budget"
        return {
            **state,
            "selected_quotes": selected,
            "budget": BudgetSummary(
                total_cny=total,
                budget_cny=budget,
                status=status,
                savings_hint=None if status == "within_budget" else "预算偏低，建议减少天数、提高预算或改选更低价交通/酒店。",
            ),
            "stage": "optimize_budget",
            "events": self._event(state, "optimize_budget", "已选择低价组合并计算预算。"),
        }

    def _ask_user_confirmation(self, state: TravelState) -> TravelState:
        confirmed = state["request"].confirmed
        return {
            **state,
            "requires_confirmation": not confirmed,
            "stage": "awaiting_confirmation" if not confirmed else "mock_booking",
            "events": self._event(
                state,
                "ask_user_confirmation",
                "等待用户确认后才允许模拟下单。" if not confirmed else "用户已确认，准备生成模拟订单。",
            ),
        }

    def _mock_booking(self, state: TravelState) -> TravelState:
        bookings = [
            self.tools.create_mock_booking(quote, confirmed=state["request"].confirmed)
            for quote in state["selected_quotes"]
        ]
        return {
            **state,
            "bookings": bookings,
            "requires_confirmation": False,
            "stage": "mock_booking",
            "events": self._event(state, "mock_booking", "已生成模拟订单。", tool="booking_mock_mcp"),
        }

    def _final_summary(self, state: TravelState) -> TravelState:
        bookings = state.get("bookings", [])
        budget = state["budget"]
        if bookings:
            summary = f"行程已完成模拟闭环，总预算 {budget.total_cny} 元，已生成 {len(bookings)} 个 mock 订单。"
            stage: Stage = "completed"
        elif budget.status == "over_budget":
            summary = f"方案已生成但预算超出：预计 {budget.total_cny} 元，高于预算 {budget.budget_cny} 元；需要用户调整或确认。"
            stage = "awaiting_confirmation"
        else:
            summary = f"方案已生成，预计 {budget.total_cny} 元；确认后可生成模拟订单。"
            stage = "awaiting_confirmation"
        return {
            **state,
            "summary": summary,
            "stage": stage,
            "events": self._event(state, stage, "已汇总行程、预算和订单状态。"),
        }

    def _event(
        self,
        state: TravelState,
        task: str,
        message: str,
        tool: str | None = None,
    ) -> list[AgentEvent]:
        skill = self.skills.match(task)
        return [
            *state.get("events", []),
            AgentEvent(
                stage=task if task != "ask_user_confirmation" else "awaiting_confirmation",
                message=message,
                skill=skill.name if skill else None,
                tool=tool,
            ),
        ]

    @staticmethod
    def _to_result(state: TravelState) -> TripPlanResult:
        return TripPlanResult(
            session_id=state["session"].id,
            stage=state["stage"],
            requires_confirmation=state.get("requires_confirmation", False),
            profile=state["profile"],
            itinerary=state["itinerary"],
            transport_options=state["transport_options"],
            hotel_options=state["hotel_options"],
            attraction_options=state["attraction_options"],
            budget=state["budget"],
            bookings=state.get("bookings", []),
            events=state["events"],
            summary=state["summary"],
        )
