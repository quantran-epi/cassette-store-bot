# Design — structured tape quantity + type on orders

Decisions already locked with the user. Do not re-ask.

| Decision | Choice |
|---|---|
| Storage | `tape_quantity INTEGER`, `tapes_json TEXT` (phôi: hãng/độ dài), `tape_genre_json TEXT` (thể loại) |
| Extraction point | At order creation AND at mutation when `items_text` changes |
| Existing 6 orders | Left NULL — no backfill |

## The invariant (most important)

`tape_quantity` is **derived**, never trusted from the model:

```
tape_quantity == sum(item["qty"] for item in tapes_json)
```

One helper computes all three values from a single source. If the LLM returns a
`tape_quantity` that disagrees with its own tape list, the sum wins — the model's own
number is discarded. If the LLM returns no tapes, derive deterministically from
`items_text`. This makes divergence structurally impossible.

## Data shape

```json
// tapes_json — phôi băng (what the shop must pull from stock)
[{"label": "sony 90p", "qty": 6}, {"label": "maxell 90p", "qty": 1}]

// tape_genre_json — thể loại nội dung (best effort, [] when unstated)
["nhạc vàng", "hải ngoại"]
```

`label` is free text normalised to lowercase; do not force a closed enum — the shop's
vocabulary is open-ended ("ud xám 90p", "băng MaxellLN90p").

## Derivation rules (deterministic fallback)

Verified against the real item strings in `cassette_store.db`:

| # | items_text | expected qty |
|---|---|---|
| 1 | `1 Lk Tuấn Vũ, 2 Chế Linh, ..., 6 Giao Linh..., 6 sony 90p` | 6 |
| 2 | `Khánh ly, Duy khánh, Thanh thuý, 3 ud xám 90p` | 3 |
| 3 | `cd thói đời, băng MaxellLN90p (1 băng)` | 1 |
| 4 | `1 Ngọc Sơn vol1, 5 Băng ca sĩ khác (6 sony 90p)` | 6 (paren spec = phôi for those tapes, not extra) |
| 5 | `Tuấn Vũ, ..., 6 băng maxell 90p` | 6 |
| 6 | `1 băng như ảnh ko dán tem` | 1 |

Rules:
1. A parenthesised `<N> <medium>` spec — `(6 sony 90p)`, `(1 băng)` — is the phôi for the
   tapes already listed; it wins and is **not** added to other counts.
2. Otherwise sum every `<N> <unit>` where unit ∈ băng/cuốn/phôi/đĩa/ud/ur/hf/sony/maxell/tdk/cd.
3. If neither matches: one tape per comma-separated entry, minimum 1 for non-empty text.
4. Empty items_text → 0 tapes, empty lists, `tape_quantity = 0`.

`label` = the matched unit phrase with the count stripped ("sony 90p", "ud xám 90p"),
lowercased and unaccented for grouping but kept readable.

## Consistency risk (must be handled)

`tapes_json` is derived data sitting next to `items_text`, its source. Divergence would make
"bao nhiêu băng Sony" silently wrong. Mitigation:

- **Write path only.** The three columns are written exclusively through one helper; no
  other code assigns them.
- **Recompute on every items_text change.** In `mutate_order_with_lock`, if `items_text`
  changes, recompute all three from the new text — never merge old tapes with new text.
  This must run inside the same transaction as the UPDATE.
- **Read path never patches.** Query-time code treats the columns as authoritative and
  does not re-derive.

## NULL semantics

Old orders keep `tape_quantity IS NULL`. Queries must distinguish NULL from 0:

- `SUM(COALESCE(tape_quantity, 0))` for totals.
- The Text-to-SQL prompt must state that NULL means "đơn cũ chưa có dữ liệu số lượng" and
  the answer should say so when the counted order set includes NULLs.
- Show "—" (not "0") on order cards for NULL.

## Files and touch points

| Area | File | Change |
|---|---|---|
| Parsing | new `src/services/tape_parser.py` | `parse_tapes_deterministic(items_text) -> TapeBreakdown`; `build_tape_columns(items_text, llm_tapes, llm_genres)` returns the 3 DB values and enforces the invariant |
| Schema | `src/db/schema.py` | 3 columns + `ALTER TABLE` migration in the existing `PRAGMA table_info` block |
| SQLite fn | `src/db/connection.py` | `tape_count()` delegates to the parser so there is one implementation |
| Model | `src/models/order.py` | `tape_quantity: int \| None`, `tapes: list[TapeItem]`, `tape_genres: list[str]` |
| LLM schema | `src/models/extractor.py` | `TapeItem(BaseModel)`; `ExtractedOrder.tapes`, `.tape_genres` + prompt guidance/examples |
| Creation prompt | `src/services/extractor.py` | few-shot examples showing tapes + genres; validator reconciliation |
| Mutation schema | `src/models/mutation.py` | `new_tapes`, `new_tape_genres` (optional — only used when items_text changes) |
| Mutation prompt | `src/services/mutation_extractor.py` | rule: when new_items_text is present, also fill new_tapes/new_tape_genres |
| Persistence | `src/db/orders.py` | `create_order` INSERT 3 columns; `_row_to_order` read them; `mutate_order_with_lock` recompute when items_text changes |
| Draft → order | `src/bot/handlers/ingest.py`, `callbacks.py` | carry the 3 values in the draft, persist on confirm |
| Cards | `src/bot/keyboards.py`, `ingest.py`, `search.py` | show tape breakdown in preview card, order detail, and mutation diff |
| Search prompt | `src/services/order_search.py` | `tape_quantity`/`tapes_json`/`tape_genre_json` documented; NULL rule; examples for "bao nhiêu băng" and "bao nhiêu băng Sony" |

## Tests that must exist

- Parser: the 6 real strings above, plus empty string, plus a string with no digits.
- Invariant: LLM returns `tape_quantity=99` with tapes summing to 6 → stored 6.
- Invariant: LLM returns no tapes → deterministic fallback used, non-zero for non-empty text.
- Persistence: create order with tapes → columns round-trip through `_row_to_order`.
- Mutation: change `items_text` only → all three columns recomputed, no stale tapes.
- Mutation: change unrelated field → tape columns untouched.
- Search prompt: contains the new columns and the NULL rule.
