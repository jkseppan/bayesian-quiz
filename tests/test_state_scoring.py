"""Tests for scoring integration in GameManager."""

import pytest
from conftest import advance_to

from bayesian_quiz.state import Estimate, GameManager, GamePhase, Question


@pytest.fixture
def gm():
    return GameManager([
        Question(text="Q1", answer=100.0, scale=50.0),
        Question(text="Q2", answer=200.0, scale=100.0),
    ])


@pytest.mark.anyio
async def test_scores_populated_on_reveal(gm):
    await gm.add_participant("p1", "Alice")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    await gm.submit_estimate("p1", mu=100.0, sigma=5.0)
    await advance_to(gm, GamePhase.REVEAL_ANSWER)

    assert 0 in gm.state.participants["p1"].scores
    assert gm.state.participants["p1"].scores[0] > 0


@pytest.mark.anyio
async def test_no_score_without_estimate(gm):
    await gm.add_participant("p1", "Alice")
    await advance_to(gm, GamePhase.REVEAL_ANSWER)

    assert 0 not in gm.state.participants["p1"].scores
    assert gm.state.participants["p1"].total_score == 0


@pytest.mark.anyio
async def test_accurate_tight_beats_accurate_wide(gm):
    await gm.add_participant("tight", "Tight")
    await gm.add_participant("wide", "Wide")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    await gm.submit_estimate("tight", mu=100.0, sigma=1.0)
    await gm.submit_estimate("wide", mu=100.0, sigma=20.0)
    await advance_to(gm, GamePhase.REVEAL_ANSWER)

    tight_score = gm.state.participants["tight"].scores[0]
    wide_score = gm.state.participants["wide"].scores[0]
    assert tight_score > wide_score


@pytest.mark.anyio
async def test_overconfident_wrong_scores_low(gm):
    await gm.add_participant("p1", "Overconfident")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    await gm.submit_estimate("p1", mu=0.0, sigma=0.1)
    await advance_to(gm, GamePhase.REVEAL_ANSWER)

    assert gm.state.participants["p1"].scores[0] < 15


@pytest.mark.anyio
async def test_hedged_wrong_beats_overconfident_wrong(gm):
    gm.state.questions = [Question(text="Q1", answer=100.0, scale=200.0)]
    await gm.add_participant("hedged", "Hedged")
    await gm.add_participant("overconf", "Overconfident")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    await gm.submit_estimate("hedged", mu=70.0, sigma=40.0)
    await gm.submit_estimate("overconf", mu=70.0, sigma=0.1)
    await advance_to(gm, GamePhase.REVEAL_ANSWER)

    assert gm.state.participants["hedged"].scores[0] > gm.state.participants["overconf"].scores[0]


@pytest.mark.anyio
async def test_total_score_accumulates_across_questions(gm):
    await gm.add_participant("p1", "Alice")

    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    await gm.submit_estimate("p1", mu=100.0, sigma=5.0)
    await advance_to(gm, GamePhase.LEADERBOARD)

    q0_score = gm.state.participants["p1"].scores[0]
    assert q0_score > 0

    await gm.advance_phase()  # -> QUESTION_ACTIVE for Q2
    assert gm.state.phase == GamePhase.QUESTION_ACTIVE
    assert gm.state.current_question_index == 1

    await gm.submit_estimate("p1", mu=200.0, sigma=10.0)
    await advance_to(gm, GamePhase.REVEAL_ANSWER)

    assert 1 in gm.state.participants["p1"].scores
    assert gm.state.participants["p1"].total_score == pytest.approx(
        q0_score + gm.state.participants["p1"].scores[1]
    )


@pytest.mark.anyio
async def test_scores_not_overwritten_on_second_reveal(gm):
    await gm.add_participant("p1", "Alice")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    await gm.submit_estimate("p1", mu=100.0, sigma=5.0)
    await advance_to(gm, GamePhase.REVEAL_ANSWER)

    score_first = gm.state.participants["p1"].scores[0]

    gm.state.participants["p1"].estimates[0] = Estimate(mu=0.0, sigma=0.1)
    gm._score_current_question()
    score_second = gm.state.participants["p1"].scores[0]

    assert score_second == score_first


@pytest.mark.anyio
async def test_question_intro_phase_when_intro_present():
    gm = GameManager([
        Question(text="Q1", answer=100.0, intro="Some context"),
        Question(text="Q2", answer=200.0),
    ])
    await gm.add_participant("p1", "Alice")
    await advance_to(gm, GamePhase.INTRO)
    # Advance past intro slides to first question — should land on QUESTION_INTRO
    while gm.state.phase == GamePhase.INTRO:
        await gm.advance_phase()
    assert gm.state.phase == GamePhase.QUESTION_INTRO
    assert gm.state.question_started_at is None

    await gm.advance_phase()
    assert gm.state.phase == GamePhase.QUESTION_ACTIVE
    assert gm.state.question_started_at is not None


@pytest.mark.anyio
async def test_no_question_intro_without_intro_field():
    gm = GameManager([
        Question(text="Q1", answer=100.0),
    ])
    await advance_to(gm, GamePhase.INTRO)
    while gm.state.phase == GamePhase.INTRO:
        await gm.advance_phase()
    assert gm.state.phase == GamePhase.QUESTION_ACTIVE


@pytest.mark.anyio
async def test_next_question_with_intro():
    gm = GameManager([
        Question(text="Q1", answer=100.0),
        Question(text="Q2", answer=200.0, intro="Context for Q2"),
    ])
    await gm.add_participant("p1", "Alice")
    await advance_to(gm, GamePhase.QUESTION_ACTIVE)
    await gm.submit_estimate("p1", mu=100.0, sigma=5.0)
    await advance_to(gm, GamePhase.LEADERBOARD)
    await gm.advance_phase()
    assert gm.state.phase == GamePhase.QUESTION_INTRO
    assert gm.state.current_question_index == 1
