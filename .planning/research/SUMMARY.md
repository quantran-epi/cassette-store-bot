# Project Research Summary

**Project:** Cassette Store Telegram Chatbot
**Domain:** Telegram Retail Order Management Chatbot (Low-Tech Elderly Merchant / Local SQLite / 9router LLM)
**Researched:** 2026-10-24
**Confidence:** HIGH

## Executive Summary

The Cassette Store Telegram Chatbot is a private backoffice order management tool designed for an elderly, low-tech merchant selling vintage audio cassettes. Customers place unstructured orders via Zalo, Facebook, and SMS with colloquial Vietnamese shorthand, missing punctuation, and varied pricing terms. Rather than imposing complex forms or multi-step wizard dialogues that alienate non-technical users, experts build this system around zero-shot free-text ingestion: the shop owner simply pastes the raw chat stream into Telegram, where an LLM parses the message into a structured draft presented on an interactive confirmation card. The order is committed to disk only after explicit human tap confirmation.

The recommended architectural approach uses Python 3.12+ with python-telegram-bot (v22.8 async long polling), aiosqlite with Write-Ahead Logging (WAL) for persistent zero-overhead storage, and the openai SDK pointing to a 9router gateway with Pydantic v2 structured schemas. Interaction ergonomics are specifically tuned for aging eyes and fingers: persistent Reply Keyboard buttons, zero required slash commands, prominent Vietnamese status badges with emoji markers, and 1-tap clipboard copy buttons (CopyTextButton / code tags) to transfer phone numbers, addresses, and tracking codes directly into carrier apps (GHTK, ViettelPost, GHN).

Key technical risks include Telegram's 30-second callback query timeout when waiting for upstream LLM inference, SQLite database lock errors in concurrent async execution, Telegram's Message is not modified API crash loop, and LLM hallucinations over Vietnamese administrative divisions (mergers of phuong/quan) and colloquial price terms (250k, 1tr2, nua trieu). These risks are mitigated by immediate callback answering (query.answer()), enforcing SQLite WAL mode with busy timeouts, capturing raw address strings without artificial normalization, strict integer VND outputs with fallback multipliers, and wrapping UI edits in idempotent exception handlers.

## Key Findings

### Recommended Stack

The chosen stack prioritizes zero-friction local execution, high reliability without background daemons, and strict type safety across data boundaries. Detailed rationale lives in STACK.md.

**Core technologies:**
- **Python (3.12+):** Modern runtime providing robust async primitives (asyncio.TaskGroup, to_thread) and native performance improvements.
- **python-telegram-bot (~=22.8):** Fully asynchronous Telegram API 7.x+ framework. Natively supports CopyTextButton, high-level callback routing, and resilient non-blocking polling without webhook/reverse-proxy overhead.
- **aiosqlite (~=0.22.1):** Async SQLite client wrapping stdlib sqlite3 in non-blocking worker threads. Runs locally as a single .db file with WAL mode enabled.
- **openai (~=3.37.0):** Standard client configured with custom base_url for 9router. Supports dual-mode schema extraction (beta.chat.completions.parse with fallback to response_format={type: json_object}).
- **pydantic (~=2.14.1) & pydantic-settings (~=2.16.1):** Fail-fast configuration parsing, runtime type validation, Telegram whitelist ID extraction, and strict LLM output parsing.

### Expected Features

Detailed specifications, dependency graphs, and prioritization matrices are documented in FEATURES.md.

**Must have (table stakes):**
- **Telegram User ID Whitelist:** Gatekeeper middleware blocking all non-whitelisted Telegram users before processing updates.
- **Customer Storage (Multi-phone, Multi-address):** Relational tracking of repeat customers with historical snapshot preservation on orders.
- **7-Stage Order Lifecycle Engine:** State machine tracking Cho lam -> Dang lam -> Da dong goi -> Da tao app -> Shipper da lay -> Da giao / Bom hang / Huy don.
- **LLM Zero-Shot Ingestion:** Free-text Vietnamese parsing of messy chat pastes into structured draft entities.
- **Two-Phase Interactive Confirmation Card:** Visual preview card with [Xac nhan] and [Huy] buttons before DB persistence.
- **1-Tap Clipboard Copy Buttons:** Inline buttons leveraging Telegram CopyTextButton to paste recipient phone, address, and tracking code into carrier apps.
- **Date-Filtered Order Listings:** Fast views for Hom nay and Hom qua with compact status badges.
- **Manual Tracking Code Entry:** Quick 1-tap prompt to attach shipping codes from carrier receipts.

**Should have (competitive differentiators):**
- **Natural Language Order Search:** Free-text query parsing (e.g. tim don anh Tuan mua bang Tuan Vu) with confirmation card.
- **Daily Digest & Revenue Summary:** Morning checklist and evening reconciliation cards.
- **Customer Purchase History Lookup:** Search past cassette tape purchases by phone number.

