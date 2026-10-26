# Investigation — 4 reported defects (2026-10-26)

All findings verified against source. Read this before planning; do not re-investigate.

## Issue 1 — Album of photos saves only the first photo

**Symptom:** user sends 3 photos with one caption when creating an order → saved order has 1 photo.

**Root cause:** `src/bot/app.py` builds the app without `.concurrent_updates(...)`. PTB docs: "If not called, updates will be processed one by one." In
`src/bot/handlers/ingest.py::handle_photo_order`, the media-group path does
`await asyncio.sleep(MEDIA_GROUP_DEBOUNCE_SECONDS)` (0.8s) **inside the handler**. That sleep blocks
the sequential update pump, so photos 2 and 3 sit in the queue. When photo 1 finishes, it writes
`_PROCESSED_MEDIA_GROUPS[media_group_id]`. Photos 2 and 3 then reach the handler, hit the guard

```python
if media_group_id in _PROCESSED_MEDIA_GROUPS:
    return
```

at `ingest.py:420`, and are silently dropped. Net effect: exactly one photo per album.

`tests/test_ingest.py::test_media_group_album_bundled_single_preview` passes only because it drives
the three handlers with `asyncio.gather(...)`, i.e. concurrently — which never happens in production.

**Required fix:** never block the update pump. Initialize the buffer + schedule the debounce
finalizer as a background task (`context.application.create_task(...)`, falling back to
`asyncio.create_task`) and return immediately. Guard against scheduling the finalizer twice for the
same group (store the task handle on the buffer). Keep the `_PROCESSED_MEDIA_GROUPS` dedupe and the
60s prune. Update the existing test to await the background finalizer (e.g. `await asyncio.sleep(...)`
after gather) and assert 3 photos. Do NOT enable `concurrent_updates` globally — the bot mutates
`context.user_data` per user; keeping updates sequential is intentional.

## Issue 2 — No customer search

**Symptom:** `tìm khách 0903626566`, `tìm khách anh Tuấn`, `tìm khách Hà Nội`, any combination →
falls into the orders Text-to-SQL path, returns an aggregate/summary, never a customer profile.

**Root cause:** search only ever emits SQL against the `orders` table
(`src/services/order_search.py::SYSTEM_PROMPT_TEXT_TO_SQL_TEMPLATE`). Nothing in
`src/bot/handlers/search.py` routes customer queries, and `src/db/customers.py` has no search
function (`get_customer_by_phone` is exact-match only).

**Required fix:** add a deterministic (no LLM needed) customer lookup that runs before the
Text-to-SQL pipeline:

- New `src/db/customers.py::search_customers(db, query, limit=5) -> list[Customer]`.
  Build a per-customer haystack of name + all phones + all addresses + notes, then require every
  substantive token to match (accent-insensitive, whole-word) using the existing `word_match`
  SQLite function registered in `src/db/connection.py`. Phones need a substring fallback because
  `word_match` uses `\b` boundaries and a partial phone like `987` has none.
  Reuse the filler-stripping idea from `src/db/orders.py::find_orders_for_mutation`
  (`khach`, `khách`, `tim`, `tìm`, `cua`, `của`, `cho`, `sdt`, `so`, `dien`, `thoai`, `ten`,
  `dia`, `chi`), plus honorific handling (`anh`, `chi`, `bac`, `ong`, `co`, `chu`, `em`).
- Intent detection: `is_customer_search(query)` — true when a search prefix
  (`tìm`, `tra cứu`, `kiểm tra`, `xem`, `khách`-first forms) co-occurs with the word `khách`
  (accent-insensitive). Route this in `search.py::process_search_query` **before** the LLM call.
- Rendering: 1 match → `render_customer_detail_card` (`src/bot/keyboards.py`, already exists) with
  stats from `get_customer_order_stats` and order history page 1, plus paging callbacks.
  Multiple matches → a compact chooser card, one button per customer, callback prefix `cus_v:`.
  Zero matches → friendly empty card telling the user which fields can be searched.
