"""Tests for quiz file parser."""

import pytest

from bayesian_quiz.questions import parse_quiz_file, load_quiz, list_quizzes


class TestParseQuizFile:
    def test_single_question(self):
        text = "Question: How old is Python?\nAnswer: 34.0\n"
        qs = parse_quiz_file(text)
        assert len(qs) == 1
        assert qs[0].text == "How old is Python?"
        assert qs[0].answer == 34.0

    def test_all_fields(self):
        text = (
            "Question: How old is Python?\n"
            "Answer: 34.0\n"
            "Unit: years\n"
            "Scale: 10.0\n"
            "Factoid: Created by Guido.\n"
        )
        qs = parse_quiz_file(text)
        assert qs[0].unit == "years"
        assert qs[0].scale == 10.0
        assert qs[0].fun_fact == "Created by Guido."

    def test_multiple_questions(self):
        text = (
            "Question: Q1\nAnswer: 1.0\n\n"
            "Question: Q2\nAnswer: 2.0\n"
        )
        qs = parse_quiz_file(text)
        assert len(qs) == 2
        assert qs[1].answer == 2.0

    def test_defaults(self):
        text = "Question: Q1\nAnswer: 42.0\n"
        qs = parse_quiz_file(text)
        assert qs[0].unit == ""
        assert qs[0].scale == 10.0
        assert qs[0].fun_fact == ""

    def test_missing_question_field(self):
        text = "Answer: 42.0\n"
        with pytest.raises(ValueError, match="Missing 'Question'"):
            parse_quiz_file(text)

    def test_missing_answer_field(self):
        text = "Question: What?\n"
        with pytest.raises(ValueError, match="Missing 'Answer'"):
            parse_quiz_file(text)

    def test_bad_answer_number(self):
        text = "Question: What?\nAnswer: not-a-number\n"
        with pytest.raises(ValueError, match="Bad number for Answer"):
            parse_quiz_file(text)

    def test_bad_scale_number(self):
        text = "Question: What?\nAnswer: 42.0\nScale: nope\n"
        with pytest.raises(ValueError, match="Bad number for Scale"):
            parse_quiz_file(text)

    def test_empty_file(self):
        assert parse_quiz_file("") == []
        assert parse_quiz_file("\n\n\n") == []

    def test_multiline_factoid(self):
        text = (
            "Question: Q1\n"
            "Answer: 42.0\n"
            "Factoid: This is a long factoid\n"
            " that spans multiple lines.\n"
        )
        qs = parse_quiz_file(text)
        assert qs[0].fun_fact == "This is a long factoid that spans multiple lines."


class TestLoadQuiz:
    def test_load_sample(self):
        qs = load_quiz("sample")
        assert len(qs) == 3
        assert qs[0].text == "How many years old is Python today?"

    def test_missing_slug(self):
        with pytest.raises(FileNotFoundError, match="Quiz not found"):
            load_quiz("nonexistent_quiz_xyz")


class TestListQuizzes:
    def test_includes_sample(self):
        slugs = list_quizzes()
        assert "sample" in slugs
