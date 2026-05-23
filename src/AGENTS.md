# src/ — Application Core

## OVERVIEW

Core application modules: entry point, configuration, database, auth, messaging, and group notifications. No packaging — flat `requirements.txt` with `python -m src.bot` entry.

## STRUCTURE

```
src/
├── bot.py            # main(): bootstrap → polling loop
├── config.py         # Config dataclass, load_config()
├── db.py             # MilkDatabase — SQLite CRUD + auto-migration
├── auth.py           # @authorized_only decorator
├── messages.py       # All user-facing Spanish strings
├── group_notifier.py # Daily summary push to Telegram group
└── handlers/         # See src/handlers/AGENTS.md
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Change startup flow | `bot.py:29 main()` | Init order: logging → config → db → auth → notifier → handlers → poll |
| Add env var | `config.py:Config` dataclass | Add field + read in `load_config()` + document in `.env.example` |
| Change DB schema | `db.py:_create_tables()` + `_migrate_schema()` | Add migration block with `try: ALTER TABLE` (soft-fail) |
| Add DB method | `db.py:MilkDatabase` | Follow existing pattern: docstring + validate + execute + commit |
| Modify auth logic | `auth.py` | `_authorized_ids` set populated by `init_auth(config)` |
| Add notification logic | `group_notifier.py` | `send_daily_summary(bot, db)` — async, uses `_config` |
| Add UI text | `messages.py` | UPPER_CASE constants, `.format()` style with named placeholders |

## CONVENTIONS

- `from __future__ import annotations` in every file — enables PEP 604 unions.
- Type hints on all function signatures. Prefer `int | None` over `Optional[int]`.
- Google-style docstrings (`Args:`, `Returns:`, `Raises:`) for complex functions.
- `raise ValueError(...)` for validation errors. Log + inform user, never silent.
- `%s` formatting in log calls, never f-strings.
- Module-level `logger = logging.getLogger(__name__)` in every file.
- `init_*()` functions for module-level state (auth, notifier).

## ANTI-PATTERNS

- **Do NOT hardcode timezone offsets.** See `db.py:8` — known bug. Use `pytz`.
- **Do NOT add `pyproject.toml`** — project convention is flat `requirements.txt`.
- **Do NOT create custom exceptions.** Use `ValueError` + descriptive message.
