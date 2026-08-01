"""Tests for the phone-friendly participant fragment content.

These drive the game via GameManager directly (registered in the shared
``games`` registry) and hit the real FastAPI routes with TestClient so the
Jinja fragment is rendered exactly as it would be in production.
"""

import pytest
from fastapi.testclient import TestClient

from bayesian_quiz.app import app
from bayesian_quiz.state import GameManager, GamePhase, Question, games

DISTINCTIVE_ANSWER = "123.456"

SLUG = "frag-test"


def make_game() -> GameManager:
    return GameManager([
        Question(
            text="What is the distinctive answer?",
            answer=123.456,
            unit="widgets",
            fun_fact="The distinctive fun fact appears here.",
            scale=10.0,
        ),
        Question(text="Q2", answer=200.0, scale=100.0),
    ])


@pytest.fixture(autouse=True)
def _register_game():
    games[SLUG] = make_game()
    yield
    games.pop(SLUG, None)


@pytest.fixture
def client():
    return TestClient(app)


def _register(client: TestClient, nickname: str) -> str:
    """Register a participant, return their participant_id cookie value."""
    resp = client.post(f"/api/register?{SLUG}", data={"nickname": nickname})
    assert resp.status_code == 200
    pid = resp.cookies.get("participant_id")
    assert pid
    return pid


def _fragment(client: TestClient, pid: str) -> str:
    resp = client.get(f"/fragments/participant?{SLUG}", cookies={"participant_id": pid})
    assert resp.status_code == 200
    return resp.text


class TestIntroSlides:
    @pytest.mark.anyio
    async def test_slide_zero_mentions_mu_sigma(self, client: TestClient):
        gm = games[SLUG]
        _pid = _register(client, "Alice")
        await gm.advance_phase()  # LOBBY -> INTRO
        assert gm.state.phase == GamePhase.INTRO
        assert gm.state.intro_slide == 0

        html = _fragment(client, _pid)
        assert "Mean" in html
        assert "Std. deviation" in html
        assert "&#956;" in html or "μ" in html
        assert "&#963;" in html or "σ" in html

    @pytest.mark.anyio
    async def test_advancing_slide_changes_content(self, client: TestClient):
        gm = games[SLUG]
        _pid = _register(client, "Alice")
        await gm.advance_phase()  # -> INTRO slide 0
        html_slide0 = _fragment(client, _pid)

        await gm.advance_phase()  # -> INTRO slide 1
        assert gm.state.intro_slide == 1
        html_slide1 = _fragment(client, _pid)

        assert html_slide0 != html_slide1
        assert "Ultimate Answer to Life" in html_slide1
        assert "Ultimate Answer to Life" not in html_slide0


class TestAnswerLeakage:
    @pytest.mark.anyio
    async def test_show_distribution_hides_answer_but_has_chart(self, client: TestClient):
        gm = games[SLUG]
        pid = _register(client, "Alice")
        await gm.start_quiz()  # -> QUESTION_ACTIVE (no intro on Q1)
        assert gm.state.phase == GamePhase.QUESTION_ACTIVE
        await gm.submit_estimate(pid, mu=100.0, sigma=5.0)
        await gm.advance_phase()  # -> SHOW_DISTRIBUTION
        assert gm.state.phase == GamePhase.SHOW_DISTRIBUTION

        html = _fragment(client, pid)
        assert "renderDistChart" in html
        assert "participant-dist-chart" in html
        assert DISTINCTIVE_ANSWER not in html


class TestRevealAnswer:
    @pytest.mark.anyio
    async def test_reveal_shows_chart_answer_and_factoid(self, client: TestClient):
        gm = games[SLUG]
        pid = _register(client, "Alice")
        await gm.start_quiz()
        await gm.submit_estimate(pid, mu=100.0, sigma=5.0)
        await gm.advance_phase()  # SHOW_DISTRIBUTION
        await gm.advance_phase()  # REVEAL_ANSWER
        assert gm.state.phase == GamePhase.REVEAL_ANSWER

        html = _fragment(client, pid)
        assert "renderDistChart" in html
        assert "participant-reveal-chart" in html
        assert DISTINCTIVE_ANSWER in html
        assert "The distinctive fun fact appears here." in html


class TestQuestionScores:
    @pytest.mark.anyio
    async def test_top_scorers_nicknames_shown(self, client: TestClient):
        gm = games[SLUG]
        pid_a = _register(client, "Alice")
        pid_b = _register(client, "Bob")
        await gm.start_quiz()
        await gm.submit_estimate(pid_a, mu=123.456, sigma=1.0)
        await gm.submit_estimate(pid_b, mu=50.0, sigma=20.0)
        await gm.advance_phase()  # SHOW_DISTRIBUTION
        await gm.advance_phase()  # REVEAL_ANSWER (scores computed here)
        await gm.advance_phase()  # QUESTION_SCORES
        assert gm.state.phase == GamePhase.QUESTION_SCORES

        html = _fragment(client, pid_a)
        assert "Alice" in html
        assert "Bob" in html


class TestEndPhase:
    @pytest.mark.anyio
    async def test_final_leaderboard_shows_other_players(self, client: TestClient):
        gm = games[SLUG]
        pid_a = _register(client, "Alice")
        pid_b = _register(client, "Bob")
        await gm.start_quiz()
        await gm.submit_estimate(pid_a, mu=123.456, sigma=1.0)
        await gm.submit_estimate(pid_b, mu=50.0, sigma=20.0)
        await gm.advance_phase()  # SHOW_DISTRIBUTION (Q1)
        await gm.advance_phase()  # REVEAL_ANSWER (Q1)
        await gm.advance_phase()  # QUESTION_SCORES (Q1)
        await gm.advance_phase()  # LEADERBOARD (Q1)
        await gm.advance_phase()  # -> Q2 QUESTION_ACTIVE
        assert gm.state.current_question_index == 1
        await gm.submit_estimate(pid_a, mu=200.0, sigma=1.0)
        await gm.submit_estimate(pid_b, mu=200.0, sigma=1.0)
        await gm.advance_phase()  # SHOW_DISTRIBUTION (Q2)
        await gm.advance_phase()  # REVEAL_ANSWER (Q2)
        await gm.advance_phase()  # QUESTION_SCORES (Q2)
        await gm.advance_phase()  # LEADERBOARD (Q2)
        await gm.advance_phase()  # -> END
        assert gm.state.phase == GamePhase.END

        html = _fragment(client, pid_a)
        assert "Alice" in html
        assert "Bob" in html
        assert "Game Over" in html
