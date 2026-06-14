# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-23
**Commit:** f051741
**Branch:** master

## OVERVIEW

GaelCareBot — Telegram bot for tracking breast milk stock (extractions, consumption, inventory). Python 3.11, `python-telegram-bot` v20+, SQLite (WAL mode), Docker. Spanish-language UI.

## STRUCTURE

```
./
├── gaelcarebot/                  # Application source
│   ├── handlers/         # Telegram command handlers (8 files)
│   ├── bot.py            # Entry point: wiring + polling
│   ├── config.py         # Env-var → Config dataclass
│   ├── db.py             # MilkDatabase: SQLite CRUD, FIFO, migrations
│   ├── auth.py           # @authorized_only decorator
│   ├── messages.py       # All user-facing strings (Spanish)
│   └── group_notifier.py # Daily summary push to Telegram group
├── tests/                # pytest (asyncio_mode=auto)
├── scripts/              # Dev utilities (seed.py)
├── Dockerfile            # python:3.11-slim, non-root appuser
├── docker-compose.yml    # Single service, volume ./data:/data
└── pyproject.toml         # PEP 621 — deps, build, metadata
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add a new command | `gaelcarebot/handlers/<name>.py` | Follow ConversationHandler or CommandHandler pattern |
| Register a handler | `gaelcarebot/bot.py:53-61` | Import symbol → `application.add_handler(...)` |
| Add a UI string | `gaelcarebot/messages.py` | All user-facing text lives here, `.format()` style |
| Add a config var | `gaelcarebot/config.py` | Extend `Config` dataclass + `.env.example` |
| DB schema changes | `gaelcarebot/db.py:_create_tables()` + `_migrate_schema()` | Add migration block, soft-fail if column exists |
| Change auth logic | `gaelcarebot/auth.py` | `_authorized_ids` module-level set |
| Group notifications | `gaelcarebot/group_notifier.py` | `send_daily_summary()` — called after mutations |
| Change deployment | `Dockerfile`, `docker-compose.yml` | See `devops-notes.md` (gitignored) |
| Run tests | `pytest` | `asyncio_mode=auto`, `pythonpath=.` |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `main()` | function | `gaelcarebot/bot.py:29` | Bootstrap: config → db → auth → handlers → poll |
| `Config` | dataclass | `gaelcarebot/config.py:16` | Frozen config from env vars |
| `load_config()` | function | `gaelcarebot/config.py:28` | Reads env → Config |
| `MilkDatabase` | class | `gaelcarebot/db.py:45` | SQLite wrapper: CRUD, FIFO consume, migrations |
| `init_auth()` | function | `gaelcarebot/auth.py:22` | Sets `_authorized_ids` from Config |
| `authorized_only` | decorator | `gaelcarebot/auth.py:42` | Gates every handler — checks `_authorized_ids` |
| `init_notifier()` | function | `gaelcarebot/group_notifier.py:29` | Stores Config for daily summaries |
| `send_daily_summary()` | function | `gaelcarebot/group_notifier.py:82` | Push summary to group chat (async) |

## CONVENTIONS

**Type hints**: Every function signature is annotated. `from __future__ import annotations` in all files. Prefer `int | None` (PEP 604) over `Optional[int]` for new code. Telegram types always annotated: `update: Update`, `context: ContextTypes.DEFAULT_TYPE`.

**Docstrings**: Google-style (`Args:`, `Returns:`, `Raises:`) for complex functions in `config.py`, `db.py`, `group_notifier.py`. Single-line `"""description."""` for simple handlers.

**Error handling**: `raise ValueError(...)` for validation. Log + inform user on catch. `logger.exception()` for DB errors (includes traceback). No custom exception classes exist.

**Logging**: Module-level `logger = logging.getLogger(__name__)` in every file. `%s` formatting only — never f-strings in log calls. Single `basicConfig` in `bot.py:36`.

**Imports**: `import module` at top. Handler functions import auth, messages, and optionally group_notifier. DB retrieved at runtime via `context.bot_data["db"]`.

**Messages**: All user-facing strings in `gaelcarebot/messages.py` as UPPER_CASE constants. `.format(**kwargs)` with named placeholders. Never hardcode strings in handlers.

**Tests**: `pytest` with `asyncio_mode=auto`. Test files mirror source structure. Handlers use `_impl` wrapper pattern for testability (decorator-free inner function).

## ANTI-PATTERNS (THIS PROJECT)

- **Do NOT hardcode timezone offsets**. Use `pytz.timezone("Europe/Madrid")`, not `timezone(timedelta(hours=2))`.
- **Do NOT import from `scripts/seed.py`** — self-contained, hacks `sys.path`.
- **Do NOT reference `/eliminar` command** — removed in commit `06f7812`, only `.pyc` remains.
- **Do NOT add custom exception classes** — project uses built-in `ValueError` + log pattern.

## UNIQUE STYLES

- **Module-level state with `init_*()`**: `auth.py` and `group_notifier.py` use module-level globals set by `init_*()` called from `main()`. No DI framework.
- **`_impl` wrapper pattern**: Public handler → `@authorized_only` → delegates to `_handler_impl()`. Allows importing `_impl` directly in tests without auth.
- **Optional import gating**: `agregar.py` and `consumir.py` wrap `send_daily_summary` import in try/except — feature degrades gracefully.
- **ConversationHandler state enums**: `STATE1, STATE2 = range(2)` at module level. Each handler exports the built `ConversationHandler` instance directly.

## COMMANDS

```bash
# Development
pip install -e .               # Install package (runtime deps)
pip install -e ".[dev]"        # Install with dev dependencies
python -m gaelcarebot.bot      # Run bot directly
python scripts/seed.py         # Reset DB + seed data
pytest                         # Run tests

# Docker
docker compose up -d --build   # Build + deploy
docker compose logs -f         # Follow logs
docker compose down            # Stop
```

## NOTES

- `DB_PATH` in `.env` uses `/data/milk.db` (Docker path). Local dev without Docker must set `DB_PATH=data/milk.db`.
- `config.timezone` is read from env but **never passed to MilkDatabase** — `now_madrid()` hardcodes UTC+2. Known bug.
- `devops-notes.md` contains deployment workflows (GHCR, Watchtower, SSH) — gitignored, personal notes.
- No CI/CD configured yet — no `.github/workflows/`.
