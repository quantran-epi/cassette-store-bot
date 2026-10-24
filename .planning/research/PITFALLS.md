# Pitfalls Research

**Domain:** Telegram Chatbot + LLM Order Management for Low-Tech/Elderly Vietnamese Users
**Researched:** 2026-10-24
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: Callback Query Unanswered / Blocking on LLM (30s Timeout Trap)

**What goes wrong:**
Telegram displays endless loading spinner on button, eventually pops up "Failed to respond" / "Bot is not responding" alert. User taps 5 more times in panic, triggering concurrent tasks that corrupt state or duplicate orders.

**Why it happens:**
`query.answer()` not called immediately or delayed until after slow LLM extraction (3–10s) or long DB write. Telegram requires `answerCallbackQuery` within 30 seconds, but UX degrades after 1 second if spinner stays.

**How to avoid:**
1. Call `await query.answer()` as first statement in callback handler (or right after state check).
2. For long operations: answer immediately with toast notice `await query.answer("Đang xử lý, bác chờ một chút nhé...", show_alert=False)`, edit message with "⏳ Đang bóc tách thông tin...", then dispatch async processing.
3. Debounce button: disable/remove keyboard immediately upon first tap.

**Warning signs:**
- Spinning clock icon on buttons in Telegram client.
- Telegram error log: `telegram.error.BadRequest: Query is too old and response timeout expired`.
- Duplicate orders created from single action.

**Phase to address:** Phase 1 (Core Bot & UX Framework)

---

### Pitfall 2: Telegram `BadRequest: Message is not modified` Crash Loop

**What goes wrong:**
Bot throws uncaught exception when editing message text or inline keyboard to identical content. Callback loop breaks, leaves user stranded without feedback.

**Why it happens:**
Calling `edit_message_text(text=same_text, reply_markup=same_markup)` triggers Telegram API error `BadRequest: Message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup`. Common in toggle buttons, refresh lists, or confirmation clicks.

**How to avoid:**
Wrap every `edit_message_text` / `edit_message_reply_markup` in try-except block catching `telegram.error.BadRequest`:
```python
try:
    await query.edit_message_text(text=new_text, reply_markup=markup)
except telegram.error.BadRequest as exc:
    if "Message is not modified" in str(exc):
        pass  # safe to ignore
    else:
        raise
```

**Warning signs:**
- Sentry/logs filled with `BadRequest: Message is not modified`.
- Buttons freeze when tapped twice.

**Phase to address:** Phase 1 (Core Bot & UX Framework)

---

### Pitfall 3: Vietnamese Address & Boundary Hallucination (Huyện vs Quận, Xã vs Phường)

**What goes wrong:**
LLM misinterprets Vietnamese shorthand address strings (e.g. "p11 q tân bình", "xã tân triều thanh trì hn", "ấp 3 mỹ hạnh nam đức hoà"). Extracts wrong administrative level or invents missing components, causing shipper delivery failure or returned package (bom hàng).

**Why it happens:**
- Ambiguity in colloquial abbreviations: "P." (Phường / Phố), "Q." (Quận), "TX" (Thị xã), "TT" (Thị trấn), "TP" (Thành phố).
- Recent administrative mergers in Vietnam (e.g. Thủ Đức, sáp nhập phường/xã).
- Pure zero-shot LLM without structural schema often lumps street and ward into name field.

**How to avoid:**
1. Pydantic schema with structured fields (`raw_address`, `recipient_name`, `phone`, `items`, `cod_amount`).
2. Keep `raw_address` untouched as primary field for copy-pasting into shipping app.
3. LLM prompt instructs: "Giữ nguyên địa chỉ gốc đầy đủ, không tự ý suy đoán thêm bớt số nhà/phường xã nếu khách không nói."
4. Confirmation card displays exact address with 1-tap copy button (`copy_text` or mono format) so owner can verify before saving.

**Warning signs:**
- Shippers calling shop owner complaining address incomplete or fake.
- Extracted address missing house number or ward present in original text.

**Phase to address:** Phase 2 (LLM Extraction Pipeline)

---

### Pitfall 4: Currency & Mixed Price Parsing Failure ("k", "tr", "ngàn", "đồng", "lít", "củ")

**What goes wrong:**
LLM extracts "250k" as 250, "1tr2" as 1.2 or 1200, "500 ngàn" as 500, or confuses COD amount with shipping fee / deposit. Result: shop loses money or overcharges COD.

