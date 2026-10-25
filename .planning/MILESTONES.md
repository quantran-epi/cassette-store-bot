# Milestones

## v1.0 MVP (Shipped: 2026-10-25)

**Phases completed:** 4 phases, 11 plans, 0 tasks
**Closeout type:** override_closeout (stale verification flags on Phases 2 & 3 from later phase touches; milestone audit passed 19/19 requirements, 110/110 tests)
**Stats:** 106 files modified (+18,688 / -29), 7,134 lines of Python, 128 commits, 2 days (2026-10-24 → 2026-10-25)

**Key accomplishments:**
- Async SQLite database with WAL mode, Telegram User ID whitelist security gate at Group -1, customer & order relational schemas with customer snapshot and photo attachments.
- Vietnamese free-text order ingestion via 9router LLM gateway (OpenAI-compatible) with 2-tier fallback (`parse` + `json_object`), VND currency normalization, and 2-phase interactive confirmation card.
- Returning customer intelligence: in-memory draft orders, multi-address picker, customer order history stats with prominent `BOM_HANG` alert banner.
- Ergonomic low-tech UX: fixed 2x2 Reply Keyboard, UTC+7 date-filtered order lists, 1-tap `CopyTextButton` (phone/address/tracking), 1-tap lifecycle status transitions, and album debounce buffer (500ms).
- Natural language order search: Text-to-SQL engine with unaccent Vietnamese matching, conversational search detection, and suggestion confirmation cards with context-preserving back navigation.

---
