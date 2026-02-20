"""Tests for nickname sanitization and uniqueness."""

import pytest

from bayesian_quiz.state import GameManager, sanitize_nickname


class TestSanitizeNickname:
    def test_strips_whitespace(self):
        assert sanitize_nickname("  Alice  ") == "Alice"

    def test_collapses_internal_whitespace(self):
        assert sanitize_nickname("Bob   Smith") == "Bob Smith"

    def test_strips_zero_width_spaces(self):
        assert sanitize_nickname("Al\u200bice") == "Alice"

    def test_strips_zero_width_joiner(self):
        assert sanitize_nickname("Al\u200dice") == "Alice"

    def test_strips_zero_width_non_joiner(self):
        assert sanitize_nickname("Al\u200cice") == "Alice"

    def test_strips_rtl_mark(self):
        assert sanitize_nickname("Alice\u200f") == "Alice"

    def test_strips_ltr_mark(self):
        assert sanitize_nickname("\u200eAlice") == "Alice"

    def test_strips_directional_overrides(self):
        assert sanitize_nickname("\u202aAlice\u202c") == "Alice"

    def test_strips_directional_embedding(self):
        assert sanitize_nickname("\u202bAlice\u202c") == "Alice"

    def test_strips_directional_isolates(self):
        assert sanitize_nickname("\u2066Alice\u2069") == "Alice"

    def test_strips_bom(self):
        assert sanitize_nickname("\ufeffAlice") == "Alice"

    def test_strips_soft_hyphen(self):
        assert sanitize_nickname("Al\u00adice") == "Alice"

    def test_strips_word_joiner(self):
        assert sanitize_nickname("Al\u2060ice") == "Alice"

    def test_strips_function_application(self):
        assert sanitize_nickname("Al\u2061ice") == "Alice"

    def test_strips_invisible_times(self):
        assert sanitize_nickname("Al\u2062ice") == "Alice"

    def test_strips_invisible_separator(self):
        assert sanitize_nickname("Al\u2063ice") == "Alice"

    def test_strips_invisible_plus(self):
        assert sanitize_nickname("Al\u2064ice") == "Alice"

    def test_strips_interlinear_annotation(self):
        assert sanitize_nickname("\ufff9Alice\ufffb") == "Alice"

    def test_strips_inhibit_swap(self):
        assert sanitize_nickname("\u206aAlice\u206a") == "Alice"

    def test_nfkc_fullwidth(self):
        assert sanitize_nickname("\uff21\uff4c\uff49\uff43\uff45") == "Alice"

    def test_nfkc_superscript(self):
        assert sanitize_nickname("x\u00b2") == "x2"

    def test_nfkc_ligature_fi(self):
        assert sanitize_nickname("\ufb01sh") == "fish"

    def test_nfkc_roman_numeral(self):
        assert sanitize_nickname("\u2163") == "IV"

    def test_empty_after_sanitization(self):
        assert sanitize_nickname("\u200b\u200c\u200d") == ""

    def test_only_whitespace_after_sanitization(self):
        assert sanitize_nickname("  \u200b  ") == ""

    def test_preserves_normal_unicode(self):
        assert sanitize_nickname("Ålice") == "Ålice"

    def test_preserves_emoji(self):
        assert sanitize_nickname("Alice 🎲") == "Alice 🎲"

    def test_preserves_cjk(self):
        assert sanitize_nickname("太郎") == "太郎"

    def test_preserves_arabic(self):
        assert sanitize_nickname("أليس") == "أليس"

    def test_preserves_combining_marks(self):
        result = sanitize_nickname("e\u0301")  # e + combining acute = é after NFKC
        assert result == "é"

    def test_html_tags_preserved_as_text(self):
        assert sanitize_nickname("<b>Alice</b>") == "<b>Alice</b>"

    def test_html_entities_preserved_as_text(self):
        assert sanitize_nickname("&lt;Alice&gt;") == "&lt;Alice&gt;"

    def test_script_tag_preserved_as_text(self):
        assert sanitize_nickname('<script>alert(1)</script>') == '<script>alert(1)</script>'


class TestDuplicateNicknames:
    @pytest.fixture
    def gm(self):
        manager = GameManager()
        manager.state.questions = []
        return manager

    @pytest.mark.anyio
    async def test_duplicate_rejected(self, gm):
        await gm.add_participant("p1", "Alice")
        with pytest.raises(ValueError, match="already taken"):
            await gm.add_participant("p2", "Alice")

    @pytest.mark.anyio
    async def test_case_insensitive_duplicate(self, gm):
        await gm.add_participant("p1", "Alice")
        with pytest.raises(ValueError, match="already taken"):
            await gm.add_participant("p2", "alice")

    @pytest.mark.anyio
    async def test_zero_width_duplicate(self, gm):
        await gm.add_participant("p1", "Alice")
        with pytest.raises(ValueError, match="already taken"):
            await gm.add_participant("p2", "Al\u200bice")

    @pytest.mark.anyio
    async def test_whitespace_duplicate(self, gm):
        await gm.add_participant("p1", "Alice")
        with pytest.raises(ValueError, match="already taken"):
            await gm.add_participant("p2", "  Alice  ")

    @pytest.mark.anyio
    async def test_fullwidth_duplicate(self, gm):
        await gm.add_participant("p1", "Alice")
        with pytest.raises(ValueError, match="already taken"):
            await gm.add_participant("p2", "\uff21\uff4c\uff49\uff43\uff45")

    @pytest.mark.anyio
    async def test_empty_nickname_rejected(self, gm):
        with pytest.raises(ValueError, match="empty"):
            await gm.add_participant("p1", "   ")

    @pytest.mark.anyio
    async def test_invisible_only_nickname_rejected(self, gm):
        with pytest.raises(ValueError, match="empty"):
            await gm.add_participant("p1", "\u200b\u200c\u200d\u200e\u200f")

    @pytest.mark.anyio
    async def test_different_nicks_allowed(self, gm):
        await gm.add_participant("p1", "Alice")
        await gm.add_participant("p2", "Bob")
        assert len(gm.state.participants) == 2

    @pytest.mark.anyio
    async def test_stored_nickname_is_sanitized(self, gm):
        await gm.add_participant("p1", "  Al\u200bice  ")
        assert gm.state.participants["p1"].nickname == "Alice"
