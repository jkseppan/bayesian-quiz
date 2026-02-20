"""Tests for multi-game registry."""

import pytest

from bayesian_quiz.state import get_or_create_game, games


@pytest.fixture(autouse=True)
def _clear_registry():
    games.clear()
    yield
    games.clear()


def test_creates_game_for_slug():
    gm = get_or_create_game("sample")
    assert len(gm.state.questions) == 3
    assert "sample" in games


def test_returns_same_instance():
    gm1 = get_or_create_game("sample")
    gm2 = get_or_create_game("sample")
    assert gm1 is gm2


def test_missing_quiz_raises():
    with pytest.raises(FileNotFoundError):
        get_or_create_game("nonexistent_quiz_xyz")
