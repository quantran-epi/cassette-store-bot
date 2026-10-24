<!-- GSD:project-start source:PROJECT.md -->

## Project

**Cassette Store Telegram Chatbot**

Chatbot Telegram phục vụ quản lý đơn hàng và khách hàng cho shop bán băng cassette. Hệ thống được thiết kế đặc thù cho người dùng lớn tuổi, low-tech, thao tác chủ yếu qua Inline Keyboard Buttons một chạm và nhập liệu dạng free-text chat tự nhiên được bóc tách bằng LLM.

**Core Value:** Người lớn tuổi nhập tự do một đoạn tin nhắn đặt hàng bất kỳ qua Telegram, bot dùng LLM tự bóc tách chính xác thông tin (khách, hàng hoá, tiền COD, hình thức), hiển thị nút bấm xác nhận trực quan và lưu trữ an toàn vào DB mà không cần thao tác biểu mẫu phức tạp.

### Constraints

- **Tech stack**: Python + SQLite (sqlite3) + python-telegram-bot (v20+ async).
- **LLM Gateway**: 9router (OpenAI-compatible protocol), cho phép cấu hình URL, API Key và Model ID trong local settings.
- **Bảo mật**: Whitelist Telegram User IDs — từ chối tương tác từ người lạ.
- **UX**: Tối đa nút bấm Inline, tối thiểu việc gõ phím cấu trúc/lệnh dài dòng; mọi hành động nhạy cảm đều phải có bước hỏi lại để confirm.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | `3.12+` or `3.13+` | Runtime environment | Standard modern async support (`asyncio.TaskGroup`, `to_thread`), native performance improvements, long-term support. |
| **python-telegram-bot** | `~=22.8` (`>=21.10,<23.0`) | Telegram Bot framework | Industry-standard async framework for Telegram Bot API 7.x+. Built-in `ApplicationBuilder`, non-blocking polling, type hints, and full support for `CopyTextButton` (crucial 1-tap copy UX for elderly users). |
| **aiosqlite** | `~=0.22.1` (`>=0.20.0`) | Async SQLite client | Zero-infrastructure, zero-network database running as local single file (`.db`). Wraps standard library `sqlite3` in worker threads to prevent event loop stalls. Supports WAL mode and row factory dictionaries. |
| **openai** | `~=3.37.0` (`>=1.50.0`) | LLM client for 9router | Official client with native `AsyncOpenAI`, configurable `base_url`, custom headers, timeout controls, and `beta.chat.completions.parse` for structured output extraction. |
| **pydantic** | `~=2.14.1` (`>=2.8.0`) | Schema validation & parsing | High-performance Rust-backed data modeling. Powers LLM output parsing, strict schema validation, currency/phone normalization, and customer/order domain objects. |
| **pydantic-settings** | `~=2.16.1` (`>=2.4.0`) | Environment & configuration | Reads `.env` files with fail-fast type validation. Automatically parses comma-separated strings into `list[int]` (whitelist IDs) and hides sensitive tokens via `SecretStr`. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | `~=0.28.1` | Underlying HTTP transport for OpenAI | Installed automatically as dependency of `openai` and `python-telegram-bot`. Use directly for custom gateway diagnostics or health check probes if needed. |
| **typing-extensions** | `>=4.12.0` | Advanced type annotations | Transitive dependency enabling modern type features across Python versions. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **ruff** | Linter & formatter | Replaces flake8, isort, black. Ultra-fast, keeps code tidy with minimal config. |
| **pytest** & **pytest-asyncio** | Async unit and integration tests | Essential for testing DB queries, parsing logic, and LLM extraction schemas without running live Telegram polling. |

## Installation

# Core dependencies

# Development dependencies

## Technical Implementations & Architectural Patterns

### 1. Telegram Bot (python-telegram-bot v20+ Async)

#### Access Control Whitelist (Security Gate)

#### ConversationHandler vs Stateless Callback Handlers

