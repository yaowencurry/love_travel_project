from __future__ import annotations

from travel_agent.models import MockBooking, QuoteOption, TripRequest


class TravelMockTools:
    def search_poi(self, request: TripRequest) -> list[str]:
        interests = request.interests or ["城市地标", "本地美食"]
        return [f"{request.destination}{interest}体验" for interest in interests[:3]]

    def quote_transport(self, request: TripRequest) -> list[QuoteOption]:
        base = 98 if request.origin in {"上海", "苏州", "南京"} else 360
        return [
            QuoteOption(
                id="transport_train_1",
                kind="transport",
                name=f"{request.origin} -> {request.destination} 高铁二等座",
                provider="mock-rail",
                price_cny=base * request.travelers,
                refundable=True,
                requires_confirmation=True,
                metadata={"vehicle": "train", "duration_minutes": 70},
            ),
            QuoteOption(
                id="transport_car_1",
                kind="transport",
                name=f"{request.origin} -> {request.destination} 城际专车",
                provider="mock-car",
                price_cny=(base + 180) * request.travelers,
                refundable=True,
                requires_confirmation=True,
                metadata={"vehicle": "car", "duration_minutes": 150},
            ),
        ]

    def quote_hotels(self, request: TripRequest) -> list[QuoteOption]:
        nights = max(request.days - 1, 1)
        return [
            QuoteOption(
                id="hotel_family_1",
                kind="hotel",
                name=f"{request.destination}湖畔亲子酒店",
                provider="mock-hotel",
                price_cny=520 * nights,
                refundable=True,
                requires_confirmation=True,
                metadata={"nights": nights, "breakfast": True},
            ),
            QuoteOption(
                id="hotel_budget_1",
                kind="hotel",
                name=f"{request.destination}市中心精选酒店",
                provider="mock-hotel",
                price_cny=360 * nights,
                refundable=True,
                requires_confirmation=True,
                metadata={"nights": nights, "breakfast": False},
            ),
        ]

    def quote_attractions(self, request: TripRequest) -> list[QuoteOption]:
        per_person = 80 if request.destination in {"杭州", "苏州", "南京"} else 160
        return [
            QuoteOption(
                id="attraction_pass_1",
                kind="attraction",
                name=f"{request.destination}核心景点联票",
                provider="mock-ticket",
                price_cny=per_person * request.travelers,
                refundable=False,
                requires_confirmation=True,
                metadata={"ticket_type": "bundle"},
            )
        ]

    def create_mock_booking(self, quote: QuoteOption, confirmed: bool) -> MockBooking:
        if not confirmed:
            return MockBooking(
                quote_id=quote.id,
                kind=quote.kind,
                status="blocked",
                note="用户未确认，禁止进入模拟下单。",
            )
        return MockBooking(
            quote_id=quote.id,
            kind=quote.kind,
            status="mock_confirmed",
            note="模拟订单已生成，未发生真实支付、出票或预订。",
        )


def choose_lowest(options: list[QuoteOption]) -> QuoteOption:
    return min(options, key=lambda option: option.price_cny)

