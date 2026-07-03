"""Tests for scripts/bump_version.py — pure-logic CLI version bumping."""

from __future__ import annotations

from scripts.bump_version import (
    compute_next_snapshot,
    compute_release,
    format_snapshot,
    format_version,
    parse_snapshot,
)

import pytest


# ---------------------------------------------------------------------------
# parse_snapshot
# ---------------------------------------------------------------------------


class TestParseSnapshot:
    """parse_snapshot accepts valid SNAPSHOT strings."""

    def test_parses_0_1_0(self):
        assert parse_snapshot("0.1.0-SNAPSHOT") == (0, 1, 0)

    def test_parses_1_0_0(self):
        assert parse_snapshot("1.0.0-SNAPSHOT") == (1, 0, 0)

    def test_parses_4_2_0(self):
        assert parse_snapshot("4.2.0-SNAPSHOT") == (4, 2, 0)


class TestParseSnapshotInvalid:
    """parse_snapshot rejects malformed input."""

    def test_rejects_plain_release(self):
        with pytest.raises(ValueError, match="not a valid SNAPSHOT version"):
            parse_snapshot("1.0.0")

    def test_rejects_garbage(self):
        with pytest.raises(ValueError):
            parse_snapshot("abc")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            parse_snapshot("")


# ---------------------------------------------------------------------------
# compute_release
# ---------------------------------------------------------------------------


class TestComputeRelease:
    """compute_release bumps major, resets minor/patch."""

    def test_from_0_1_0(self):
        assert compute_release(0, 1, 0) == (1, 0, 0)

    def test_from_1_1_0(self):
        assert compute_release(1, 1, 0) == (2, 0, 0)

    def test_from_4_2_0(self):
        assert compute_release(4, 2, 0) == (5, 0, 0)


# ---------------------------------------------------------------------------
# compute_next_snapshot
# ---------------------------------------------------------------------------


class TestComputeNextSnapshot:
    """compute_next_snapshot bumps minor, resets patch."""

    def test_from_1_0_0(self):
        assert compute_next_snapshot(1, 0, 0) == (1, 1, 0)

    def test_from_2_0_0(self):
        assert compute_next_snapshot(2, 0, 0) == (2, 1, 0)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


class TestFormatHelpers:
    """format_version and format_snapshot produce correct strings."""

    def test_format_version(self):
        assert format_version(1, 0, 0) == "1.0.0"
        assert format_version(4, 2, 0) == "4.2.0"

    def test_format_snapshot(self):
        assert format_snapshot(1, 0, 0) == "1.0.0-SNAPSHOT"
        assert format_snapshot(0, 1, 0) == "0.1.0-SNAPSHOT"


# ---------------------------------------------------------------------------
# Integration: full cycle
# ---------------------------------------------------------------------------


class TestFullCycle:
    """End-to-end: SNAPSHOT → release → next SNAPSHOT."""

    def test_0_1_0_snapshot_to_release_to_next(self):
        original = "0.1.0-SNAPSHOT"

        mjr, mnr, ptc = parse_snapshot(original)
        rel_mjr, rel_mnr, rel_ptc = compute_release(mjr, mnr, ptc)
        release_str = format_version(rel_mjr, rel_mnr, rel_ptc)

        assert release_str == "1.0.0"

        nxt_mjr, nxt_mnr, nxt_ptc = compute_next_snapshot(
            rel_mjr, rel_mnr, rel_ptc
        )
        next_snapshot_str = format_snapshot(nxt_mjr, nxt_mnr, nxt_ptc)

        assert next_snapshot_str == "1.1.0-SNAPSHOT"

    def test_4_2_0_snapshot_to_release_to_next(self):
        original = "4.2.0-SNAPSHOT"

        mjr, mnr, ptc = parse_snapshot(original)
        rel_mjr, rel_mnr, rel_ptc = compute_release(mjr, mnr, ptc)
        release_str = format_version(rel_mjr, rel_mnr, rel_ptc)

        assert release_str == "5.0.0"

        nxt_mjr, nxt_mnr, nxt_ptc = compute_next_snapshot(
            rel_mjr, rel_mnr, rel_ptc
        )
        next_snapshot_str = format_snapshot(nxt_mjr, nxt_mnr, nxt_ptc)

        assert next_snapshot_str == "5.1.0-SNAPSHOT"