**Why it happens:**
Vietnamese conversational shorthand has multiple colloquial formats:
- `250k` = `250.000`
- `1tr2` / `1tr200` = `1.200.000`
- `nửa triệu` = `500.000`
- `300` (in cassette context) = `300.000`
- Confusing "cọc 100k còn lại thu COD" vs "tổng tiền 400k".

**How to avoid:**
1. Strict LLM system prompt with concrete few-shot examples of Vietnamese slang.
2. Output schema requires integer VND (`cod_amount: int` in Dong, e.g. `250000`, never decimal or string).
3. Sanity check rule in code: if cassette order COD < 10000 (e.g. 250), auto-multiply by 1000 or flag warning for owner verification.
4. Total display always formatted with dot separators: `250.000 đ` (never `250000`).

**Warning signs:**
- Order saved with COD = 250 đ.
- Discrepancy between customer text and extracted amount on confirmation card.

**Phase to address:** Phase 2 (LLM Extraction Pipeline)

---

### Pitfall 5: SQLite Concurrency Lock in Async Python (`sqlite3.OperationalError: database is locked`)

**What goes wrong:**
When bot processes incoming message while another background task or webhook write runs, SQLite raises `OperationalError: database is locked`. Bot crashes or drops order.

**Why it happens:**
Default SQLite connection mode in Python is rollback journal. Multiple async tasks sharing connections across thread/event-loop boundaries or running long write transactions block all reads and writes.

**How to avoid:**
1. Enable WAL mode on DB initialization:
   ```python
   PRAGMA journal_mode=WAL;
   PRAGMA synchronous=NORMAL;
   PRAGMA busy_timeout=5000;  # wait up to 5s before failing
   ```
2. Single dedicated DB writer or use `aiosqlite` with short-lived connections per request.
3. Never hold open SQLite transaction across LLM network calls. Fetch data -> close DB -> call LLM -> open DB -> write result.

**Warning signs:**
- `sqlite3.OperationalError: database is locked` in logs during simultaneous clicks.
- Slow query responses when file size grows.

**Phase to address:** Phase 1 (Data Persistence & Schema)

---

### Pitfall 6: Low-Tech Trap: Command Menus, Small Text & Pagination Confusion

**What goes wrong:**
Elderly owner forgets `/order_status_update_342`, cannot read tiny Telegram copy text, gets lost across 10-page list, or taps wrong small button on mobile touch screen. Shop owner stops using bot, reverts to paper notebook.

**Why it happens:**
Developers build bot for themselves (CLI mindset, compact data density, slash commands, deep sub-menus). Low-tech users have presbyopia (viễn thị), trembling fingers, zero familiarity with command syntax.

**How to avoid:**
1. **Zero required slash commands** for daily operations: all guided by big Inline Keyboard buttons with emoji (`📦 Đơn mới`, `🚚 Chờ giao`, `✅ Đã xong`).
2. **One-tap copy format:** Use Telegram MarkdownV2 backtick mono block `` `0912345678` `` or modern `CopyTextButton` so tapping copies directly to clipboard without selecting text manually.
3. **Chunked card view instead of infinite scroll/deep pagination:** Show today's 5 most recent orders with clear status badges, filter by date buttons (`Hôm nay`, `Hôm qua`).
4. **Always provide cancel/back escape hatch:** Every confirmation dialog has clear red `❌ Huỷ bỏ` button.

**Warning signs:**
- User types question mark or "alo bot ơi" instead of commands.
- User complains text is too small or cannot copy phone number to call shipper.

**Phase to address:** Phase 1 & Phase 3 (UX & Order Management)

---

### Pitfall 7: Telegram Bot Token Leak & Whitelist Bypass

**What goes wrong:**
Unauthorized Telegram users discover bot, view customer names, phone numbers, home addresses, or tamper with orders. Bot token leaked to Git repo triggers instant bot hijacking.

**Why it happens:**
Hardcoding token in source code; checking whitelist only on `/start` command instead of global middleware/filter on every incoming `Update`.

**How to avoid:**
1. Token and allowed User IDs strictly loaded from `.env` or local config file (in `.gitignore`).
2. Global `BaseHandler` / filter in `python-telegram-bot` checking `update.effective_user.id in WHITELIST_USER_IDS`. Drop/ignore non-whitelisted updates silently (no response to prevent reconnaissance).
3. Validate whitelist at startup: if empty, refuse to start bot.

