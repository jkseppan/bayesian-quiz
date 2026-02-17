"""FastAPI application for Bayesian Quiz."""

import asyncio
import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from .state import game

app = FastAPI(title="Bayesian Quiz")

# Templates setup
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Serve mockups as static files for now (until we migrate to templates)
MOCKUPS_DIR = Path(__file__).parent.parent.parent / "mockups"
if MOCKUPS_DIR.exists():
    app.mount("/mockups", StaticFiles(directory=MOCKUPS_DIR, html=True), name="mockups")


# --- SSE Endpoint ---


@app.get("/events")
async def events(request: Request):
    """SSE endpoint for real-time state updates."""

    async def event_generator():
        queue = game.subscribe()
        try:
            # Send initial state
            yield {
                "event": "connected",
                "data": json.dumps({"phase": game.state.phase.value}),
            }

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for events with timeout to check disconnection
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": event,
                        "data": json.dumps(_serialize_state()),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "keepalive", "data": ""}

        finally:
            game.unsubscribe(queue)

    return EventSourceResponse(event_generator())


def _serialize_state() -> dict:
    """Serialize game state for JSON transmission."""
    state = game.state
    return {
        "phase": state.phase.value,
        "current_question_index": state.current_question_index,
        "total_questions": len(state.questions),
        "participant_count": len(state.participants),
        "estimate_count": len(state.get_current_estimates()),
        "question": (
            {
                "text": state.current_question.text,
                "unit": state.current_question.unit,
            }
            if state.current_question
            else None
        ),
    }


# --- Page Routes ---


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page with links to different views."""
    return templates.TemplateResponse(
        request, "index.html", {"game": game.state}
    )


@app.get("/projector", response_class=HTMLResponse)
async def projector(request: Request):
    """Projector view - shown on the big screen."""
    return templates.TemplateResponse(
        request, "projector.html", {"game": game.state}
    )


@app.get("/play", response_class=HTMLResponse)
async def participant(
    request: Request, participant_id: Annotated[str | None, Cookie()] = None
):
    """Participant view - for players on their phones."""
    participant = None
    if participant_id:
        participant = game.state.participants.get(participant_id)

    return templates.TemplateResponse(
        request,
        "participant.html",
        {"game": game.state, "participant": participant},
    )


@app.get("/control", response_class=HTMLResponse)
async def quizmaster(request: Request):
    """Quizmaster control panel."""
    return templates.TemplateResponse(
        request,
        "quizmaster.html",
        {"game": game.state},
    )


# --- HTMX Fragment Routes ---


@app.get("/fragments/projector", response_class=HTMLResponse)
async def fragment_projector(request: Request):
    """Get projector fragment for HTMX updates."""
    return templates.TemplateResponse(
        request,
        "fragments/projector.html",
        {"game": game.state},
    )


@app.get("/fragments/participant", response_class=HTMLResponse)
async def fragment_participant(
    request: Request, participant_id: Annotated[str | None, Cookie()] = None
):
    """Get participant fragment for HTMX updates."""
    participant = None
    if participant_id:
        participant = game.state.participants.get(participant_id)

    return templates.TemplateResponse(
        request,
        "fragments/participant.html",
        {"game": game.state, "participant": participant},
    )


@app.get("/fragments/quizmaster", response_class=HTMLResponse)
async def fragment_quizmaster(request: Request):
    """Get quizmaster fragment for HTMX updates."""
    return templates.TemplateResponse(
        request,
        "fragments/quizmaster.html",
        {"game": game.state},
    )


# --- API Routes ---


@app.post("/api/register", response_class=HTMLResponse)
async def register(
    request: Request,
    nickname: Annotated[str, Form()],
):
    """Register a new participant."""
    participant_id = str(uuid4())
    participant = await game.add_participant(participant_id, nickname)
    # Return the participant fragment so HTMX can swap it in
    response = templates.TemplateResponse(
        request,
        "fragments/participant.html",
        {"game": game.state, "participant": participant},
    )
    response.set_cookie(key="participant_id", value=participant_id, httponly=True)
    return response


@app.post("/api/estimate", response_class=HTMLResponse)
async def submit_estimate(
    request: Request,
    mu: Annotated[float, Form()],
    sigma: Annotated[float, Form()],
    participant_id: Annotated[str | None, Cookie()] = None,
):
    """Submit an estimate for the current question."""
    if not participant_id:
        return HTMLResponse("<p>Not registered</p>", status_code=401)

    participant = game.state.participants.get(participant_id)
    if not participant:
        return HTMLResponse("<p>Participant not found</p>", status_code=404)

    await game.submit_estimate(participant_id, mu, sigma)
    # Return the updated participant fragment
    return templates.TemplateResponse(
        request,
        "fragments/participant.html",
        {"game": game.state, "participant": participant},
    )


@app.post("/api/advance")
async def advance():
    """Advance to the next phase (quizmaster only)."""
    await game.advance_phase()
    return {"phase": game.state.phase.value}


@app.post("/api/reset")
async def reset():
    """Reset the game (quizmaster only)."""
    await game.reset()
    return {"status": "reset"}


# --- Dev server entry point ---


def main() -> None:
    """Run the development server."""
    import uvicorn

    uvicorn.run(
        "bayesian_quiz.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
