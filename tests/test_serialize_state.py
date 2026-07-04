"""Tests that _serialize_state does not leak upcoming question text over SSE."""

import pytest
from conftest import advance_to

from bayesian_quiz.app import _serialize_state
from bayesian_quiz.state import GameManager, GamePhase, Question


@pytest.fixture
def gm():
    # Question has an intro so QUESTION_INTRO is reachable.
    return GameManager([
        Question(text="Secret Q1", answer=100.0, scale=50.0, intro="Some intro text"),
    ])


@pytest.mark.anyio
async def test_question_hidden_in_lobby(gm):
    assert gm.state.phase == GamePhase.LOBBY
    assert _serialize_state(gm)["question"] is None


@pytest.mark.anyio
async def test_question_hidden_in_intro(gm):
    await advance_to(gm, GamePhase.INTRO)
    assert _serialize_state(gm)["question"] is None


@pytest.mark.anyio
async def test_question_hidden_in_question_intro(gm):
    await advance_to(gm, GamePhase.QUESTION_INTRO)
    assert gm.state.phase == GamePhase.QUESTION_INTRO
    assert _serialize_state(gm)["question"] is None


@pytest.mark.anyio
async def test_question_visible_in_question_active(gm):
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    payload = _serialize_state(gm)["question"]
    assert payload is not None
    assert payload["text"] == "Secret Q1"