**Warning signs:**
- Unknown user IDs appearing in Telegram logs.
- Bot token flagged by GitHub secret scanning.

**Phase to address:** Phase 1 (Security & Core Infrastructure)

---

### Pitfall 8: Telegram Message Length Limit (4096 Characters) on Order Lists

**What goes wrong:**
Querying order list for a busy day or monthly summary exceeds 4096 characters. Telegram rejects request with `BadRequest: Message is too long`. Bot crashes or shows blank screen.

**Why it happens:**
Naively concatenating 30+ order details with full customer address and item breakdown into a single message string.

**How to avoid:**
1. Split list messages into compact summaries (e.g. 5 orders per message) or paginate.
2. Summary view shows only: `#ID - Tên khách - SĐT - COD - Trạng thái` (1 line per order).
3. Detail view opens only when tapping specific order button.
4. Utility function helper: `send_safe_message()` that automatically splits text at newline boundaries if length > 3800 chars.

**Warning signs:**
- `BadRequest: Message is too long` when running "Xem đơn hôm nay" on days with >15 orders.

**Phase to address:** Phase 3 (Order Management & Queries)

---

### Pitfall 9: Cassette Title & Audio Format Ambiguity

**What goes wrong:**
LLM misinterprets cassette titles, quantities, or formats: "Băng Tuấn Vũ 2 cuốn, Khánh Ly 1" extracted as 1 item or prices blended together. "Băng gốc" vs "Băng thu lại" vs "Phôi Maxell UD" confused.

**Why it happens:**
Music cassettes have idiosyncratic naming: singer name, album title, tape brand (TDK, Maxell, Sony), tape type (Type I, Normal, CrO2 Type II), original vs recorded. LLM may attempt to canonicalize or "correct" spelling of old Vietnamese music albums.

**How to avoid:**
1. Store goods as verbatim text line items (`items_text`), do not enforce rigid catalog lookup in DB.
2. Prompt LLM: "Không sửa tên ca sĩ, tên băng nhạc hoặc loại phôi băng. Giữ nguyên vẹn văn bản người bán viết."
3. Highlight extracted item list in confirmation preview for easy verification.

**Warning signs:**
- Extracted items list altered spelling of old albums or omitted tape quantities.

**Phase to address:** Phase 2 (LLM Extraction Pipeline)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Storing SQLite DB in working directory without backup mechanism | Zero config, instant start | Single disk failure or accidental delete destroys all customer records | Never. Implement daily auto-backup to safe directory or dump |
| Calling LLM synchronously inside Telegram handler | Simpler code, no async queue | Blocks whole event loop; bot unresponsiveness for all interactions | Never. Must use `asyncio` / async client |
| Relying solely on regex for phone/address extraction | Free, zero API cost | Fails on 60% of natural Vietnamese chat inputs | Never as sole extractor; OK as pre-validation fallback |
| Hardcoding prompt strings inside bot handlers | Quick prototyping | Cannot tune extraction without redeploying code | MVP only; move to dedicated `prompts.py` or config in Phase 2 |
| Keeping all states in memory (`user_data`) | Easy session management | Server restart / bot crash wipes out active confirmation dialogs | MVP only if fallback prompt asks user to resend text |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **9router / OpenAI Gateway** | No timeout configured on HTTP client; hangs indefinitely on gateway outage | Set explicit `timeout=15.0` on OpenAI client; catch `TimeoutException` and prompt owner to confirm manually |
| **9router Model Drift** | Hardcoding specific model name in code that gets deprecated or rate-limited | Configurable model string in `config.py` / `.env`, fallback to secondary model on 5xx error |
| **Telegram Callback Data** | Exceeding 64-byte limit in `callback_data` (e.g. putting full order UUID or JSON) | Use compact callback prefixes: `ord:view:12` or `st:done:12` (short IDs) |
| **Telegram MarkdownV2** | Forgetting to escape special characters (`_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`) causing parse error | Use helper escape function or send plain text / HTML mode (`parse_mode='HTML'`) which is far less fragile |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Unindexed SQLite Search** | Slow query when searching orders by customer phone or name | Add DB indexes: `CREATE INDEX idx_orders_phone ON ...` | > 1,000 orders |
| **Unbounded Order History Query** | Bot freezes when rendering "Tất cả đơn hàng" | Limit query results: `LIMIT 20` with next/prev buttons | > 50 orders |
| **Polling Lag on Webhook/Long Polling** | Delayed response by several seconds | Ensure long polling timeout = 30s, drop pending updates on restart `drop_pending_updates=True` | Bot restarts |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Missing Telegram User ID Whitelist check on callback queries | Unauthorized user can click buttons or alter orders if message forwarded | Check whitelist on every handler including `CallbackQueryHandler` |
| Leaking Telegram Bot Token or LLM API Key in public Git | Bot takeover, wallet depletion on LLM gateway | `.env` file excluded via `.gitignore`, check with `git status` |
| Exposing customer PII in logs | Customer addresses and phones exposed in plaintext server logs | Mask phone numbers in debug logs (`0912***789`) |

