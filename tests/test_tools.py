from travel_agent.models import TripRequest
from travel_agent.tools import TravelMockTools


def test_mock_tools_mark_transactional_quotes_as_confirmation_required() -> None:
    tools = TravelMockTools()
    request = TripRequest(origin="上海", destination="杭州", days=2, travelers=2, budget_cny=3000)

    quotes = [
        *tools.quote_transport(request),
        *tools.quote_hotels(request),
        *tools.quote_attractions(request),
    ]

    assert quotes
    assert all(quote.requires_confirmation for quote in quotes)


def test_mock_booking_is_blocked_without_confirmation() -> None:
    tools = TravelMockTools()
    request = TripRequest(origin="上海", destination="杭州", days=2, travelers=2, budget_cny=3000)
    quote = tools.quote_transport(request)[0]

    booking = tools.create_mock_booking(quote, confirmed=False)

    assert booking.status == "blocked"
    assert "未确认" in booking.note

