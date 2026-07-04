"""Tests for idempotent /api/advance guarding against stale/double clicks."""

import pytest
from fastapi.testclient import TestClient

from bayesian_quiz.app import app
from bayesian_quiz.state import games

_AUTH = ("quizmaster", "test-password")


@pytest.fixture(autouse=True)
def _clear_registry():
    games.clear()
    yield
    games.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_stale_from_phase_does_not_advance(client):
    # First advance with no guard: lobby -> intro.
    r = client.post("/api/advance?sample", auth=_AUTH)
    assert r.json()["phase"] == "intro"

    # Stale click still thinks we are in lobby -> no-op.
    r = client.post("/api/advance?sample", data={"from_phase": "lobby"}, auth=_AUTH)
    assert r.json()["phase"] == "intro"


def test_correct_from_phase_advances(client):
    r = client.post("/api/advance?sample", auth=_AUTH)
    assert r.json()["phase"] == "intro"
    r = client.post(
        "/api/advance?sample", data={"from_phase": "intro", "from_slide": "0"}, auth=_AUTH
    )
    # Advancing intro from slide 0 moves to slide 1 (still intro phase).
    assert r.json()["phase"] == "intro"
    assert games["sample"].state.intro_slide == 1


def test_two_rapid_advances_move_one_phase(client):
    # Get to lobby state (fresh). Two rapid advances both carry from_phase=lobby.
    r1 = client.post("/api/advance?sample", data={"from_phase": "lobby"}, auth=_AUTH)
    r2 = client.post("/api/advance?sample", data={"from_phase": "lobby"}, auth=_AUTH)
    # First one advanced; second one is stale and no-ops.
    assert r1.json()["phase"] == "intro"
    assert r2.json()["phase"] == "intro"


def test_stale_from_slide_does_not_advance(client):
    # lobby -> intro (slide 0)
    client.post("/api/advance?sample", auth=_AUTH)
    # Advance intro slide 0 -> slide 1.
    client.post("/api/advance?sample", data={"from_phase": "intro", "from_slide": "0"}, auth=_AUTH)
    assert games["sample"].state.intro_slide == 1
    # A stale click still on slide 0 must no-op.
    client.post("/api/advance?sample", data={"from_phase": "intro", "from_slide": "0"}, auth=_AUTH)
    assert games["sample"].state.intro_slide == 1