---

## UX Pitfalls (Elderly / Low-Tech Focus)

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Small copyable text | Owner struggles to select phone number or address to paste into GHTK/GHN app | Use `<code>0901234567</code>` in HTML mode — tapping copies immediately to clipboard |
| English technical errors ("Error 500: Internal server error") | Owner panics, thinks they broke the system | Friendly Vietnamese: "⚠️ Dạ bot đang bận một chút, bác bấm lại nút bên dưới nhé!" |
| Deep hierarchical menus | Owner gets lost, doesn't know how to return home | Max 2 button levels; always include "🔙 Quay lại" and "🏠 Về trang chủ" |
| Silent success without visual feedback | Owner taps multiple times unsure if action worked | Show checkmark badge "✅ Đã lưu đơn #12 thành công!" and update original message |
| Strict formatting requirements | Owner frustrated because input "didn't follow template" | Accept any free-text format; let LLM parse; show confirmation card |

---

## "Looks Done But Isn't" Checklist

- [ ] **LLM Extraction:** Works on clean test input — verify it handles typo-ridden, unpunctuated Vietnamese messages without house numbers.
- [ ] **Inline Buttons:** Works when clicked once — verify it doesn't crash on rapid double-clicking or unchanged message edits.
- [ ] **Whitelist Check:** Blocks non-whitelisted text messages — verify it ALSO blocks forwarded messages and callback queries.
- [ ] **Order Pricing:** Parses standard "200k" — verify it handles "cọc 50k thu 150k", "1tr2", and "2 băng 300 ngàn".
- [ ] **Database Setup:** Works under single test runner — verify concurrent callback taps don't trigger `database is locked`.
- [ ] **Copy to Shipping App:** Text displayed on screen — verify phone and address can be copied with a single finger tap on mobile.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| LLM Gateway Outage | LOW | Switch to manual text input prompt with guided buttons; update endpoint in `.env` |
| SQLite DB Corrupted / Locked | MEDIUM | Restore from latest daily backup file `.db.bak`; WAL checkpoint recovery |
| Erroneously Extracted Order Saved | LOW | Provide 1-tap "✏️ Sửa đơn" or "🗑️ Huỷ đơn" button directly on order detail card |
| Bot Token Leaked | LOW | Revoke token via `@BotFather`, update `.env`, restart bot process |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Telegram Callback Timeout & `Message is not modified` | Phase 1 (Core Bot & UX Framework) | Unit tests simulating duplicate callbacks and edit identical text |
| SQLite Concurrency & Locking | Phase 1 (Data Persistence & Schema) | Concurrency stress script with 10 simulated simultaneous writes |
| Security: Token Leak & Whitelist Bypass | Phase 1 (Core Bot & Security) | Automated test verifying non-whitelisted ID receives zero response |
| Vietnamese Address & Cassette Goods Extraction | Phase 2 (LLM Extraction Pipeline) | Test suite with 20 real-world messy Vietnamese cassette order messages |
| Mixed Pricing Parsing ("k", "tr", "ngàn") | Phase 2 (LLM Extraction Pipeline) | Edge-case price test cases verifying correct integer VND |
| Message Length Limit & Elderly 1-Tap Copy UX | Phase 3 (Order Management & UI) | Mobile manual testing on real Telegram app checking copy behavior |

---

## Sources

- python-telegram-bot Official Documentation (v20+ async patterns & error handling)
- Telegram Bot API Specification (Callback queries, message limits, button restrictions)
- SQLite Official Documentation (Write-Ahead Logging - WAL mode & concurrency)
- Production experience with Vietnamese NLP and conversational e-commerce patterns

---
*Pitfalls research for: Cassette Store Telegram Chatbot*
*Researched: 2026-10-24*
