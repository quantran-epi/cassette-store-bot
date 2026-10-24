# Feature Research: Cassette Store Telegram Chatbot

**Domain:** Telegram Retail Order Management Chatbot (Small Low-Tech Merchant)
**Researched:** 2026-10-24
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features required for basic operations. Missing any breaks daily workflow.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Customer Profile (Multi-phone, Multi-address, Notes) | Repeat customers use alternate phones or shipping addresses; notes track past preferences or delivery quirks | MEDIUM | SQLite schema: `customers` (1) to `customer_phones` (N) and `customer_addresses` (N). Auto-match on phone lookup during ingestion. |
| Order Lifecycle Tracking (7-stage state machine) | Cassette preparation requires distinct craft steps (recording tape, printing j-card, packaging, dispatch, delivery) | LOW | Stages: `Chờ làm` -> `Đang làm` -> `Đã đóng gói` -> `Đã tạo đơn trên app` -> `Shipper đã lấy` -> `Đã giao thành công` / `Bom hàng` / `Huỷ đơn`. Persisted as string enum column with indexed queries. |
| Payment Method & Split Accounting (COD vs Banking) | Merchant must separate prepaid banking revenue from pending cash collection by carrier | LOW | Fields: `payment_method` (`BANKING` or `COD`), `total_amount`, `cod_amount`. If `BANKING`, `cod_amount = 0`. |
| Tracking Code Entry (`Mã vận đơn`) | Carrier tracking number needed to verify status on external carrier apps (GHTK, GHN, ViettelPost) | LOW | Text column on order. Updated via 1-tap button prompt or parsed from chat text. |
| Date-filtered Order Listing (`Hôm nay`, `Hôm qua`, Date) | Merchant needs morning checklist of pending work and evening reconciliation | LOW | Pre-canned buttons: Today, Yesterday, or direct input `DD/MM/YYYY`. Displays compact order summaries with status badges. |
| Telegram User ID Whitelist | Internal store tool holding PII and revenue data; unauthorized users must be blocked | LOW | Middleware check on `update.effective_user.id` against configured whitelist list. Non-whitelisted IDs receive silent drop or access denied message. |
| Order Detail Inspection Card | View customer details, line items, status, payment details in single readable layout | LOW | Formatted markdown card sent via Telegram message with inline action buttons below. |

### Differentiators (Competitive Advantage)

Features providing high leverage for low-tech elderly operator.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM Zero-shot Free-Text Order Ingestion | Replaces 8-step input forms. Merchant pastes raw, messy customer chat from Facebook/Zalo directly into Telegram. LLM extracts entities accurately | HIGH | 9router gateway (OpenAI-compatible) with JSON-schema/structured output. Prompts tuned for Vietnamese names, informal addresses, cassette titles, currency slang (`k`, `tr`, `nghìn`). |
| Interactive Order Preview & Confirmation Card | Eliminates fear of LLM hallucinations. Merchant inspects parsed fields before DB write | MEDIUM | Telegram message containing parsed draft + Inline Keyboard: `[Xác nhận]` and `[Huỷ / Sửa]`. Order saved only on callback tap. |
| 1-Tap Copy Inline Buttons | Eliminates tedious mobile text selection. One tap copies phone number, address, or tracking code for pasting into GHTK/GHN app | LOW | Telegram inline buttons using `CopyTextButton` (`copy_text` property) or `switch_inline_query` fallback. Essential for low-dexterity fingers. |
| Natural Language Free-Text Order Search | Elderly user cannot remember order IDs or syntax commands. Types queries like "đơn anh Tuấn ở Cần Thơ mua băng Tuấn Vũ" | HIGH | Two-step lookup: LLM extracts search filters (name, tape title, phone, date), SQL runs fuzzy match, bot presents preview card asking "Phải đơn này không?" before showing full detail. |
| 1-Tap Status Transition Buttons | Update state with zero typing. Current card displays next valid lifecycle actions | LOW | Inline buttons tailored to current state (e.g. at `Đang làm`, show `[Đã đóng gói]`; at `Shipper đã lấy`, show `[Đã giao]` and `[Bom]`). |

