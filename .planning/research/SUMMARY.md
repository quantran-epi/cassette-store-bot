# Project Research Summary

**Project:** Cassette Store Telegram Chatbot (Milestone v1.1 NL Order Mutation, Console Admin, RBAC & GitHub Backup)  
**Domain:** Telegram Retail Order Management Chatbot (Low-Tech Cassette Merchant)  
**Researched:** 2026-10-25  
**Confidence:** HIGH  

## Executive Summary

Milestone v1.1 extends the validated v1.0 cassette store bot with natural language order mutation, a local server console, multi-tier RBAC, and automated GitHub backups. The target users remain elderly, low-tech shop operators who manage retail cassette orders via Telegram free-text and 1-tap touch buttons. Natural language order editing introduces high operational risk: speech-to-text slips or ambiguous phrasing can silently overwrite addresses, corrupt prices, or cancel active orders. Experts mitigate this by combining a deterministic 3-way intent router (separating Ingest, Search, and Mutation) with a mandatory 2-phase visual diff preview card (`Before ➡️ After`) before any SQLite update commits.

The administration architecture decouples local host maintenance from remote Telegram operations. A server console CLI runs concurrently with Telegram polling in the Python asyncio loop, providing server status, diagnostics, whitelist administration, and instant backup triggers without Telegram dependencies. Access control upgrades from a static `.env` whitelist to a two-tier dynamic model (`SUPER_ADMIN` vs `ADMIN`) anchored by an immutable root Super Admin ID in configuration.

Database protection relies on atomic, zero-infrastructure online backups. In SQLite WAL mode, raw file copying leads to corrupted snapshots. The recommended approach executes atomic `VACUUM INTO` snapshots, compresses them via Python stdlib `gzip` (75–85% reduction), and commits `.db.gz` archives directly to a private GitHub repository via `httpx` async calls to the GitHub REST API. This eliminates local Git CLI processes, SSH key friction, and binary tree bloat while providing both scheduled (daily 02:00 AM VN time) and manual backup triggers.

## Key Findings

### Recommended Stack

Milestone v1.1 builds upon the existing v1.0 foundation (`python-telegram-bot~=22.8`, `aiosqlite~=0.22.1`, `openai~=3.37.0`, `pydantic~=2.14.1`, `pydantic-settings~=2.16.1`, `httpx~=0.28.1`). It minimizes new third-party packages by leveraging Python standard libraries (`gzip`, `base64`, `enum.StrEnum`, `zoneinfo`) and existing HTTP clients.

**Core technologies:**
- `python-telegram-bot[job-queue]~=22.8`: APScheduler-backed scheduled tasks inside PTB runtime — drives daily 02:00 AM VN time backups with timezone awareness.
- `prompt_toolkit~=3.0.53` (or `asyncio.to_thread(sys.stdin.readline)`): Non-blocking terminal input — handles server console input without stalling the asyncio event loop.
- `SQLite3 VACUUM INTO` (Stdlib): Point-in-time atomic online backup via `aiosqlite` — creates standalone, clean `.db` snapshot from live WAL database with zero lock contention.
- `httpx` (GitHub REST API): Existing async HTTP client — pushes base64-encoded compressed backups directly to GitHub Contents API (`PUT /repos/{owner}/{repo}/contents/{path}`) with zero Git CLI or SSH setup.

### Expected Features

Milestone v1.1 introduces four operational pillars to support multi-operator daily workflows.

**Must have (table stakes):**
- 3-Way Intent Disambiguation: Route incoming text cleanly between Search, Mutate, and New Ingest without collisions.
- 2-Phase Mutation Preview & Diff: HTML card with bold/strikethrough changes and 1-tap `[✅ Xác nhận sửa]` / `[❌ Huỷ]` buttons (120s TTL draft).
- Core Field Mutations: Update status (8 enum values), tracking code, notes, COD/total amount, recipient phone, and shipping address.
- Multi-Match Disambiguation: Inline list picker when a mutation target matches multiple orders.
- Super Admin vs Admin RBAC: Dynamic `admin_users` table with immutable `.env` Super Admin anchor and `@require_role` gate.
- Server Interactive Console: Terminal management CLI with status, RBAC management, diagnostics, and manual backup.
- Telegram `/admin` Control Dashboard: Mobile management card for status, reports, backup trigger, and admin delegation.
- Atomic SQLite WAL Snapshot & GitHub REST Backup: Safe snapshotting, gzip compression, and automated daily + manual cloud uploads.