- **Free-text ingestion & confirmation:** Use stateless `CallbackQueryHandler` with structured `callback_data` (e.g., `ord:confirm:<draft_id>` or `ord:cancel:<draft_id>`). Store temporary drafts in `context.user_data["pending_order"]`.
- **Text input prompts (e.g. entering tracking code or notes):** Use `ConversationHandler` with explicit timeout and cancel fallback:

#### Elderly Low-Tech UX Patterns

### 2. SQLite Database & Schema Design

#### Database Configuration (aiosqlite)

#### Relational Schema (Multi-phone, Multi-address, Snapshot Orders)

### 3. OpenAI Client, 9router Gateway & Structured Outputs

#### Pydantic Extraction Schema

#### Dual-Mode LLM Client with Fallback

### 4. Settings Management (Pydantic-Settings v2)

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **aiosqlite** | **SQLAlchemy Async / Tortoise ORM** | Only if domain has 20+ tables with complex relation graphs and multi-database migrations. For a 3-table store bot, ORMs add 300+ lines of async session lifecycle ceremony without value. |
| **aiosqlite** | **Standard sqlite3 + asyncio.to_thread** | Acceptable for quick prototypes, but `aiosqlite` encapsulates context managers and thread pools cleanly with fewer bugs. |
| **pydantic-settings** | **python-dotenv** | Use `python-dotenv` only if zero additional dependencies are permitted. `python-dotenv` lacks type validation and fails silently if env vars are malformed or missing. |
| **openai (AsyncOpenAI)** | **httpx raw calls** | When zero external client dependencies are desired. However, `openai` already provides connection pooling, retry logic, error hierarchies, and type definitions out of the box. |
| **python-telegram-bot** | **aiogram (v3)** | Both are excellent modern async frameworks. PTB is chosen here because of simpler high-level conversation handling, stability, and direct standard library alignment without extra FSM boilerplate. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Synchronous `sqlite3` in async handlers** | Blocks Python's single-threaded event loop during disk writes; freezes bot responses for all users. | `aiosqlite` with WAL mode. |
| **FastAPI / Flask / Webhook servers** | Requires public static IP, HTTPS certificates, reverse proxy (Nginx), or tunnel (ngrok) for local running. Unnecessary operational friction for a private internal bot. | PTB's built-in `Application.run_polling()`. |
| **Redis / Celery** | Overkill complexity for low-throughput retail bot (<100 orders/day). Adds external service failure modes. | SQLite for persistence and Python `asyncio` for background operations. |
| **Strict JSON schema only (without fallback)** | 9router routes to heterogeneous models; models from some providers crash with HTTP 400 when sent OpenAI `json_schema` parameters. | 2-tier extractor: try `beta.chat.completions.parse()`, fallback to `response_format={"type": "json_object"}` + `Pydantic.model_validate_json()`. |
| **Hardcoded Vietnamese strings in queries** | Fails on diacritic accents and informal address queries. | Use SQL parameters and SQLite `LIKE` queries with normalized strings. |

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `python-telegram-bot==22.8` | `httpx~=0.28.1`, `Python >= 3.9` | Fully async; supports Bot API 7.3+ `CopyTextButton`. |
| `openai==3.37.0` | `pydantic>=2.8.0`, `httpx>=0.28.0` | Supports structured output parsing (`parse`) and custom `base_url`. |
| `pydantic-settings==2.16.1` | `pydantic>=2.14.0` | Provides unified environment and secret management. |
| `aiosqlite==0.22.1` | `Python >= 3.8` | Stable thread-pool async bridge to SQLite. |

## Sources

- [PyPI - python-telegram-bot](https://pypi.org/project/python-telegram-bot/) — verified v22.8 release and Bot API 7.3+ CopyTextButton support.
- [PyPI - openai](https://pypi.org/project/openai/) — verified v3.37.0 release, `AsyncOpenAI`, and structured output support.
- [PyPI - pydantic-settings](https://pypi.org/project/pydantic-settings/) — verified v2.16.1 release and type coercion capabilities.
- [PyPI - aiosqlite](https://pypi.org/project/aiosqlite/) — verified v0.22.1 release.
- [Telegram Bot API Documentation](https://core.telegram.org/bots/api#copytextbutton) — verified `CopyTextButton` specification.

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
