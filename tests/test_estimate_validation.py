"""Tests for estimate validation at submission time (state + API level)."""

import math

import pytest
from conftest import advance_to
from fastapi.testclient import TestClient

from bayesian_quiz.app import app
from bayesian_quiz.state import GameManager, GamePhase, Question, games, get_or_create_game


@pytest.fixture
def gm():
    return GameManager([
        Question(text="Q1", answer=100.0, scale=50.0),
        Question(text="Q2", answer=200.0, scale=100.0),
    ])


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mu", "sigma"),
    [
        (100.0, 0.0),
        (100.0, -1.0),
        (math.nan, 5.0),
        (100.0, math.inf),
    ],
)
async def test_invalid_estimate_rejected_and_not_stored(gm, mu, sigma):
    await gm.add_participant("p1", "Alice")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    with pytest.raises(ValueError, match="must be"):
        await gm.submit_estimate("p1", mu=mu, sigma=sigma)
    assert 0 not in gm.state.participants["p1"].estimates


@pytest.mark.anyio
async def test_game_survives_rejected_estimate_through_reveal(gm):
    """A player whose sigma=0 was rejected must not brick advance_phase."""
    await gm.add_participant("p1", "Alice")
    await gm.add_participant("p2", "Bob")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)

    with pytest.raises(ValueError, match="must be"):
        await gm.submit_estimate("p1", mu=100.0, sigma=0.0)
    await gm.submit_estimate("p2", mu=110.0, sigma=5.0)

    # Should advance cleanly through scoring without crps_normal blowing up.
    await advance_to(gm, GamePhase.REVEAL_ANSWER)
    assert gm.state.phase == GamePhase.REVEAL_ANSWER
    assert 0 not in gm.state.participants["p1"].scores
    assert gm.state.participants["p2"].scores[0] > 0


class TestEstimateAPI:
    @pytest.fixture(autouse=True)
    def _game(self):
        games.clear()
        yield
        games.clear()

    def _register_client(self) -> TestClient:
        import asyncio

        client = TestClient(app)
        resp = client.post("/api/register?sample", data={"nickname": "Alice"})
        assert resp.status_code == 200
        # Drive the game to QUESTION_ACTIVE so estimates are accepted.
        game = get_or_create_game("sample")
        asyncio.run(advance_to(game, GamePhase.QUESTION_ACTIVE))
        return client

    @pytest.mark.parametrize(
        "data",
        [
            {"mu": "100", "sigma": "0"},
            {"mu": "nan", "sigma": "5"},
        ],
    )
    def test_bad_estimate_returns_400(self, data):
        client = self._register_client()
        resp = client.post("/api/estimate?sample", data=data)
        assert resp.status_code == 400
