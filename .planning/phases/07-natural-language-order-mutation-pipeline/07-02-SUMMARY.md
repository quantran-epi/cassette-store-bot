---
phase: 07-natural-language-order-mutation-pipeline
plan: 02
subsystem: bot-handlers-and-concurrency
tags: [telegram, optimistic-locking, audit-trail, visual-diff, callback-query, keyboards]
requires:
  - phase: 07-natural-language-order-mutation-pipeline
    plan: 01
    provides: order_history, 3-way intent router, OrderMutationDelta, extract_mutation_delta
provides:
  - handler: handle_mutation_flow, handle_mutation_selection, handle_status_suggestion_selection
  - handler: handle_mutation_callback (^ord_mut_)
  - keyboards: render_mutation_diff_card, build_mutation_confirm_keyboard, build_mutation_disambiguation_keyboard, build_mutation_status_keyboard, get_suggested_next_statuses
  - db: mutate_order_with_lock with optimistic concurrency check
  - ui: 14-character divider constant DIVIDER per D-19 and spaced order lists
affects:
  - src/bot/keyboards.py
  - src/db/orders.py
  - src/bot/handlers/mutation.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/callbacks.py
  - src/bot/app.py
tech-stack:
  added: []
  patterns:
    - 14-char Unicode divider (──────────────) preventing mobile wrapping
    - Before ➡️ After visual diff card formatting showing only modified fields
    - Optimistic concurrency lock WHERE id=? AND updated_at=? with millisecond precision
    - 120s in-memory TTL expiry for interactive mutation drafts in context.user_data
    - 1-tap disambiguation buttons and contextual status suggestions
key-files:
  created:
    - src/bot/handlers/mutation.py
    - tests/test_mutation_card_and_lock.py
    - tests/test_status_suggestions.py
    - tests/test_mutation_handler_flow.py
  modified:
    - src/bot/keyboards.py
    - src/db/orders.py
    - src/bot/handlers/ingest.py
    - src/bot/handlers/callbacks.py
    - src/bot/app.py
    - src/services/intent_router.py
decisions:
  - "D-08/D-10: Multi-order match presents 1 button per order and immediately transitions to Visual Diff upon selection."
  - "D-09: 0 match returns friendly empty guidance with search tips."
  - "D-11: Visual Diff Card formats only changed fields with Before ➡️ After."
  - "D-12: 120s TTL expiry and cancel edits message in-place and clears all inline buttons."
  - "D-13: Contextual next status suggestions based on order lifecycle (CHO_LAM to SHIPPER_DA_LAY)."
  - "D-14: Successful confirmation edits diff card in-place to Updated Order Card with standard action buttons."
  - "D-15/D-17/D-18: Optimistic locking checks updated_at and notifies conflict with previous modifier details."
  - "D-19: Shortened section divider to 14 characters and added blank line separation between orders in list."
metrics:
  duration: 6m
  completed_date: "2026-10-25"
  tasks_completed: 3
  files_changed: 9
---

# Phase 07 Plan 02: Visual Diff Card UX, Optimistic Concurrency Engine & Handler Integration Summary

Full Telegram pipeline wiring, Visual Diff Card UX, 120s TTL management, optimistic locking concurrency engine, and audit logging for Natural Language Order Mutation.

## Performance & Architecture

- **Mobile Visual Diff Card**: `render_mutation_diff_card` displays only fields present in mutation delta using 14-character divider (`──────────────`) per D-11 and D-19, preventing visual line breaks on small phone screens.
- **Race-Free Optimistic Concurrency**: `mutate_order_with_lock` verifies `WHERE id = ? AND updated_at = ?` with millisecond precision (`strftime('%Y-%m-%d %H:%M:%f', 'now')`). If modified in-flight, it extracts the last modifier's name and diff from `order_history` to present an informative conflict notice per D-17 and D-18.
- **Elderly-Friendly Disambiguation**: When an intent matches 2 to 5 active orders, `handle_mutation_flow` generates 1-tap buttons per order (`[📦 Đơn #12 - Nam - 250.000 đ - Chờ làm]`). Tapping a button applies the draft delta and renders the Visual Diff card instantly without re-querying the LLM.
- **End-to-End Routing**: `handle_text_order` routes `MUTATE` intents to `handle_mutation_flow`, checking reply message order context and 0ms fast-path status regex before falling back to the 2-tier extractor.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unaccent parameter matching in active-first order search**
- **Found during:** Task 3 disambiguation test
- **Issue:** `find_orders_for_mutation` queried `unaccent(customer_name) LIKE ?` with raw Vietnamese string, which prevented accents from matching ASCII normalization.
- **Fix:** Normalized query keyword using `remove_accents(keyword.strip())` before passing to SQL parameter.
- **Files modified:** `src/db/orders.py`
- **Commit:** `1995151`

**2. [Rule 1 - Bug] Draft ID regex hex matching**
- **Found during:** Task 3 callback unit tests
- **Issue:** Test mock draft IDs included non-hex characters (`"testcf01"`), which failed `[a-f0-9]{8}` regex.
- **Fix:** Switched mock draft IDs to standard 8-character hex strings (`"11223344"`, `"aabbccdd"`).
- **Files modified:** `tests/test_mutation_handler_flow.py`
- **Commit:** `1995151`

**3. [Rule 1 - Bug] Audit history conflict summary handling dictionary vs string changes**
- **Found during:** Task 3 conflict handling test
- **Issue:** `v.get('old')` raised `AttributeError` when `v` in changes was a string rather than `{old: ..., new: ...}` dict.
- **Fix:** Added type check `isinstance(v, dict)` before calling `.get()`.
- **Files modified:** `src/bot/handlers/callbacks.py`
- **Commit:** `1995151`

## Key Decisions Made

- Enforced 120s TTL expiry for interactive mutation drafts in `context.user_data["pending_mutations"]`.
- Ensured in-place message editing upon confirmation, cancellation, or TTL timeout to keep chat history tidy for elderly users.
- Updated `Order` creation in `handle_order_callback` to store `created_by_user_id` and `created_by_name`.

## Verification

All 22 plan tests and all 214 total project tests pass:
```bash
./.venv/bin/pytest tests/test_mutation_card_and_lock.py tests/test_status_suggestions.py tests/test_mutation_handler_flow.py -v
```

## Self-Check: PASSED

- Created files exist:
  - `src/bot/handlers/mutation.py`: FOUND
  - `tests/test_mutation_card_and_lock.py`: FOUND
  - `tests/test_status_suggestions.py`: FOUND
  - `tests/test_mutation_handler_flow.py`: FOUND
- Task commits verified:
  - `132e136`: feat(07-02): visual diff card formatter, 14-char divider & status suggestions
  - `6991d70`: feat(07-02): optimistic locking database update & conflict resolution
  - `1995151`: feat(07-02): telegram mutation handler, callback router & pipeline wiring
