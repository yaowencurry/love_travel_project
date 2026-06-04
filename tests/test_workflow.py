import pytest

from travel_agent.models import TripRequest
from travel_agent.workflow import TravelAgentWorkflow


@pytest.mark.asyncio
async def test_workflow_blocks_mock_booking_without_user_confirmation() -> None:
    workflow = TravelAgentWorkflow()

    result = await workflow.run(
        TripRequest(
            origin="上海",
            destination="杭州",
            days=2,
            travelers=2,
            budget_cny=2500,
            interests=["亲子", "西湖"],
            confirmed=False,
        )
    )

    assert result.stage == "awaiting_confirmation"
    assert result.bookings == []
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_workflow_generates_mock_bookings_after_confirmation() -> None:
    workflow = TravelAgentWorkflow()

    result = await workflow.run(
        TripRequest(
            origin="上海",
            destination="杭州",
            days=2,
            travelers=2,
            budget_cny=3000,
            interests=["亲子", "西湖"],
            confirmed=True,
        )
    )

    assert result.stage == "completed"
    assert result.requires_confirmation is False
    assert len(result.itinerary.days) == 2
    assert len(result.transport_options) >= 1
    assert len(result.hotel_options) >= 1
    assert len(result.attraction_options) >= 1
    assert len(result.bookings) == 3
    assert all(booking.status == "mock_confirmed" for booking in result.bookings)
    assert result.budget.total_cny <= 3000


@pytest.mark.asyncio
async def test_workflow_marks_over_budget_when_budget_is_too_low() -> None:
    workflow = TravelAgentWorkflow()

    result = await workflow.run(
        TripRequest(
            origin="北京",
            destination="三亚",
            days=3,
            travelers=2,
            budget_cny=500,
            interests=["海滩"],
            confirmed=False,
        )
    )

    assert result.budget.status == "over_budget"
    assert "预算" in result.summary