**Should have (competitive differentiators):**
- Elderly-Friendly Visual Diff Card: Visual "Before ➡️ After" lines with clear change indicators remove technology fear.
- Ambiguity Fallback to 1-Tap Action Pills: If user says "sửa đơn 12" without specifying a field, bot renders 1-tap buttons for all editable fields.
- Zero-Git-CLI GitHub REST Backup: Pure HTTPS API upload requiring no Git binary or SSH keys on the host.
- Safe Admin Delegation with Protection Anchor: Immutable Super Admin check prevents self-demotion or bot lockout.

**Defer (v2+):**
- Voice Note Mutation via Whisper (v1.1.x / v2).
- Automated Database Restore Wizard (v2+).
- Web-based SaaS Admin Dashboard (Anti-feature: violates zero-maintenance, low-footprint architecture).
- Direct mutation without confirmation (Anti-feature: fatal for low-tech elderly users).

### Architecture Approach

The architecture maintains a layered, single-process asyncio model. Telegram long-polling and the Server Console run concurrently under explicit lifecycle control in `main.py`. Incoming messages pass through a Group -1 dynamic RBAC security gate before hitting the 3-Way Intent Router. Database mutations require a 2-phase confirmation loop backed by an in-memory draft cache. Backups are completely decoupled: a standalone backup service handles SQLite `VACUUM INTO`, gzip compression, and GitHub REST uploads, callable by the PTB JobQueue scheduler, Telegram `/admin`, or Console CLI.

**Major components:**
1. **Interactive Server Console (`src/console/`):** Reads stdin asynchronously via worker thread; auto-detects headless environments via `sys.stdin.isatty()`.
2. **3-Way Intent Router (`src/services/router.py`):** Deterministic heuristic and verb classifier preventing mutation collisions with ingest or search.
3. **NL Order Mutation Service (`src/services/order_mutation.py`):** Target order resolver + 9router LLM structured delta extractor (`OrderMutationDelta`).
4. **RBAC Security Gate (`src/bot/rbac.py`):** Two-tier role verification (`SUPER_ADMIN` vs `ADMIN`), in-memory cache, and `@require_role` decorators for commands and callbacks.
5. **GitHub Backup Service & Scheduler (`src/services/backup.py`, `src/services/scheduler.py`):** Transaction-safe online snapshotter, gzip encoder, and async REST uploader with daily JobQueue scheduling.

### Critical Pitfalls

1. **Event Loop Stalls & Headless CPU Spin from Terminal Console:** Synchronous `input()` freezes Telegram polling and timers; running without a TTY spins at 100% CPU on EOF.  
   *Prevention:* Check `sys.stdin.isatty()` on startup; use `asyncio.to_thread(sys.stdin.readline)` or `prompt_toolkit` with clean EOF handling.
2. **Intent Collisions & Silent Data Overwrites in NL Mutation:** Free-text edits misclassified as new orders, or vice versa, causing data corruption without confirmation.  
   *Prevention:* Deterministic 3-way intent router; mandatory 2-phase Before/After diff card with explicit button confirmation; short-lived draft TTL (120s).
3. **SQLite WAL Backup Corruption & Git Binary Bloat:** Direct OS file copy misses active WAL/SHM frames; git commits bloat repository size.  
   *Prevention:* SQLite `VACUUM INTO` atomic snapshot; in-memory gzip compression; upload via GitHub REST Contents API to a dedicated private backup repo.
4. **Broken Role Boundaries & Callback Privilege Escalation:** Securing `/admin` slash command but neglecting inline callback queries allows secondary admins to trigger restricted actions.  
   *Prevention:* Enforce `@require_role` decorator on both command handlers AND callback query handlers; lock root Super Admin ID in `.env`.
