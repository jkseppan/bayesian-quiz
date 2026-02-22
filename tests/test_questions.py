"""Tests for quiz file parser."""

import pytest

from bayesian_quiz.questions import list_quizzes, load_quiz, parse_quiz_file

SAMPLE_QUIZ_TEXT = "Question: How old is Python?\nAnswer: 34.0\n"


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

    def test_slug_case_insensitive(self):
        qs_lower = load_quiz("sample")
        qs_upper = load_quiz("SAMPLE")
        qs_mixed = load_quiz("SaMpLe")
        assert [q.text for q in qs_lower] == [q.text for q in qs_upper]
        assert [q.text for q in qs_lower] == [q.text for q in qs_mixed]

    def test_missing_slug(self):
        with pytest.raises(FileNotFoundError, match="Quiz not found"):
            load_quiz("nonexistent_quiz_xyz")

    def test_load_from_env_var(self, monkeypatch):
        monkeypatch.setenv("QUIZ_ENVTEST", SAMPLE_QUIZ_TEXT)
        qs = load_quiz("envtest")
        assert len(qs) == 1
        assert qs[0].text == "How old is Python?"
        assert qs[0].answer == 34.0

    def test_env_var_slug_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("QUIZ_ENVTEST", SAMPLE_QUIZ_TEXT)
        assert load_quiz("ENVTEST")[0].answer == 34.0
        assert load_quiz("EnvTest")[0].answer == 34.0

    def test_env_var_takes_precedence_over_file(self, monkeypatch, tmp_path):
        override = "Question: Override\nAnswer: 99.0\n"
        monkeypatch.setenv("QUIZ_SAMPLE", override)
        qs = load_quiz("sample")
        assert qs[0].text == "Override"


class TestListQuizzes:
    def test_includes_sample(self):
        slugs = list_quizzes()
        assert "sample" in slugs

    def test_includes_env_var_quiz(self, monkeypatch):
        monkeypatch.setenv("QUIZ_MYQUIZ", SAMPLE_QUIZ_TEXT)
        assert "myquiz" in list_quizzes()

    def test_env_var_slug_is_lowercased(self, monkeypatch):
        monkeypatch.setenv("QUIZ_UPPERCASE", SAMPLE_QUIZ_TEXT)
        slugs = list_quizzes()
        assert "uppercase" in slugs
        assert "UPPERCASE" not in slugs

    def test_merges_env_and_files(self, monkeypatch):
        monkeypatch.setenv("QUIZ_ENVONLY", SAMPLE_QUIZ_TEXT)
        slugs = list_quizzes()
        assert "envonly" in slugs
        assert "sample" in slugs
