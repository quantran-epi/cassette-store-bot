---
status: complete
date: 2026-10-26
quick_id: 261026-kt4
---

# Quick Task 261026-kt4 — Summary

## What changed

`tape_artist_json` added as a fourth derived tape column, kept strictly separate from
`tapes_json` (phôi) and `tape_genre_json` (genre only).

| Layer | Change |
|---|---|
| `src/services/tape_parser.py` | `TapeColumns` NamedTuple (quantity/tapes/genres/artists); `build_tape_columns(..., llm_artists)`; `_normalize_names` dedupe case-insensitive; `format_artist_summary` |
| `src/models/order.py` | `Order.tape_artists` |
| `src/db/schema.py` | `tape_artist_json TEXT` + `ALTER TABLE` migration |
| `src/db/orders.py` | create/read/recompute (mutation on `items_text`) |
| `src/models/extractor.py` | `ExtractedOrder.tape_artists` + validator |
| `src/models/mutation.py` | `new_tape_artists` |
| `src/services/extractor.py` | rule 4b + corrected Chế Linh example (`tapes` = `không rõ`, artists carry the name) |
| `src/services/mutation_extractor.py` | artists filled when `new_items_text` present |
| `src/bot/handlers/ingest.py`, `callbacks.py`, `keyboards.py` | preview/detail/diff show `🎤 CA SĨ`, HTML-escaped |
| `src/services/order_search.py` | `tape_artist_json` documented; artist-filter example; NULL disclosure |

## Two real defects found by running the app, not by tests

1. **Artist leaked into the phôi label.** Deterministic fallback turned
   `3 cuốn Thanh Tuyền` into tape label `cuon thanh tuyen`. Fixed: a generic medium
   word (`băng/cuốn/phôi/đĩa`) with no specific brand in the phrase now yields
   `khong ro`; `6 băng maxell 90p` still yields `maxell 90p`.
2. **`OR tape_quantity IS NULL` in the prompt filter** made every legacy row match every
   filter (`bao nhiêu băng Chế Linh` counted non-Chế-Linh orders). Replaced with a
   subquery for the disclosure count; added a regression test that no worked example
   contains the banned clause.
3. **Model silently dropped the "old orders not counted" caveat.** Added
   `_append_missing_tape_note` so the disclosure is deterministic, not model-dependent.

## Verification

- `python -m pytest tests/ -q` → **313 passed**.
- Live gateway extraction: `2 cuốn Chế Linh` → tapes `không rõ ×2`, artists `["Chế Linh"]`,
  genres `["nhạc vàng","bolero"]`; `6 băng maxell 90p` → tapes `maxell 90p ×6`.
- DB copy migration: 7 legacy rows keep all tape columns NULL; detail card renders `—`.
- Seeded copy aggregate queries: `bao nhiêu băng Chế Linh` → 2 tapes + disclosure of 7
  old orders; `bao nhiêu băng nhạc vàng` → 2 + disclosure.
- Mutation: items change recomputes all four columns; unrelated field leaves them intact.

## Notes

- Old orders were **not** backfilled (explicit choice). Individually requested later.
- Nothing committed — working tree also holds earlier quick-task changes.