5. **Replay Attacks & Race Conditions on Confirmation Callbacks:** Double-tapping `[Xác nhận sửa]` applies stale changes or crashes Telegram callback payload limits.  
   *Prevention:* Immediate `query.answer()`; short draft IDs (8 chars); single-use token deletion; optimistic concurrency check in SQL `UPDATE`.

---

## Implications for Roadmap

Milestone v1.1 builds upon the completed v1.0 foundation (Phases 01–04). The suggested 5-phase structure groups components by architectural dependency: security and storage first, followed by concurrent host infrastructure, complex natural language mutation, and unified Telegram administration.

### Phase 05: RBAC & Dynamic Access Control
**Rationale:** Security foundation must precede administrative actions and order mutations. Upgrading the security gate from static `.env` to a dynamic database table enables role verification across both Telegram and Console layers.  
**Delivers:** `admin_users` table schema, Super Admin `.env` bootstrap on startup, in-memory role cache in `bot_data`, `@require_role` decorators, and updated Group -1 whitelist gate.  
**Addresses:** Super Admin vs Admin role separation, safe admin delegation foundation.  
**Avoids:** Broken role boundaries, callback privilege escalation, Super Admin lockout (Pitfall 5).

### Phase 06: Database Backup Engine & GitHub REST Integration
**Rationale:** Data protection must be operational before introducing destructive order mutation capabilities. As an isolated service, backup can be built and tested completely independently of UI handlers.  
**Delivers:** SQLite `VACUUM INTO` snapshot runner, in-memory gzip compression pipeline, async GitHub REST API client via `httpx`, PTB JobQueue daily scheduler (02:00 AM VN time), and backup notification cards.  
**Addresses:** Atomic SQLite WAL snapshotting, periodic and manual GitHub backups, backup integrity receipt.  
**Avoids:** Corrupted WAL backups, Git CLI subprocess crashes, binary repo bloat, PII exposure (Pitfall 3 & Pitfall 4).

### Phase 07: Interactive Server Console App & Concurrency Lifecycle
**Rationale:** Host-level operator tooling requires refactoring `main.py` from `app.run_polling()` to explicit async application lifecycle management (`initialize()`, `start()`, `updater.start_polling()`). Establishing non-blocking terminal I/O ensures server stability.  
**Delivers:** Decoupled CLI runner in `src/console/`, non-blocking stdin reader with `asyncio.to_thread`, TTY auto-detection (`sys.stdin.isatty()`) for headless environments, and interactive commands (status, RBAC whitelist, manual backup, order inspect).  
**Addresses:** Terminal interactive console app, server maintenance without Telegram dependency.  
**Avoids:** Event loop stalls, 100% CPU infinite loop in headless/daemon mode, signal clashes on `Ctrl+C` (Pitfall 1).

### Phase 08: 3-Way Intent Router & NL Order Mutation Pipeline
**Rationale:** The highest user-value and highest complexity feature of v1.1. Builds on top of Phase 02 LLM gateway, Phase 03 order actions, and Phase 04 search.  
**Delivers:** 3-way intent router (Mutation vs Search vs Ingest), Order Target Resolver, LLM delta extractor (`OrderMutationDelta` Pydantic schema), 2-phase Before/After visual diff card, 1-tap confirmation/cancel callbacks with 120s TTL draft, multi-match disambiguation keyboard, and field-specific atomic SQL updates.  
**Addresses:** NL intent disambiguation, 2-phase diff preview, core field mutations, status target suggestions, ambiguity fallbacks.  
**Avoids:** Intent collisions, silent data overwrites, double-tap callback replays, 64-byte callback overflow (Pitfall 2 & Pitfall 6).

### Phase 09: Telegram Admin Suite & Operational Management
**Rationale:** Final integration phase bringing together RBAC, backup triggers, and order summaries into an ergonomic mobile control center for shop owners on Telegram.  
**Delivers:** `/admin` command handler and interactive control card, revenue/order statistics cards, 1-tap manual backup trigger with live progress notifications, and Super Admin user delegation flow (add/remove Admin with numeric ID input).  
**Addresses:** Telegram `/admin` command & control card, mobile admin delegation.  
**Avoids:** Secondary admin privilege escalation, accidental self-demotion.

