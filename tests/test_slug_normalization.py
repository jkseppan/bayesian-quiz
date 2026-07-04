"""Tests that slugs are normalized to lowercase so case variants share a game."""

import pytest
from fastapi.testclient import TestClient

from bayesian_quiz.app import app
from bayesian_quiz.state import games


@pytest.fixture(autouse=True)
def _clear_registry():
    games.clear()
    yield
    games.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_case_variants_share_one_game(client):
    client.get("/play?SAMPLE")
    client.get("/play?sample")
    assert list(games.keys()) == ["sample"]


def test_mixed_case_normalized(client):
    client.get("/play?Sample")
    assert list(games.keys()) == ["sample"]


def test_invalid_slug_rejected(client):
    # Slug with disallowed characters must not create a game.
    resp = client.get("/play?bad!slug", follow_redirects=False)
    assert resp.status_code == 302
    assert games == {}
