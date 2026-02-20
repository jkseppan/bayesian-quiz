"""Game state management for Bayesian Quiz."""

import re
import time
import unicodedata
from enum import Enum
from dataclasses import dataclass, field
import asyncio

from bayesian_quiz.scoring import crps_normal, crps_to_points

QUESTION_DURATION_SECONDS = 30
_WHITESPACE_RUN = re.compile(r"\s+")


def sanitize_nickname(raw: str) -> str:
    """Normalize and sanitize a nickname.

    NFKC normalization collapses fullwidth/compatibility characters.
    Stripping Unicode category Cf removes zero-width chars, RTL/LTR marks,
    directional overrides, and other invisible format characters.
    """
    normalized = unicodedata.normalize("NFKC", raw)
    cleaned = "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf")
    return _WHITESPACE_RUN.sub(" ", cleaned).strip()
GRACE_PERIOD_SECONDS = 1


class GamePhase(str, Enum):
    """The current phase of the quiz."""

    LOBBY = "lobby"
    QUESTION_ACTIVE = "question_active"
    SHOW_DISTRIBUTION = "show_distribution"
    REVEAL_ANSWER = "reveal_answer"
    QUESTION_SCORES = "question_scores"
    LEADERBOARD = "leaderboard"
    END = "end"


@dataclass
class Estimate:
    """A participant's estimate for a question."""

    mu: float  # Mean estimate
    sigma: float  # Standard deviation (uncertainty)


@dataclass
class Participant:
    """A quiz participant."""

    id: str
    nickname: str
    scores: dict[int, float] = field(default_factory=dict)  # question_index -> score
    estimates: dict[int, Estimate] = field(default_factory=dict)  # question_index -> estimate

    @property
    def total_score(self) -> float:
        return sum(self.scores.values())


@dataclass
class Question:
    """A quiz question."""

    text: str
    answer: float
    unit: str = ""
    fun_fact: str = ""
    scale: float = 10.0


@dataclass
class GameState:
    """The complete state of a quiz game."""

    phase: GamePhase = GamePhase.LOBBY
    questions: list[Question] = field(default_factory=list)
    current_question_index: int = 0
    participants: dict[str, Participant] = field(default_factory=dict)
    question_started_at: float | None = None
    question_deadline: float | None = None

    @property
    def seconds_remaining(self) -> int | None:
        if self.phase != GamePhase.QUESTION_ACTIVE or self.question_started_at is None:
            return None
        elapsed = time.monotonic() - self.question_started_at
        return max(0, int(QUESTION_DURATION_SECONDS - elapsed))

    @property
    def current_question(self) -> Question | None:
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    def get_current_estimates(self) -> list[Estimate]:
        """Get all estimates for the current question."""
        return [
            p.estimates[self.current_question_index]
            for p in self.participants.values()
            if self.current_question_index in p.estimates
        ]

    def get_question_results(self) -> list[dict]:
        """Get per-participant results for the current question, sorted by points descending."""
        qi = self.current_question_index
        question = self.current_question
        if question is None:
            return []
        results = []
        for p in self.participants.values():
            if qi not in p.estimates:
                continue
            est = p.estimates[qi]
            crps = crps_normal(est.mu, est.sigma, question.answer)
            points = p.scores.get(qi, 0.0)
            results.append({
                "nickname": p.nickname,
                "participant_id": p.id,
                "mu": est.mu,
                "sigma": est.sigma,
                "crps": crps,
                "points": points,
            })
        results.sort(key=lambda r: r["points"], reverse=True)
        return results