**Defer (v2+):**
- **Direct Carrier API 2-Way Sync:** Out of scope. Requires complex carrier partner accounts and breaks on informal Vietnamese addresses.
- **Strict SKU / Barcode Inventory:** Cassettes are unique, vintage, or custom recordings; inventory tracking adds massive overhead. Raw free-text item lists suffice.
- **Multi-step Conversational Wizards:** Rigid forms frustrate elderly users; single paste + confirmation is preferred.
- **Web Dashboard / TMA:** Forces context switching and small mobile touch targets.

### Architecture Approach

The architecture follows a modular layered pattern separating presentation, ephemeral session state, LLM extraction, domain rules, and persistent SQLite storage. Complete diagrams and directory layouts are in ARCHITECTURE.md.

**Major components:**
1. **Security Whitelist Middleware:** Outer gateway inspecting update.effective_user.id against configured whitelist; drops unauthorized updates silently.
2. **Telegram Presentation Layer (bot/):** Handlers, formatters, and keyboard builders rendering elder-friendly UI with high-contrast emojis and large touch targets.
3. **LLM Extraction Service (llm/):** Dual-mode 9router wrapper converting natural Vietnamese chat into Pydantic models with schema fallback.
4. **Ephemeral Flow State Manager:** In-memory short-lived cache using 8-character UUID tokens to keep Telegram callback_data well under the 64-byte limit.
5. **Domain Lifecycle Engine (domain/):** Finite state machine enforcing legal order state transitions and preventing terminal state modification.
6. **Persistence Repositories (db/):** Parameterized SQLite queries managing normalized customers and immutable order snapshots with WAL concurrency.

### Critical Pitfalls

Complete analysis of technical failure modes and recovery procedures is detailed in PITFALLS.md.

1. **Callback Query Unanswered / 30s Timeout Trap:** Waiting for LLM extraction before calling query.answer() causes Telegram spinner timeouts and duplicate user taps. **Prevention:** Acknowledge callbacks immediately (await query.answer()) and edit the message into a loading status before long async jobs.
2. **BadRequest: Message is not modified Crash Loop:** Editing a Telegram message or inline keyboard to identical content raises fatal API exceptions. **Prevention:** Wrap all UI edit calls in try-except blocks that ignore Message is not modified.
3. **Vietnamese Address & Ward Hallucination:** LLMs attempt to complete or rewrite informal Vietnamese addresses (e.g. confusing merged wards or changing commune names), leading to shipping failures. **Prevention:** Retain raw, untouched recipient address text in orders and instruct prompts never to invent street or ward numbers.
4. **Colloquial Price & Currency Misparsing (k, tr, ngan):** Vietnamese shorthand (250k -> 250, 1tr2 -> 1.2) corrupts COD amounts. **Prevention:** Strict integer VND schema, explicit prompt few-shots, and automatic validation sanity checks (e.g. COD < 10,000 multiplied by 1,000 or flagged for confirmation).
5. **SQLite Concurrency File Lock (database is locked):** Simultaneous writes during async execution block database operations. **Prevention:** Enforce PRAGMA journal_mode = WAL;, set busy_timeout = 5000;, and keep database connection transactions short.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Core Foundation, Persistence & Security
**Rationale:** Database persistence and security whitelist must exist before any handler or UI can safely interact with state.
**Delivers:** Pydantic settings loading .env, SQLite schema initialization with WAL mode and foreign keys, normalized CustomerRepository and snapshot OrderRepository, and the Telegram User ID whitelist middleware.
**Addresses:** Whitelist security, customer profile database (multi-phone, multi-address), orders schema.
**Avoids:** Pitfall 5 (SQLite concurrency locks) and Pitfall 7 (Bot token leak and whitelist bypass).

### Phase 2: LLM Extraction Pipeline & Currency Rules
**Rationale:** The natural language parser must be verified against ambiguous Vietnamese texts independently before connecting it to Telegram UI callbacks.
**Delivers:** AsyncOpenAI client targeting 9router, Pydantic OrderDraft schema, robust prompt templates for colloquial cassette and address slang, and automated test suite covering tricky price formats (250k, 1tr2, coc 50k thu COD 200k).
**Addresses:** Vietnamese chat entity extraction without rigid form prompts.
**Avoids:** Pitfall 3 (address hallucination), Pitfall 4 (pricing misparsing), and Pitfall 9 (cassette title alterations).

### Phase 3: Ergonomic Ingestion & Confirmation Flow
**Rationale:** Connects the LLM extraction engine to Telegram via two-phase confirmation, fulfilling the core business value.
**Delivers:** Free-text message handler, ephemeral draft cache (8-char UUID tokens), interactive confirmation card with [Xac nhan] and [Huy], safe message edits, and atomic DB order creation upon user tap.
**Addresses:** Zero-shot order ingestion and hallucination guardrails.
**Avoids:** Pitfall 1 (callback query 30s timeout) and Pitfall 2 (Message is not modified exception).