### Phase Ordering Rationale

- **Phase 05 (RBAC) precedes Phase 07 & 09:** Both Console and Telegram `/admin` handlers require the `Role` enum, `admin_users` table, and `@require_role` decorators to function.
- **Phase 06 (Backup Engine) precedes Phase 08 (Mutation):** Safe automated backup guarantees that if any unintended mutation occurs during early operational use, a point-in-time snapshot exists on GitHub.
- **Phase 07 (Console) decouples server operations early:** Refactoring the application lifecycle in `main.py` allows background tasks (scheduler, polling, console) to run stably together before adding more Telegram handlers.
- **Phase 08 (Mutation) is isolated after infrastructure:** Mutation touches LLM prompts, candidate lookup, and 2-phase UI. Isolating it ensures focused testing of Vietnamese regex/intent heuristics without distraction from server administration logic.
- **Phase 09 (Telegram Admin) finishes milestone:** Wires together previously tested services (RBAC, Backup, Statistics) into the user-facing Telegram UI.

### Research Flags

**Phases needing deeper research / evaluation during planning:**
- **Phase 08 (NL Order Mutation Pipeline):** Requires careful prompt engineering and test phrase matrix (30+ Vietnamese queries) to calibrate the 3-way intent router boundary against Search and Ingest.
- **Phase 06 (GitHub Backup Engine):** Verify GitHub Personal Access Token scopes and test SHA handling when committing to existing repository paths.

**Phases with standard patterns (skip research-phase):**
- **Phase 05 (RBAC):** Standard SQLite table + Python decorator pattern.
- **Phase 07 (Server Console):** Standard `asyncio.to_thread` terminal prompt loop with `isatty()` guard.
- **Phase 09 (Telegram Admin Suite):** Standard PTB `InlineKeyboardMarkup` and `ConversationHandler` patterns already established in v1.0.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Minimal new dependencies (`prompt_toolkit`, PTB `job-queue`); stdlib `sqlite3 VACUUM INTO`, `gzip`, `zoneinfo`, and existing `httpx` verified via PyPI and official documentation. |
| Features | HIGH | Concrete specifications derived from elderly user domain constraints, Vietnamese retail workflows, and v1.0 operational lessons. |
| Architecture | HIGH | Concurrency lifecycle, 3-way intent routing, atomic SQLite backup, and RBAC hierarchy validated against PTB v20+ and SQLite 3.27+ specifications. |
| Pitfalls | HIGH | Critical failure modes (WAL copy corruption, event loop stalls, headless CPU spin, callback escalation, intent collisions) explicitly identified with concrete prevention strategies. |

**Overall confidence:** HIGH

### Gaps to Address

- **GitHub Personal Access Token Scope:** Ensure operator configures a fine-grained PAT restricted solely to the backup repository with `contents:write` permission. Document clearly in setup guide.
- **Vietnamese LLM Verb Drift:** Monitor 9router performance across different base models to verify that Vietnamese mutation terms (e.g., "gán mã", "bom hàng", "chuyển khoản rồi") consistently parse into the correct `OrderMutationDelta` schema.

---

## Sources

### Primary (HIGH confidence)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/) — verified v22.8 `Application` manual lifecycle, JobQueue integration, and CallbackQuery mechanics.
- [SQLite Official Documentation - VACUUM INTO](https://www.sqlite.org/lang_vacuum.html#vacuuminto) — verified atomic online backup behavior in WAL mode without locking readers or writers.
- [GitHub REST API Documentation - Create or Update File Contents](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents) — verified Base64 PUT endpoint, 100MB payload limits, and SHA overwrite semantics.
- [Python asyncio Documentation - Running in Threads](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread) — verified non-blocking standard input reading.

### Secondary (MEDIUM confidence)
- [PyPI - prompt_toolkit](https://pypi.org/project/prompt_toolkit/) — verified v3.0.53 release, `prompt_async` and `patch_stdout` support for terminal consoles.
- Cassette Store Bot v1.0 Production Architecture & Milestone v1.1 Specifications.

---
*Research completed: 2026-10-25*  
*Ready for roadmap: yes*
