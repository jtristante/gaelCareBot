"""Tests for src/messages.py — no Markdown syntax in user-facing strings."""

from __future__ import annotations

from src.messages import HELP_MSG, TABLE_HEADER


class TestTableHeaderNoMarkdown:
    """TABLE_HEADER must not contain Markdown formatting."""

    def test_no_backticks(self):
        """TABLE_HEADER should use HTML <pre> tags, not backticks."""
        assert "`" not in TABLE_HEADER, (
            "TABLE_HEADER contains backtick (`) — use <pre> instead"
        )

    def test_has_bold_title(self):
        """TABLE_HEADER title should be wrapped in <b>."""
        assert "<b>🗓️ Historial de stock</b>" in TABLE_HEADER


class TestHelpMsgNoMarkdown:
    """HELP_MSG must use HTML formatting instead of Markdown."""

    def test_no_bold_markdown(self):
        """HELP_MSG must not contain ** Markdown bold syntax."""
        assert "**" not in HELP_MSG, (
            "HELP_MSG contains Markdown bold (**) — use <b> instead"
        )

    def test_has_bold_html(self):
        """HELP_MSG should use <b> for the title."""
        assert "<b>Comandos disponibles:</b>" in HELP_MSG

    def test_has_code_tags(self):
        """HELP_MSG should use <code> tags for parameter placeholders."""
        assert "<code>" in HELP_MSG
        assert "</code>" in HELP_MSG

    def test_angle_brackets_escaped(self):
        """Parameter notation uses square brackets inside <code> tags (no HTML entities needed)."""
        assert "[cantidad]" in HELP_MSG
