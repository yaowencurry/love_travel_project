# Travel Agent V1

FastAPI + LangGraph travel planning agent with MCP-style mock tools and a local `SKILL.md` registry.

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/uvicorn travel_agent.api:app --reload --port 8000
```

Open `http://127.0.0.1:8000`.

## Test

```bash
.venv/bin/python -m pytest -q
```

## V1 Boundaries

- Orders are mock-only.
- No real payment, ticketing, hotel reservation, refund, or cancellation is performed.
- All transactional quotes require user confirmation before mock booking.
- Skills are loaded from `skills/**/SKILL.md` and injected per workflow node.