### Anti-Features (Commonly Requested, Often Problematic)

Features that add friction, tech overhead, or user confusion for elderly non-tech users.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Multi-step Conversational Wizards (Ask name -> ask phone -> ask items...) | Classic bot pattern | User forgets step, enters wrong field, cannot back up, gets trapped in state machine | Single raw text dump -> LLM parse -> preview card confirmation. |
| Barcode / Strict SKU Inventory Management | Traditional retail standard | Cassettes are often custom mixtapes, vintage recordings, or one-offs. Creating SKU for each cassette creates massive data entry barrier | Store raw line items as free-text string (`Băng Tuấn Vũ 1 x1, Băng Chế Linh x2`). |
| Direct Carrier API 2-way Sync (GHTK, GHN, ViettelPost) | Auto-fetches status and tracking codes | Requires carrier merchant accounts, OAuth/tokens, strict district/ward master ID mapping that fails on informal Vietnamese addresses, webhook servers | Merchant creates order in carrier mobile app (using 1-tap copied text), pastes tracking code back to bot. |
| Automated Payment Gateway / Webhook Polling | Instant payment verification | Third-party bank scraping/gateways (SePay, Casso) introduce external breakage risks and monthly fees. Elderly user already checks banking notification on phone | Mark order manually: `Chuyển khoản` vs `COD`. |
| Nested Slash Command Hierarchy (`/orders /list /search /settings /filter`) | Standard developer pattern | Elderly users cannot remember slash commands or discover nested menus on mobile virtual keyboard | Persistent Reply Keyboard with 3-4 primary buttons (`Tạo đơn`, `Đơn hôm nay`, `Tìm kiếm`) + Inline Buttons. |
| Web Dashboard / Telegram Mini App (TMA) | Rich UI charts and tables | Forces browser context switch, small desktop fonts on mobile, session token timeouts, complex touch interactions | 100% native Telegram chat stream messages with large fonts and emoji markers. |
| Customer Self-Service Order Interface | Reduces merchant work | Customers do not want to use a bot; they want human chat on Zalo/Facebook. Bot is purely merchant-facing backoffice tool | Merchant-only bot secured by User ID whitelist. |

## Feature Dependencies

```
[Telegram Whitelist Auth]
    └──requires──> None (Entry gate)

[Customer Data Layer]
    └──requires──> [SQLite DB Schema]

[Order Lifecycle State Machine]
    └──requires──> [Customer Data Layer]

[LLM Free-Text Ingestion]
    └──requires──> [9router / LLM Gateway]
    └──requires──> [Customer Data Layer]
    └──requires──> [Order Lifecycle State Machine]

[Interactive Preview Card]
    └──requires──> [LLM Free-Text Ingestion]

[1-Tap Copy Buttons]
    └──enhances──> [Interactive Preview Card]
    └──enhances──> [Order Detail Inspection Card]

[1-Tap Status Transitions]
    └──requires──> [Order Lifecycle State Machine]
    └──enhances──> [Order Detail Inspection Card]

[Natural Language Order Search]
    └──requires──> [9router / LLM Gateway]
    └──requires──> [Customer Data Layer]
    └──requires──> [Order Lifecycle State Machine]

[Date-filtered Order Listing]
    └──requires──> [Order Lifecycle State Machine]
```

### Dependency Notes

- **LLM Ingestion requires Customer Data Layer:** LLM extracts name/phone; ingestion engine must check if phone exists to update address/notes or create new customer record.
- **Interactive Preview Card requires LLM Ingestion:** Preview holds transient memory (or temp DB record) awaiting callback data before committing to main `orders` table.
- **1-Tap Copy Buttons enhance Inspection Card:** Placing `copy_text` inline buttons directly under customer phone and shipping address reduces friction when switching to shipping apps.
- **Natural Language Search requires 9router Gateway:** Non-exact queries must be transformed into SQL filters or ranked candidate IDs.

## MVP Definition

### Launch With (v1)

Minimum viable tool to run daily cassette shop operations without paper notebooks.