### Phase 4: Order Lifecycle & 1-Tap Ergonomic Actions
**Rationale:** Once orders are saved, the merchant needs daily lifecycle transitions and low-friction mobile actions to dispatch parcels.
**Delivers:** 7-stage order state machine, detailed order inspection card, 1-tap clipboard copy buttons (CopyTextButton for phone, address, tracking code), manual tracking code prompt, and next-stage inline action buttons.
**Addresses:** Lifecycle tracking (Cho lam to Da giao), tracking code attachment, 1-tap copy UX.
**Avoids:** Pitfall 6 (elderly UI confusion / command memory) and Pitfall 2 (duplicate state transition crashes).

### Phase 5: Date Listings & Daily Management
**Rationale:** Daily order triage requires rapid morning and evening reviews without pagination complexity.
**Delivers:** Persistent Reply Keyboard (Tao don, Don hom nay, Don hom qua), compact list cards with status badges, and message splitting safeguards (send_safe_message).
**Addresses:** Date-filtered order listing, daily order count reviews.
**Avoids:** Pitfall 8 (Telegram 4096 character message length limit).

### Phase 6: Natural Language Order Search
**Rationale:** Natural language search is an enhancement built on top of an already populated database and verified LLM client.
**Delivers:** Free-text search handler, LLM query parameter extractor (SearchFilter), SQL fuzzy/phone matching, and interactive Did you mean? candidate selection cards.
**Addresses:** Natural language order search and lookup.
**Avoids:** Premature complexity during initial MVP operations.

### Phase Ordering Rationale

- **Data & Security first:** Eliminates structural refactoring and prevents data leaks or schema lockups before UI handlers are wired up.
- **LLM Pipeline isolated:** Benchmarks extraction accuracy on real Vietnamese texts with unit tests without running Telegram long polling.
- **Ingestion & Lifecycle core:** Delivers the end-to-end MVP workflow (chat paste -> confirm -> advance status -> copy to carrier app).
- **Search & Listings last:** Search requires existing database records and builds on verified LLM and repository abstractions.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (LLM Pipeline):** Dual-mode gateway routing on 9router. Some upstream providers reject OpenAI strict response_format schemas; prompt structure and fallback to json_object need rigorous testing on Vietnamese cassette edge cases.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Standard pydantic-settings and aiosqlite WAL configuration.
- **Phase 3 & 4 (Ingestion & Lifecycle):** Well-documented python-telegram-bot v20+ callback query patterns and state machines.
- **Phase 5 (Listings):** Standard parameterized SQLite date() queries and compact formatted strings.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core libraries (python-telegram-bot 22.8, aiosqlite 0.22.1, openai 3.37.0, pydantic 2.14.1) verified against PyPI and official specs. |
| Features | HIGH | Project scope and constraints directly validated against .planning/PROJECT.md and real-world Vietnamese low-tech e-commerce patterns. |
| Architecture | HIGH | Layered architecture, stateless callback tokens, and two-phase confirmation patterns verified against Telegram Bot API limits. |
| Pitfalls | HIGH | Specific edge cases identified (30s timeout, modified message error, Vietnamese currency slang, WAL locking, 4096 char limit). |

**Overall confidence:** HIGH

### Gaps to Address

- **9router Upstream Model Behavior:** 9router routes across heterogeneous LLM models (GPT-4o-mini, Gemini Flash, Claude Haiku, DeepSeek). Need to verify that the configured model consistently outputs valid JSON matching the Pydantic schema across varied Vietnamese text samples during Phase 2.
- **Telegram Bot API Version Support on Older Phones:** While CopyTextButton is supported in Telegram Bot API 7.3+, very old Telegram clients may ignore it. Mitigation: Format copyable phone numbers and addresses using both CopyTextButton and HTML code tags for universal tap-to-copy support.

## Sources

### Primary (HIGH confidence)
- python-telegram-bot Official Documentation (v20+ / v22.8) - Async ApplicationBuilder, CallbackQueryHandler, and CopyTextButton specifications.
- Telegram Bot API Specification - Callback query 30s timeouts, 64-byte callback_data limit, and 4096 character message limits.
- SQLite Official Documentation - Write-Ahead Logging (WAL) concurrency, foreign key pragma, and busy timeouts.
- OpenAI Structured Outputs Guide - Schema-enforced outputs via Pydantic.

### Secondary (MEDIUM confidence)
- 9router Gateway API Conventions - OpenAI-compatible proxy behavior and model routing.
- Field observations - Vietnamese social-commerce order workflows (Facebook/Zalo chat patterns, informal currency slang k/tr).

---
*Research completed: 2026-10-24*
*Ready for roadmap: yes*
