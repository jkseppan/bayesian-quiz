"""FastAPI application for Bayesian Quiz."""

import asyncio
import io
import json
import os
import secrets
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import qrcode
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .questions import list_quizzes
from .state import (
    GRACE_PERIOD_SECONDS,
    QUESTION_DURATION_SECONDS,
    GameManager,
    GamePhase,
    games,
    get_or_create_game,
)

app = FastAPI(title="Bayesian Quiz")

_basic = HTTPBasic()
QUIZMASTER_USER = os.environ.get("QUIZMASTER_USER", "quizmaster")
QUIZMASTER_PASS = os.environ.get("QUIZMASTER_PASS")
if not QUIZMASTER_PASS:
    raise RuntimeError("QUIZMASTER_PASS environment variable must be set")


def _require_quizmaster(credentials: Annotated[HTTPBasicCredentials, Depends(_basic)]):
    user_ok = secrets.compare_digest(credentials.username.encode(), QUIZMASTER_USER.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), QUIZMASTER_PASS.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.on_event("shutdown")
async def _shutdown():
    for gm in games.values():
        await gm.shutdown()


TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def _fmt_number(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}".replace(",", "\u202f")
    return f"{value:,.2f}".replace(",", "\u202f")


templates.env.filters["fmt_number"] = _fmt_number

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

MOCKUPS_DIR = Path(__file__).parent.parent.parent / "mockups"
if MOCKUPS_DIR.exists():
    app.mount("/mockups", StaticFiles(directory=MOCKUPS_DIR, html=True), name="mockups")


def _get_slug(request: Request) -> str | None:
    """Extract slug from query string: the first key with an empty value (?sample)."""
    for key, value in request.query_params.items():
        if value == "":
            return key
    return None


class _BadSlug(Exception):
    pass


def _get_game(request: Request) -> tuple[str, GameManager]:
    slug = _get_slug(request)
    if not slug:
        raise _BadSlug("Missing quiz slug")
    try:
        return slug, get_or_create_game(slug)
    except FileNotFoundError:
        raise _BadSlug(f"Quiz not found: {slug}") from None


@app.exception_handler(_BadSlug)
async def _bad_slug_handler(request: Request, exc: _BadSlug):
    return RedirectResponse(url="/", status_code=302)


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
    _slug, game = _get_game(request)
    try:
        queue = game.subscribe()
    except ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many active connections",
        ) from None

    async def event_generator():
        try:
            yield "retry: 500\n"
            yield _sse_message("connected", json.dumps({"phase": game.state.phase.value}))

            while not game._shutting_down:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=5.0)
                    if event is None:
                        break
                    yield _sse_message(event, json.dumps(_serialize_state(game)))
                except TimeoutError:
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
    return templates.TemplateResponse(request, "index.html", {})


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


@app.get("/control", response_class=HTMLResponse, dependencies=[Depends(_require_quizmaster)])
async def quizmaster(request: Request):
    slug = _get_slug(request)
    if not slug:
        return templates.TemplateResponse(
            request, "control_pick.html", {"quizzes": list_quizzes()}
        )
    try:
        game = get_or_create_game(slug)
    except FileNotFoundError:
        return templates.TemplateResponse(
            request,
            "control_pick.html",
            {"quizzes": list_quizzes(), "error": f"Quiz not found: {slug}"},
        )
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


@app.get("/fragments/estimate-count", response_class=HTMLResponse)
async def fragment_estimate_count(request: Request):
    _slug, game = _get_game(request)
    s = game.state
    n = len(s.get_current_estimates())
    total = len(s.participants)
    return HTMLResponse(
        f'<span class="font-mono text-2xl font-bold text-emerald-600">{n}</span>'
        f" / {total} answered"
    )


@app.get("/fragments/player-count", response_class=HTMLResponse)
async def fragment_player_count(request: Request):
    _slug, game = _get_game(request)
    n = len(game.state.participants)
    return HTMLResponse(
        f'<span class="font-mono text-3xl font-bold text-indigo-600">{n}</span>'
        f" players joined"
    )


@app.get("/fragments/nickname-arena", response_class=HTMLResponse)
async def fragment_nickname_arena(request: Request):
    slug, game = _get_game(request)
    return templates.TemplateResponse(
        request,
        "fragments/nickname_arena.html",
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


@app.get(
    "/fragments/quizmaster",
    response_class=HTMLResponse,
    dependencies=[Depends(_require_quizmaster)],
)
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
    response.set_cookie(key="participant_id", value=participant_id, httponly=True, samesite="lax")
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


@app.post("/api/advance", dependencies=[Depends(_require_quizmaster)])
async def advance(request: Request):
    _slug, game = _get_game(request)
    await game.advance_phase()
    if game.state.phase == GamePhase.QUESTION_ACTIVE:
        _schedule_auto_advance(game)
    return {"phase": game.state.phase.value}


@app.post("/api/start-quiz", dependencies=[Depends(_require_quizmaster)])
async def start_quiz(request: Request):
    _slug, game = _get_game(request)
    await game.start_quiz()
    _schedule_auto_advance(game)
    return {"phase": game.state.phase.value}


@app.post("/api/back", dependencies=[Depends(_require_quizmaster)])
async def back(request: Request):
    _slug, game = _get_game(request)
    await game.back_slide()
    return {"phase": game.state.phase.value, "intro_slide": game.state.intro_slide}


@app.post("/api/reset", dependencies=[Depends(_require_quizmaster)])
async def reset(request: Request):
    _slug, game = _get_game(request)
    await game.reset()
    return {"status": "reset"}


JOIN_DOMAIN = os.environ.get("JOIN_DOMAIN", "pydata.win")


@app.get("/api/qr")
async def qr_code(request: Request):
    slug = _get_slug(request)
    if not slug:
        return Response(status_code=404)
    url = f"https://{JOIN_DOMAIN}/?{slug}"
    img = qrcode.make(url, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# --- Dev server entry point ---


def main() -> None:
    import uvicorn

    uvicorn.run(
        "bayesian_quiz.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