- [ ] Whitelist auth middleware — secure bot to shop owner's Telegram ID.
- [ ] SQLite storage for customers (multi-phone, multi-address) and orders.
- [ ] Order lifecycle state machine with 7 statuses (`Chờ làm` to `Đã giao / Bom / Huỷ`).
- [ ] LLM raw text parser (9router) converting Vietnamese order text to structured draft.
- [ ] Interactive order confirmation card with `[Xác nhận]` and `[Huỷ]` inline buttons.
- [ ] Order detail display with 1-tap copy buttons (phone, address, tracking code).
- [ ] Tracking code manual update button.
- [ ] Date filter listings (`Hôm nay`, `Hôm qua`).
- [ ] Basic status transition inline buttons.

### Add After Validation (v1.x)

Features to add once daily order flow is steady.

- [ ] Natural language free-text order search with confirmation prompt.
- [ ] Daily revenue and order count summary report (morning / evening digest).
- [ ] Customer order history view (lookup past tape purchases by phone number).
- [ ] Quick order edit button (update item list or COD amount without recreating order).

### Future Consideration (v2+)

Deferred until scale demands it.

- [ ] CSV/Excel export for accountant or tax reporting.
- [ ] Backup/restore database command via Telegram private file upload.
- [ ] Multi-staff role whitelisting (Owner vs Assistant).

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Telegram User ID Whitelist | HIGH | LOW | P1 |
| Customer Multi-Phone/Address DB | HIGH | MEDIUM | P1 |
| 7-Stage Order Lifecycle Engine | HIGH | LOW | P1 |
| LLM Raw Vietnamese Text Parser | HIGH | MEDIUM | P1 |
| Preview Card with Confirm/Cancel | HIGH | LOW | P1 |
| 1-Tap Copy Buttons (Phone/Address/Tracking) | HIGH | LOW | P1 |
| Manual Tracking Code Attachment | HIGH | LOW | P1 |
| Date Order Listings (Today/Yesterday) | HIGH | LOW | P1 |
| 1-Tap Status Advance Buttons | HIGH | LOW | P1 |
| NL Free-Text Search with Confirm | MEDIUM | MEDIUM | P2 |
| Quick Edit Order Attributes | MEDIUM | MEDIUM | P2 |
| Daily Revenue / Status Digest | MEDIUM | LOW | P2 |
| Customer Past Purchase Lookup | MEDIUM | MEDIUM | P2 |
| SQLite Backup via Telegram File | LOW | LOW | P3 |
| CSV Data Export | LOW | LOW | P3 |

**Priority key:**
- P1: Non-negotiable for v1 launch
- P2: Immediate fast-follow post-launch
- P3: Nice-to-have operational convenience

## Competitor Feature Analysis

| Feature | Sổ Bán Hàng / KiotViet Mobile | Standard Telegram E-Commerce Bot | Cassette Store Bot (Our Approach) |
|---------|-------------------------------|----------------------------------|------------------------------------|
| Order Ingestion | 6-10 screen taps, product selection, customer form | Structured command tree or web app cart | Single raw text paste parsed by LLM into draft card. Zero forms. |
| Customer Data | Mandatory unique phone, strict address fields | Username/Telegram ID based | Multi-phone, multi-address, informal text supported. |
| Product Catalog | Strict SKU, barcode, price, inventory levels | Pre-defined inline keyboard catalog | Free-text cassette titles. No inventory blockage. |
| Carrier Integration | Direct API sync with GHTK/GHN | None | Manual tracking code entry + 1-tap copy buttons for fast external app paste. |
| Search | Filter dropdowns, exact phone input | Keyword match | Natural language LLM search with "Did you mean?" confirmation. |
| UX for Elderly | Complex UI, small text, dense dashboards | Slash commands, chat forms | Large text, emojis, persistent reply keyboard, 1-tap inline buttons. |

## Sources

- Cassette Store Project Spec: `.planning/PROJECT.md`
- Telegram Bot API Documentation: InlineKeyboardMarkup, CopyTextButton (`copy_text`)
- Field research: Low-tech Vietnamese social-commerce workflows (Facebook/Zalo to Telegram order triage)

---
*Feature research for: Cassette Store Telegram Chatbot*
*Researched: 2026-10-24*
