import pytest

from bayesian_quiz.app import _load_quizmaster_pass


def test_env_var_takes_precedence(monkeypatch, tmp_path):
    pass_file = tmp_path / "p"
    pass_file.write_text("from-file\n")
    monkeypatch.setenv("QUIZMASTER_PASS", "from-env")
    monkeypatch.setenv("QUIZMASTER_PASS_FILE", str(pass_file))
    assert _load_quizmaster_pass() == "from-env"


def test_falls_back_to_file(monkeypatch, tmp_path):
    pass_file = tmp_path / "p"
    pass_file.write_text("secret-from-file\n")
    monkeypatch.delenv("QUIZMASTER_PASS", raising=False)
    monkeypatch.setenv("QUIZMASTER_PASS_FILE", str(pass_file))
    assert _load_quizmaster_pass() == "secret-from-file"


def test_strips_trailing_newline_only(monkeypatch, tmp_path):
    pass_file = tmp_path / "p"
    pass_file.write_text("  spaces and tabs\t\n")
    monkeypatch.delenv("QUIZMASTER_PASS", raising=False)
    monkeypatch.setenv("QUIZMASTER_PASS_FILE", str(pass_file))
    assert _load_quizmaster_pass() == "  spaces and tabs\t"


def test_raises_when_neither_set(monkeypatch):
    monkeypatch.delenv("QUIZMASTER_PASS", raising=False)
    monkeypatch.delenv("QUIZMASTER_PASS_FILE", raising=False)
    with pytest.raises(RuntimeError, match="QUIZMASTER_PASS"):
        _load_quizmaster_pass()
