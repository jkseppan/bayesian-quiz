"""Quiz file parser — loads questions from RFC 822-like text files."""

import re
from pathlib import Path

from bayesian_quiz.state import Question

QUIZZES_DIR = Path(__file__).parent.parent.parent / "quizzes"

_SAFE_SLUG = re.compile(r"^[a-z0-9_-]{1,64}$")


def parse_quiz_file(text: str) -> list[Question]:
    """Parse quiz file text into Question objects.

    Format: RFC 822-like headers separated by blank lines.
    Required fields: Question, Answer
    Optional fields: Unit, Scale, Factoid
    """
    questions: list[Question] = []
    for block in _split_blocks(text):
        fields = _parse_block(block)
        if not fields:
            continue
        if "question" not in fields:
            raise ValueError(f"Missing 'Question' field in block: {block!r}")
        if "answer" not in fields:
            raise ValueError(f"Missing 'Answer' field in block: {block!r}")
        try:
            answer = float(fields["answer"])
        except ValueError:
            raise ValueError(f"Bad number for Answer: {fields['answer']!r}")
        scale = 10.0
        if "scale" in fields:
            try:
                scale = float(fields["scale"])
            except ValueError:
                raise ValueError(f"Bad number for Scale: {fields['scale']!r}")
        questions.append(Question(
            text=fields["question"],
            answer=answer,
            unit=fields.get("unit", ""),
            fun_fact=fields.get("factoid", ""),
            scale=scale,
        ))
    return questions


def _split_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == "":
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _parse_block(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    current_value_lines: list[str] = []

    for line in block.splitlines():
        if ":" in line and not line[0].isspace():
            if current_key is not None:
                fields[current_key] = " ".join(current_value_lines).strip()
            key, _, value = line.partition(":")
            current_key = key.strip().lower()
            current_value_lines = [value.strip()]
        elif current_key is not None:
            current_value_lines.append(line.strip())

    if current_key is not None:
        fields[current_key] = " ".join(current_value_lines).strip()

    return fields


def load_quiz(slug: str) -> list[Question]:
    if not _SAFE_SLUG.match(slug):
        raise FileNotFoundError(f"Quiz not found: {slug}")
    path = QUIZZES_DIR / f"{slug}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Quiz not found: {slug}")
    return parse_quiz_file(path.read_text())


def list_quizzes() -> list[str]:
    if not QUIZZES_DIR.is_dir():
        return []
    return sorted(p.stem for p in QUIZZES_DIR.glob("*.txt"))