class GameManager:
    """Manages game state and broadcasts updates to connected clients."""

    def __init__(self, questions: list[Question]) -> None:
        self.state = GameState(questions=list(questions))
        self._subscribers: list[asyncio.Queue[str]] = []
        self._auto_advance_task: asyncio.Task | None = None

    def subscribe(self) -> asyncio.Queue[str]:
        """Subscribe to state updates. Returns a queue that receives update events."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        """Unsubscribe from state updates."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def broadcast(self, event: str = "state_update") -> None:
        """Broadcast an event to all subscribers."""
        for queue in self._subscribers:
            await queue.put(event)

    async def shutdown(self) -> None:
        """Signal all subscribers to disconnect."""
        for queue in self._subscribers:
            await queue.put(None)

    async def add_participant(self, participant_id: str, nickname: str) -> Participant:
        """Add a new participant to the game."""
        nickname = sanitize_nickname(nickname)
        if not nickname:
            raise ValueError("Nickname cannot be empty")
        existing = {p.nickname.casefold() for p in self.state.participants.values()}
        if nickname.casefold() in existing:
            raise ValueError("Nickname already taken")
        participant = Participant(id=participant_id, nickname=nickname)
        self.state.participants[participant_id] = participant
        await self.broadcast("participant_joined")
        return participant

    async def submit_estimate(
        self, participant_id: str, mu: float, sigma: float
    ) -> None:
        """Submit an estimate for the current question."""
        if participant_id not in self.state.participants:
            raise ValueError("Participant not found")
        if self.state.phase != GamePhase.QUESTION_ACTIVE:
            raise ValueError("Not accepting estimates")
        if self.state.question_started_at is not None:
            elapsed = time.monotonic() - self.state.question_started_at
            if elapsed > QUESTION_DURATION_SECONDS + GRACE_PERIOD_SECONDS:
                raise ValueError("Time expired")

        estimate = Estimate(mu=mu, sigma=sigma)
        self.state.participants[participant_id].estimates[
            self.state.current_question_index
        ] = estimate
        await self.broadcast("estimate_submitted")

    async def advance_phase(self) -> None:
        """Advance to the next phase in the quiz flow."""
        transitions = {
            GamePhase.LOBBY: GamePhase.QUESTION_ACTIVE,
            GamePhase.QUESTION_ACTIVE: GamePhase.SHOW_DISTRIBUTION,
            GamePhase.SHOW_DISTRIBUTION: GamePhase.REVEAL_ANSWER,
            GamePhase.REVEAL_ANSWER: GamePhase.QUESTION_SCORES,
            GamePhase.QUESTION_SCORES: GamePhase.LEADERBOARD,
            GamePhase.LEADERBOARD: self._next_question_or_end,
        }

        next_phase = transitions.get(self.state.phase)
        if callable(next_phase):
            next_phase = next_phase()
        if next_phase:
            if next_phase == GamePhase.REVEAL_ANSWER:
                self._score_current_question()
            self.state.phase = next_phase
            if next_phase == GamePhase.QUESTION_ACTIVE:
                self.state.question_started_at = time.monotonic()
                self.state.question_deadline = time.time() + QUESTION_DURATION_SECONDS
            else:
                self.state.question_started_at = None
                self.state.question_deadline = None
            await self.broadcast("phase_changed")

    def _score_current_question(self) -> None:
        question = self.state.current_question
        if question is None:
            return
        qi = self.state.current_question_index
        for participant in self.state.participants.values():
            if qi not in participant.estimates:
                continue
            est = participant.estimates[qi]
            crps = crps_normal(est.mu, est.sigma, question.answer)
            participant.scores[qi] = crps_to_points(crps, question.scale)

    def _next_question_or_end(self) -> GamePhase:
        """Move to next question or end the game."""
        if self.state.current_question_index < len(self.state.questions) - 1:
            self.state.current_question_index += 1
            return GamePhase.QUESTION_ACTIVE
        return GamePhase.END

    async def reset(self) -> None:
        """Reset the game to initial state, keeping the same questions."""
        questions = self.state.questions
        self.state = GameState(questions=questions)
        await self.broadcast("phase_changed")


games: dict[str, GameManager] = {}


def get_or_create_game(slug: str) -> GameManager:
    if slug not in games:
        from bayesian_quiz.questions import load_quiz
        games[slug] = GameManager(load_quiz(slug))
    return games[slug]