- Callbacks: handle `cus_pg:{customer_id}:{page}` and `cus_bk:{search_id}` in
  `src/bot/handlers/search.py` and register the pattern in `src/bot/app.py`
  (existing `^sch_` handler registration is the model to follow).

Keep this deterministic — do not add LLM cost for customer lookup.

## Issue 3a — "có bao nhiêu băng" answers the order count instead of tape count

**Symptom:** order contains `6 băng maxell`; asking "có bao nhiêu băng" returns the number of orders.

**Root cause:** `items_text` is free text; the schema prompt
(`src/services/order_search.py`) gives the model no way to count cassettes, so it falls back to
`COUNT(*)` over orders.

**Required fix:** register a SQLite function `tape_count(items_text)` in
`src/db/connection.py` (alongside `unaccent` / `word_match`) and document it in the Text-to-SQL
prompt:

- Sum quantities written against a medium/unit word: `(\d+)\s*(băng|cuốn|cuon|phôi|phoi|đĩa|dia|ud|ur|hf|sony|maxell|tdk|cd)\b` and the parenthesised forms `(6 sony 90p)`.
- Include bare leading quantities when the following phrase is a cassette/artist item (`1 Chế Linh`) — but **do not** count a leading number when it is a track index followed by a title on an enumerated list; treat a comma-list where every entry is `N <title>` as track numbering and count such entries as 1 each.
- Never return 0 for a non-empty `items_text`: fall back to counting comma-separated items as 1 tape each.
- Prompt rule to add: questions about `băng`/`cuốn`/`phôi` quantity (not order count) must use
  `SUM(tape_count(o.items_text)) AS total_tapes`, and the answer must use that column.

Keep the heuristic documented as an estimate — add a `ponytail:` comment naming the ceiling.

## Issue 3b — "khung giờ nào bán được nhiều đơn nhất" says no information

**Root cause:** the Text-to-SQL prompt only documents `datetime(created_at, '+7 hours')` and
`date(...)`. It documents nothing about hour-of-day or weekday grouping, so the model either emits
unsupported SQL or a shape the aggregate classifier rejects.

**Required fix:** add explicit prompt rules/examples:

- Hour bucket: `strftime('%H', o.created_at, '+7 hours')` → group and order by count DESC.
- Weekday bucket: `strftime('%w', o.created_at, '+7 hours')`.
- Note that `created_at` is stored UTC and every bucket expression must apply `'+7 hours'`.
- Add a worked example to the prompt: "khung giờ nào bán được nhiều đơn nhất" →
  `SELECT strftime('%H', created_at, '+7 hours') AS hour, COUNT(*) AS total_orders FROM orders GROUP BY hour ORDER BY total_orders DESC LIMIT 1`.

## Issue 4 — MIXED results say "danh sách chi tiết thì chưa có bác nhé"

**Root cause:** in `src/services/order_search.py::_execute_search_statements`, MIXED summarises the
aggregate by calling `summarize_aggregate_result` with **only** the aggregate rows. The summariser
(`SYSTEM_PROMPT_SUMMARY`) is free to state that no detail list exists, and the user sees that claim
stacked above the actual list the bot renders itself.

**Required fix:**

- Add a summary-prompt rule: the result is only the statistics half; the order list is rendered
  separately by the bot below the answer; never state that a detail list is missing or unavailable.
- Add a deterministic post-filter in `summarize_aggregate_result` (or at the MIXED call site) that
  strips sentences containing `danh sách` + (`chưa có` | `không có` | `chưa`), so the regression
  cannot reach the user even if the model ignores the instruction. Strip whole sentences, keep the
  rest, and fall back to the raw summary when everything was stripped.

## Verification expectations

- `pytest tests/` — all existing tests pass, plus new tests covering: 3-photo album persisted,
  customer search by name/phone/address token combinations, `tape_count` on the real item strings
  from `cassette_store.db`, hour-bucket prompt guidance, and the MIXED summary post-filter.
- Manual smoke: `python -m pytest tests/test_ingest.py -q` and `python -m pytest tests/test_order_search.py -q`.
