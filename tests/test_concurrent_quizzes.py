"""Tests for concurrent quizzes running independently in different phases."""

import pytest
from conftest import advance_to

from bayesian_quiz.state import GameManager, GamePhase, Question


def make_game() -> GameManager:
    return GameManager([
        Question(text="Q1", answer=100.0, scale=50.0),
        Question(text="Q2", answer=200.0, scale=100.0),
    ])


@pytest.mark.anyio
async def test_two_games_in_different_phases():
    game_a = make_game()
    game_b = make_game()

    await advance_to(game_a, GamePhase.QUESTION_ACTIVE)
    assert game_a.state.phase == GamePhase.QUESTION_ACTIVE
    assert game_b.state.phase == GamePhase.LOBBY


@pytest.mark.anyio
async def test_advancing_one_game_does_not_affect_other():
    game_a = make_game()
    game_b = make_game()

    await game_a.add_participant("a1", "Alice")
    await game_b.add_participant("b1", "Bob")

    await advance_to(game_a, GamePhase.QUESTION_ACTIVE)
    await game_a.submit_estimate("a1", mu=100.0, sigma=5.0)
    await advance_to(game_a, GamePhase.REVEAL_ANSWER)

    assert game_a.state.phase == GamePhase.REVEAL_ANSWER
    assert game_b.state.phase == GamePhase.LOBBY
    assert "a1" not in game_b.state.participants
    assert "b1" not in game_a.state.participants


@pytest.mark.anyio
async def test_participants_isolated_between_games():
    game_a = make_game()
    game_b = make_game()

    await game_a.add_participant("p1", "Alice")
    await game_b.add_participant("p1", "Alice")

    assert len(game_a.state.participants) == 1
    assert len(game_b.state.participants) == 1
    assert game_a.state.participants["p1"] is not game_b.state.participants["p1"]


@pytest.mark.anyio
async def test_estimates_isolated_between_games():
    game_a = make_game()
    game_b = make_game()

    await game_a.add_participant("p1", "Alice")
    await game_b.add_participant("p1", "Bob")

    await advance_to(game_a, GamePhase.QUESTION_ACTIVE)
    await advance_to(game_b, GamePhase.QUESTION_ACTIVE)

    await game_a.submit_estimate("p1", mu=50.0, sigma=10.0)
    await game_b.submit_estimate("p1", mu=999.0, sigma=1.0)

    assert game_a.state.participants["p1"].estimates[0].mu == 50.0
    assert game_b.state.participants["p1"].estimates[0].mu == 999.0


@pytest.mark.anyio
async def test_scores_isolated_between_games():
    game_a = make_game()
    game_b = make_game()

    await game_a.add_participant("p1", "Alice")
    await game_b.add_participant("p1", "Bob")

    await advance_to(game_a, GamePhase.QUESTION_ACTIVE)
    await game_a.submit_estimate("p1", mu=100.0, sigma=5.0)
    await advance_to(game_a, GamePhase.REVEAL_ANSWER)

    await advance_to(game_b, GamePhase.QUESTION_ACTIVE)
    await game_b.submit_estimate("p1", mu=0.0, sigma=0.1)
    await advance_to(game_b, GamePhase.REVEAL_ANSWER)

    score_a = game_a.state.participants["p1"].scores[0]
    score_b = game_b.state.participants["p1"].scores[0]
    assert score_a > 0
    assert score_a > score_b


@pytest.mark.anyio
async def test_broadcast_isolated_between_games():
    game_a = make_game()
    game_b = make_game()

    queue_a = game_a.subscribe()
    queue_b = game_b.subscribe()

    await game_a.advance_phase()

    assert queue_a.qsize() == 1
    assert queue_b.qsize() == 0

    game_a.unsubscribe(queue_a)
    game_b.unsubscribe(queue_b)


@pytest.mark.anyio
async def test_reset_one_game_does_not_affect_other():
    game_a = make_game()
    game_b = make_game()

    await game_a.add_participant("p1", "Alice")
    await game_b.add_participant("p1", "Bob")
    await advance_to(game_a, GamePhase.QUESTION_ACTIVE)
    await advance_to(game_b, GamePhase.QUESTION_ACTIVE)

    await game_a.reset()

    assert game_a.state.phase == GamePhase.LOBBY
    assert len(game_a.state.participants) == 0
    assert game_b.state.phase == GamePhase.QUESTION_ACTIVE
    assert len(game_b.state.participants) == 1


@pytest.mark.anyio
async def test_games_on_different_questions():
    game_a = make_game()
    game_b = make_game()

    await game_a.add_participant("p1", "Alice")
    await game_b.add_participant("p1", "Bob")

    await advance_to(game_a, GamePhase.QUESTION_ACTIVE)
    await game_a.submit_estimate("p1", mu=100.0, sigma=5.0)
    await advance_to(game_a, GamePhase.LEADERBOARD)
    await game_a.advance_phase()
    assert game_a.state.current_question_index == 1

    await advance_to(game_b, GamePhase.QUESTION_ACTIVE)
    assert game_b.state.current_question_index == 0

    assert game_a.state.current_question.text == "Q2"
    assert game_b.state.current_question.text == "Q1"
