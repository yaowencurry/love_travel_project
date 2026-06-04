from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from travel_agent.agent import AgentService
from travel_agent.agent_models import AddMessageRequest, CreateSessionRequest
from travel_agent.models import TripRequest
from travel_agent.workflow import TravelAgentWorkflow


app = FastAPI(title="Travel Agent V1")
workflow = TravelAgentWorkflow()
agent_service = AgentService()

app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    index_path = Path("web/dist/index.html")
    if not index_path.exists():
        index_path = Path("web/index.html")
    return index_path.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent/sessions")
async def create_agent_session(request: CreateSessionRequest):
    try:
        return await agent_service.create_session(request.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/agent/sessions/{session_id}")
def get_agent_session(session_id: str):
    try:
        return agent_service.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/agent/sessions/{session_id}/messages")
async def add_agent_message(session_id: str, request: AddMessageRequest):
    try:
        return await agent_service.add_message(
            session_id,
            message=request.message,
            action=request.action,
            decision_id=request.decision_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/agent/sessions/{session_id}/events")
async def stream_agent_events(session_id: str, replay: bool = False):
    try:
        session = agent_service.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def events():
        if replay:
            for event in session.events:
                payload = event.model_dump(mode="json")
                yield f"event: {event.event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            return
        async for event in agent_service.subscribe(session_id):
            payload = event.model_dump(mode="json")
            yield f"event: {event.event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/trips/plan")
async def plan_trip(request: TripRequest):
    return await workflow.run(request)


@app.post("/api/trips/stream")
async def stream_trip(request: TripRequest):
    result = await workflow.run(request)

    async def events():
        for event in result.events:
            yield f"data: {event.model_dump_json()}\n\n"
        yield f"data: {json.dumps({'stage': result.stage, 'summary': result.summary}, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
