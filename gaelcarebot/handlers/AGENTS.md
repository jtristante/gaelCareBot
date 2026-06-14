# src/handlers/ — Telegram Command Handlers

## OVERVIEW

8 handler modules: 4 simple commands, 3 ConversationHandlers, 1 global error handler. No shared base classes — each module is self-contained following consistent patterns.

## STRUCTURE

```
handlers/
├── start.py     # /start → welcome + help
├── help.py      # /help → command list
├── agregar.py   # /agregar → add entry (inline or interactive, 2 states)
├── consumir.py  # /consumir → reverse entry (ENTRADA→SALIDA, 2 states)
├── stock.py     # /stock → monospace table of ENTRADA entries
├── total.py     # /total → net stock balance
├── editar.py    # /editar → multi-field edit (5 states)
└── error.py     # Global error handler (no auth, no DB)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add simple command | `help.py` or `start.py` as template | Export async function → register `CommandHandler` in `bot.py` |
| Add multi-step flow | `agregar.py` as template | Export `ConversationHandler` instance → register in `bot.py` |
| Modify a conversation state | `editar.py` — `SELECTING_ENTRY, EDITING_FIELD, ... = range(5)` | Add state int → add entry point → add handler function |
| Add message constant | `src/messages.py` | UPPER_CASE, `.format()` style |
| Debug handler auth | `src/auth.py:authorized_only` decorator | Check `_authorized_ids` set + `is_authorized()` |
| Test a handler | `tests/test_<handler>.py` | Import `_impl` function directly (bypasses auth) |

## CONVENTIONS

### All handlers must:
- Apply `@authorized_only` decorator from `src.auth` (except `error_handler`)
- Retrieve DB via `context.bot_data["db"]` (injected in `bot.py:51`)
- Use message constants from `src/messages.py` — never hardcode strings
- Accept `(update: Update, context: ContextTypes.DEFAULT_TYPE)` signature
- Use `from __future__ import annotations`

### Simple commands (`start`, `help`, `stock`, `total`):
- Export a single async function
- Decorated with `@authorized_only`
- Registered with `CommandHandler("name", function)`

### ConversationHandlers (`agregar`, `consumir`, `editar`):
- States as `RANGE(N)` module-level constants
- Each handler function is `@authorized_only`
- Include `_clear_*_data(context)` to clean user_data on exit
- Include reusable `cancel()` function handling both `callback_query` and `message`
- Export the built `ConversationHandler` instance directly
- Registered with `application.add_handler(conv_handler_instance)`

### Error handler (`error.py`):
- No auth (must always catch)
- No DB access
- Logs via `logger.error(..., exc_info=context.error)` — includes full traceback
- Replies `ERROR_GENERIC` to user — never re-raises

## ANTI-PATTERNS

- **Do NOT reference `/eliminar`** — removed in commit `06f7812`.
- **Do NOT hardcode message strings in handlers.** Always add to `src/messages.py`.
- **Do NOT access DB directly from `error.py`.**
- **Do NOT remove `_impl` wrappers** — they exist for testability.
- **Do NOT merge the `_impl` function into the decorated function** — tests import `_impl` to bypass auth.
