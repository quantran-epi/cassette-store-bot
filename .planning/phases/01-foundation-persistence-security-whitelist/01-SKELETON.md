# Walking Skeleton — Cassette Store Telegram Chatbot

**Phase:** 1
**Generated:** 2026-10-24

## Capability Proven End-to-End

A whitelisted user sends `/ping` to the Telegram bot, which verifies SQLite WAL database read/write readiness and responds with uptime and database status, while strangers are rejected with their User ID.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | `python-telegram-bot` v22.8 | Industry standard async framework for Telegram Bot API 7.x+, native asyncio TaskGroup compatibility, robust `TypeHandler` pipeline and `CopyTextButton` support for elderly users. |
| Data layer | `aiosqlite` v0.22.1 + SQLite WAL | Zero-infrastructure local database file with non-blocking worker threads, `PRAGMA journal_mode=WAL` for concurrent reads/writes without lock stalls, and JSON array support. |
| Access Control | `TypeHandler(Update)` at `group=-1` | Intercepts every Telegram update before group 0 handlers, validates against in-memory whitelist, replies with stranger ID and halts execution via `ApplicationHandlerStop()`. |
| Settings & Env | `pydantic-settings` v2 + `SecretStr` | Fail-fast type validation from `.env`, masked secrets preventing accidental leaks in logs, and custom parsing for comma-separated whitelist User IDs. |
| Domain Models | Pydantic v2 `BaseModel` + `Enum` | High-performance serialization, JSON array validation for customer phones/addresses and order photos, and strict 8-state `OrderStatus` lifecycle. |
| Directory layout | Clean single-module layout under `src/` | `src/config.py`, `src/bot/` (security, handlers, app), `src/db/` (connection, schema, CRUD), `src/models/` (domain models), and `main.py` root entrypoint. |

## Stack Touched in Phase 1

- [x] Project scaffold (`pyproject.toml`, pytest, ruff, `.env.example`, `.gitignore`)
- [x] Routing — Telegram commands `/start`, `/ping`, and `group=-1` security whitelist gate
- [x] Database — SQLite WAL connection, `customers` table with JSON arrays, and `orders` table with customer snapshot and 8-state lifecycle
- [x] UI / Telegram interaction — Welcome message on `/start`, DB connectivity health check on `/ping`, and stranger polite rejection showing User ID
- [x] Deployment / Run — Polling mode entrypoint `main.py` executable locally with standard Python

## Out of Scope (Deferred to Later Slices)

- LLM gateway integration via 9router (`openai` client) and free-text order extraction (deferred to Phase 2)
- Interactive two-phase order confirmation card with Inline buttons (deferred to Phase 2)
- Elderly low-tech Reply Keyboard and 1-tap `CopyTextButton` actions (deferred to Phase 3)
- Order status transition UI buttons and shipping tracking assignment (deferred to Phase 3)
- Natural language Vietnamese order search via LLM (deferred to Phase 4)

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: LLM Ingestion & Interactive Confirmation — 9router OpenAI client extracts unstructured Vietnamese order text into structured draft with preview card.
- Phase 3: Ergonomic Order Management & Low-Tech Actions — Fixed Reply Keyboard, daily order lists, 1-tap copy buttons, photo viewing, and status transitions.
- Phase 4: Natural Language Order Search — Conversational search with confirmation prompt before opening order details.
