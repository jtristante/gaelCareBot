"""Standalone CLI for SNAPSHOT/release version bumping.

Usage:
    python scripts/bump_version.py release <X.Y.Z.dev0>
    python scripts/bump_version.py next <X.Y.Z>

Functions are importable for testing — zero external dependencies.
"""

from __future__ import annotations

import re
import sys

_RE_SNAPSHOT = re.compile(r"^(\d+)\.(\d+)\.(\d+)\.dev0$")
_RE_RELEASE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_snapshot(version_str: str) -> tuple[int, int, int]:
    """Parse a ``X.Y.Z.dev0`` string into ``(major, minor, patch)``.

    Args:
        version_str: Version string to parse.

    Returns:
        Tuple of (major, minor, patch) integers.

    Raises:
        ValueError: If the string does not match ``X.Y.Z.dev0``.
    """
    m = _RE_SNAPSHOT.match(version_str)
    if not m:
        raise ValueError(
            f"'{version_str}' is not a valid dev version "
            "(expected X.Y.Z.dev0)"
        )
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def compute_release(
    major: int, minor: int, patch: int
) -> tuple[int, int, int]:
    """Compute the release version from a snapshot's parts.

    Bumps *major* by 1 and resets minor/patch to 0.
    """
    return (major + 1, 0, 0)


def compute_next_snapshot(
    rel_major: int, rel_minor: int, rel_patch: int
) -> tuple[int, int, int]:
    """Compute the next dev version after a release.

    Bumps *minor* by 1 and resets patch to 0.
    """
    return (rel_major, rel_minor + 1, 0)


def format_version(major: int, minor: int, patch: int) -> str:
    """Format ``(major, minor, patch)`` as ``"X.Y.Z"``."""
    return f"{major}.{minor}.{patch}"


def format_snapshot(major: int, minor: int, patch: int) -> str:
    """Format ``(major, minor, patch)`` as ``"X.Y.Z.dev0"``."""
    return f"{major}.{minor}.{patch}.dev0"


def _main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv

    if len(argv) != 3:
        _die(f"Usage: {argv[0]} <release|next> <version>")

    command, version = argv[1], argv[2]

    if command == "release":
        try:
            parts = parse_snapshot(version)
        except ValueError as exc:
            _die(str(exc))
        rel = compute_release(*parts)
        sys.stdout.write(format_version(*rel))
        sys.stdout.write("\n")
        sys.exit(0)

    if command == "next":
        m = _RE_RELEASE.match(version)
        if not m:
            _die(
                f"'{version}' is not a valid release version "
                "(expected X.Y.Z, no .dev0 suffix)"
            )
        parts = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        nxt = compute_next_snapshot(*parts)
        sys.stdout.write(format_snapshot(*nxt))
        sys.stdout.write("\n")
        sys.exit(0)

    _die(f"Unknown command '{command}' — use 'release' or 'next'")


def _die(message: str) -> None:
    sys.stderr.write(f"Error: {message}\n")
    sys.exit(1)


if __name__ == "__main__":
    _main()
