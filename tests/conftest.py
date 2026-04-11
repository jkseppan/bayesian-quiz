import os

os.environ.setdefault("QUIZMASTER_PASS", "test-password")

import pytest

from bayesian_quiz.state import GameManager, GamePhase


@pytest.fixture
def two_question_game() -> GameManager:
    from bayesian_quiz.state import Question
    return GameManager([
        Question(text="Q1", answer=100.0, scale=50.0),
        Question(text="Q2", answer=200.0, scale=100.0),
    ])


async def advance_to(gm: GameManager, target: GamePhase) -> None:
    phase_order = [
        GamePhase.LOBBY,
        GamePhase.INTRO,
        GamePhase.QUESTION_INTRO,
        GamePhase.QUESTION_ACTIVE,
        GamePhase.SHOW_DISTRIBUTION,
        GamePhase.REVEAL_ANSWER,
        GamePhase.QUESTION_SCORES,
        GamePhase.LEADERBOARD,
    ]
    while gm.state.phase != target:
        current_idx = phase_order.index(gm.state.phase)
        target_idx = phase_order.index(target)
        if current_idx >= target_idx:
            break
        await gm.advance_phase()
