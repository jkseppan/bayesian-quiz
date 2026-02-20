"""FastAPI application for Bayesian Quiz."""

import asyncio
import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .state import (
    get_or_create_game,
    games,
    GameManager,
    GamePhase,
    QUESTION_DURATION_SECONDS,
    GRACE_PERIOD_SECONDS,
)
from .questions import list_quizzes

app = FastAPI(title="Bayesian Quiz")


@app.on_event("shutdown")
async def _shutdown():
    for gm in games.values():
        await gm.shutdown()


TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

MOCKUPS_DIR = Path(__file__).parent.parent.parent / "mockups"
if MOCKUPS_DIR.exists():
    app.mount("/mockups", StaticFiles(directory=MOCKUPS_DIR, html=True), name="mockups")


def _get_slug(request: Request) -> str | None:
    """Extract slug from query string (first key without a value, or 'slug' param)."""
    if "slug" in request.query_params:
        return request.query_params["slug"]
    for key, value in request.query_params.items():
        if value == "":
            return key
    return None


def _get_game(request: Request) -> tuple[str, GameManager]:
    slug = _get_slug(request)
    if not slug:
        raise ValueError("Missing quiz slug")
    return slug, get_or_create_game(slug)


# --- SSE Endpoint ---


def _sse_message(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def _serialize_state(game: GameManager) -> dict:
    state = game.state
    return {
        "phase": state.phase.value,
        "current_question_index": state.current_question_index,
        "total_questions": len(state.questions),
        "participant_count": len(state.participants),
        "estimate_count": len(state.get_current_estimates()),
        "question_deadline": state.question_deadline,
        "question": (
            {
                "text": state.current_question.text,
                "unit": state.current_question.unit,
            }
            if state.current_question
            else None
        ),
    }


@app.get("/events")
async def events(request: Request):
    slug, game = _get_game(request)

    async def event_generator():
        queue = game.subscribe()
        try:
            yield "retry: 500\n"
            yield _sse_message("connected", json.dumps({"phase": game.state.phase.value}))

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if event is None:
                        break
                    yield _sse_message(event, json.dumps(_serialize_state(game)))
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

        finally:
            game.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Page Routes ---


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    slug = _get_slug(request)
    if slug:
        return RedirectResponse(url=f"/play?{slug}", status_code=302)
    available = list_quizzes()
    return templates.TemplateResponse(
        request, "index.html", {"quizzes": available}
    )


@app.get("/projector", response_class=HTMLResponse)
async def projector(request: Request):
    slug, game = _get_game(request)
    return templates.TemplateResponse(
        request, "projector.html", {"game": game.state, "slug": slug}
    )


@app.get("/play", response_class=HTMLResponse)
async def participant(
    request: Request, participant_id: Annotated[str | None, Cookie()] = None
):
    slug, game = _get_game(request)
    p = None
    if participant_id:
        p = game.state.participants.get(participant_id)

    return templates.TemplateResponse(
        request,
        "participant.html",
        {"game": game.state, "participant": p, "slug": slug},
    )


@app.get("/control", response_class=HTMLResponse)
async def quizmaster(request: Request):
    slug, game = _get_game(request)
    return templates.TemplateResponse(
        request,
        "quizmaster.html",
        {"game": game.state, "slug": slug},
    )


# --- HTMX Fragment Routes ---


@app.get("/fragments/projector", response_class=HTMLResponse)
async def fragment_projector(request: Request):
    slug, game = _get_game(request)
    return templates.TemplateResponse(
        request,
        "fragments/projector.html",
        {"game": game.state, "slug": slug},
    )


@app.get("/fragments/participant", response_class=HTMLResponse)
async def fragment_participant(
    request: Request, participant_id: Annotated[str | None, Cookie()] = None
):
    slug, game = _get_game(request)
    p = None
    if participant_id:
        p = game.state.participants.get(participant_id)

    return templates.TemplateResponse(
        request,
        "fragments/participant.html",
        {"game": game.state, "participant": p, "slug": slug},
    )


@app.get("/fragments/quizmaster", response_class=HTMLResponse)
async def fragment_quizmaster(request: Request):
    slug, game = _get_game(request)
    return templates.TemplateResponse(
        request,
        "fragments/quizmaster.html",
        {"game": game.state, "slug": slug},
    )


# --- API Routes ---


@app.post("/api/register", response_class=HTMLResponse)
async def register(
    request: Request,
    nickname: Annotated[str, Form()],
):
    slug, game = _get_game(request)
    participant_id = str(uuid4())
    try:
        p = await game.add_participant(participant_id, nickname)
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "fragments/participant.html",
            {"game": game.state, "participant": None, "error": str(e), "slug": slug},
        )
    response = templates.TemplateResponse(
        request,
        "fragments/participant.html",
        {"game": game.state, "participant": p, "slug": slug},
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
    slug, game = _get_game(request)
    if not participant_id:
        return HTMLResponse("<p>Not registered</p>", status_code=401)

    p = game.state.participants.get(participant_id)
    if not p:
        return HTMLResponse("<p>Participant not found</p>", status_code=404)

    try:
        await game.submit_estimate(participant_id, mu, sigma)
    except ValueError as e:
        return HTMLResponse(f"<p>{e}</p>", status_code=400)
    return templates.TemplateResponse(
        request,
        "fragments/participant.html",
        {"game": game.state, "participant": p, "slug": slug},
    )


def _schedule_auto_advance(game: GameManager) -> None:
    if game._auto_advance_task and not game._auto_advance_task.done():
        game._auto_advance_task.cancel()

    async def _auto_advance(question_index: int) -> None:
        await asyncio.sleep(QUESTION_DURATION_SECONDS + GRACE_PERIOD_SECONDS)
        if (
            game.state.phase == GamePhase.QUESTION_ACTIVE
            and game.state.current_question_index == question_index
        ):
            await game.advance_phase()

    game._auto_advance_task = asyncio.create_task(
        _auto_advance(game.state.current_question_index)
    )


@app.post("/api/advance")
async def advance(request: Request):
    slug, game = _get_game(request)
    await game.advance_phase()
    if game.state.phase == GamePhase.QUESTION_ACTIVE:
        _schedule_auto_advance(game)
    return {"phase": game.state.phase.value}


@app.post("/api/reset")
async def reset(request: Request):
    slug, game = _get_game(request)
    await game.reset()
    return {"status": "reset"}


# --- Dev server entry point ---


def main() -> None:
    import uvicorn

    uvicorn.run(
        "bayesian_quiz.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
