from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from travel_agent.models import TripRequest
from travel_agent.tools import TravelMockTools

travel_search_mcp = FastMCP("travel_search_mcp")
hotel_mock_mcp = FastMCP("hotel_mock_mcp")
ticket_mock_mcp = FastMCP("ticket_mock_mcp")
booking_mock_mcp = FastMCP("booking_mock_mcp")
tools = TravelMockTools()


@travel_search_mcp.tool()
def search_poi(origin: str, destination: str, days: int, travelers: int, budget_cny: int) -> list[str]:
    return tools.search_poi(
        TripRequest(
            origin=origin,
            destination=destination,
            days=days,
            travelers=travelers,
            budget_cny=budget_cny,
        )
    )


@travel_search_mcp.tool()
def quote_transport(origin: str, destination: str, days: int, travelers: int, budget_cny: int) -> list[dict]:
    request = TripRequest(origin=origin, destination=destination, days=days, travelers=travelers, budget_cny=budget_cny)
    return [option.model_dump(mode="json") for option in tools.quote_transport(request)]


@hotel_mock_mcp.tool()
def quote_hotels(origin: str, destination: str, days: int, travelers: int, budget_cny: int) -> list[dict]:
    request = TripRequest(origin=origin, destination=destination, days=days, travelers=travelers, budget_cny=budget_cny)
    return [option.model_dump(mode="json") for option in tools.quote_hotels(request)]


@ticket_mock_mcp.tool()
def quote_attractions(origin: str, destination: str, days: int, travelers: int, budget_cny: int) -> list[dict]:
    request = TripRequest(origin=origin, destination=destination, days=days, travelers=travelers, budget_cny=budget_cny)
    return [option.model_dump(mode="json") for option in tools.quote_attractions(request)]

