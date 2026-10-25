# Feature Research: Milestone v1.1 NL Order Mutation, Console Admin, RBAC & GitHub Backup

**Domain:** Telegram Retail Order Management Chatbot (Low-Tech Cassette Merchant)
**Researched:** 2026-10-25
**Confidence:** HIGH

---

## Executive Overview & Milestone Scope

Milestone v1.1 expands the validated v1.0 system (which supports text-to-order extraction, 2x2 reply keyboards, 1-tap copy buttons, manual status buttons, and natural language search) with four core operational pillars:
1. **Natural Language Order Mutation (NL Mutation):** Free-text edits to existing orders with intent separation, partial info handling, and 2-phase visual diff confirmation.
2. **Interactive Console App:** Server-side terminal control menu for headless host maintenance, diagnostic checks, and direct whitelist administration.
3. **Multi-tier RBAC & Telegram Admin Suite:** Separation between `Super Admin` (full owner/system authority) and `Admin` (store operations/staff), paired with a secure `/admin` Telegram control card.
4. **Automated & Manual GitHub Database Backup:** Atomic SQLite WAL snapshotting via online backup APIs, gzip compression, and GitHub REST API integration with retention policies.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features required for basic operations in milestone v1.1. Missing any leaves the management workflow incomplete or unsafe.

| Feature | Why Expected | Complexity | Implementation Notes |
|---------|--------------|------------|----------------------|
| **NL Intent Disambiguation (Search vs Mutate vs Ingest)** | Operator types free-text like "đổi đơn anh Tuấn sang đã giao" or "sửa sđt đơn 12"; system must never accidentally create a new order or run a read-only search | MEDIUM | 3-tier router: (1) Active conversation state check, (2) Lexical verb matching ("đổi", "sửa", "chuyển", "cập nhật", "huỷ", "gán mã"), (3) LLM Intent Classifier with structured output. |
| **2-Phase Mutation Preview & Diff Confirmation** | Elderly operator must see exact "Before -> After" changes before committing destructive updates to database | MEDIUM | Formatted Telegram card with HTML strikethrough/arrow diff (`Trạng thái: ⏳ CHỜ LÀM ➡️ ✅ ĐÃ GIAO`). Inline buttons `[✅ Xác nhận sửa]` and `[❌ Huỷ giữ nguyên]`. 120s TTL draft in memory. |
| **Core Order Field Mutations** | Operator needs to adjust the most common order changes: status, tracking code, notes, COD/total price, recipient phone, and address | MEDIUM | Atomic SQLite update query per field or batch update. Phone validated with 10-digit regex. Status constrained to 8 OrderStatus enum values. |
| **Multi-Match Order Disambiguation** | If query references "đơn anh Tuấn" but multiple orders match, bot must not guess blindly | LOW | Renders compact choice list of matching orders with items and date badges. 1-tap selection button resumes mutation flow for that specific order ID. |
| **Terminal Interactive Console App** | System admin on VPS/server needs direct access without depending on active Telegram polling or bot credentials | MEDIUM | Terminal interactive menu (stdlib/rich/prompt loop): status overview, whitelist admin, instant backup trigger, and service diagnostics. |
| **Super Admin vs Admin Role Separation** | Store owner must delegate daily order processing to family/assistant without granting power to change bot permissions or erase admin rights | LOW | Database table `user_roles` (`user_id`, `role`, `created_at`). Super Admin ID anchored in `.env` config as immutable root of trust. |
| **Telegram `/admin` Command & Control Card** | Admins need mobile access to operational tools (revenue summary, trigger backup, bot health, user management for Super Admin) | MEDIUM | Protected command handler checking role >= ADMIN. Renders inline interactive dashboard with permission-gated buttons. |
| **Atomic SQLite WAL Snapshotting** | Backing up live SQLite while bot writes can cause corrupted database files if done via raw file copy | MEDIUM | Must use SQLite Online Backup API (`sqlite3.backup` or `VACUUM INTO`) to generate clean snapshot without blocking concurrent bot operations. |
| **Periodic & Manual GitHub Backup** | Protection against VPS disk failure, local machine loss, or accidental deletion | MEDIUM | Scheduled daily backup via PTB `JobQueue` / `asyncio` task + instant trigger via Telegram `/admin` and Terminal Console. |

---

### Differentiators (Competitive Advantage)

Features providing high leverage for low-tech elderly operators and single-operator store reliability.

| Feature | Value Proposition | Complexity | Implementation Notes |
|---------|-------------------|------------|----------------------|
| **Elderly-Friendly Visual "Before ➡️ After" Diff Card** | Elderly users get nervous about accidental data overwrites. Highlighting exact field changes with emoji markers removes fear of technology | LOW | Visual diff generator showing only changed fields in bold/italic with clear change arrows. Unchanged fields kept out of clutter. |
| **Ambiguity Fallback to 1-Tap Action Pill Buttons** | When user says ambiguous command like "sửa đơn 12" without specifying field, bot displays instant 1-tap buttons for all editable fields | LOW | Dynamic inline keyboard: `[📦 Đổi trạng thái]`, `[🚚 Gán mã vận đơn]`, `[💰 Sửa tiền COD]`, `[📍 Sửa địa chỉ]`, `[📝 Thêm ghi chú]`. Zero typing required. |
| **Status-Target Suggestion Buttons** | When user says "đổi trạng thái đơn chú Hùng" without stating new status, bot renders 8 status pills grouped ergonomically | LOW | Inline grid of 8 lifecycle statuses with recognizable emojis (`⏳ Đang làm`, `📦 Đã gói`, `🚚 Shipper lấy`, `✅ Đã giao`, `⚠️ Bom`, `❌ Huỷ`). |
| **Zero-Git-CLI GitHub REST Backup** | Backup runs via HTTPS GitHub Contents API using standard `httpx` (already installed), requiring no local Git binary, SSH keys, or Git repo setup on server | LOW | Encodes compressed `.db.gz` into base64 and commits directly to private GitHub backup repo via GitHub REST API `PUT /repos/{owner}/{repo}/contents/{path}`. |
| **Safe Admin Delegation with Protection Anchor** | Super Admin cannot accidentally remove themselves or be demoted by secondary admins, preventing bot lockout | LOW | Hardcoded immutable check in RBAC gate: `user_id == settings.telegram_super_admin_id` always overrides DB and cannot be deleted via Telegram. |
| **Backup Integrity Manifest & Telegram Receipt** | After backup, bot sends instant Telegram receipt with commit hash, file size, order count, and direct link | LOW | Generates `backup_manifest.json` alongside `.db.gz` with SHA-256 checksum, row counts, and timestamp; sends formatted card to admin chat. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that add friction, technical overhead, or user confusion for this domain.

| Anti-Feature | Why Requested | Why Problematic | Alternative / Better Approach |
|--------------|---------------|-----------------|-------------------------------|
| **Direct Mutation Without Confirmation** | Users want speed ("just change it, don't ask me twice") | Fatal for low-tech elderly users; speech-to-text or minor typos could corrupt price, customer phone, or mark order cancelled by mistake | Always require 2-phase preview card with prominent `[✅ Xác nhận]` and `[❌ Huỷ]`. |
| **Web-Based Admin Dashboard** | Standard SaaS practice for multi-user admin | Requires web server (FastAPI/Nginx), SSL certs, port forwarding, authentication cookies, mobile browser logins. Breaks core zero-maintenance promise | 100% native Telegram `/admin` menu + Terminal Console for server maintenance. |
| **Git CLI Subprocess Execution for Backups** | Typical developer instinct to run `git commit && git push` | Requires local git config, SSH deploy keys, handles merge conflicts, fails if working tree is dirty or network times out | Use direct GitHub REST API with personal access token via `httpx.AsyncClient`. Single atomic HTTP call. |
| **Complex Multi-Level Role Hierarchy (Owner, Manager, Staff, Viewer)** | Enterprise RBAC systems | Over-engineering for a 2-3 person family shop. Adds cognitive load and configuration bugs | Strictly 2 tiers: `SUPER_ADMIN` (owner/config/RBAC) and `ADMIN` (store operations/staff). |
| **Raw `.db` File Copy via OS File System** | Simplest backup script (`cp cassette_store.db backup.db`) | Corrupts data when SQLite is in WAL mode and active writes are happening | Use SQLite Online Backup API (`VACUUM INTO` or `conn.backup()`) for transactional consistency. |
| **Interactive Terminal TUI Framework (e.g. Textual/Curses)** | Looks modern and flashy in terminal | High terminal emulator incompatibility over SSH/tmux/Windows Terminal, complex mouse/cursor captures, extra heavy dependencies | Clean ANSI menu loop with standard `input()` prompts. Rock-solid on any server. |
| **In-place Customer Profile Overwrite on Order Mutation** | Editing an order's address/phone automatically changes the customer master profile | If a customer orders a gift delivered to a friend's address, changing the order address must NOT ruin customer's home address | Mutate order snapshot by default; offer optional prompt `[Cập nhật vào hồ sơ khách?]` only when explicitly desired. |

---

## Detailed Specifications for New Features

### 1. Natural Language Order Mutation

#### 1.1 Intent Routing & Disambiguation
Incoming text routing pipeline:
1. **Active State Check:**
   - If user is in `search_state` -> route to search.
   - If user is in `action_state` (e.g. entering tracking code or note) -> route to action handler.
   - If user has pending `mutation_draft` -> wait for button confirmation.
2. **Fast Regex / Lexical Filter:**
   - Mutation action verbs: `đổi`, `sửa`, `chuyển`, `cập nhật`, `gán`, `set`, `báo`, `thay`, `huỷ`, `giảm`.
   - Combined with order target tokens: `đơn`, `mã`, `vận đơn`, `trạng thái`, `tiền`, `cod`, `sđt`, `địa chỉ`, `ghi chú`.
   - If match found without search-only prefix (`tìm`, `tra cứu`) -> route to NL Mutation Extractor.
3. **LLM Mutation Extraction Schema:**
   - Output structured Pydantic model:
     - `order_identifier`: Order ID, customer name, phone, or relative time reference.
     - `mutation_field`: Enum (`STATUS`, `TRACKING_CODE`, `NOTES`, `AMOUNT`, `PHONE`, `ADDRESS`, `CANCEL`, `AMBIGUOUS`).
     - `new_value`: Extracted target value (e.g. new phone string, integer amount, tracking code string, or target status).
     - `confidence`: Extraction confidence score.

#### 1.2 Handling Partial & Ambiguous Information
- **Case A: Order Reference Matches Multiple Records:**
  - Query: "Đổi đơn anh Tuấn sang đã giao" (Database returns 2+ orders for "anh Tuấn").
  - Response: Display disambiguation card:
    ```
    🔍 Bác muốn đổi đơn nào của anh Tuấn ạ?
    [ Đơn #102: 2 cuốn Tuấn Vũ (350k) - Chờ làm ]
    [ Đơn #108: 1 cuốn Chế Linh (180k) - Shipper lấy ]
    [ ❌ Huỷ thao tác ]
    ```
  - User taps button -> target order is bound, mutation card is displayed immediately.
- **Case B: Ambiguous Target Field:**
  - Query: "Sửa đơn 45" or "Chỉnh đơn anh Tuấn" (Order identified, but no field specified).
  - Response: Display order summary card with 1-tap action buttons:
    ```
    📦 ĐƠN HÀNG #45 - Nguyễn Văn Tuấn
    Bác muốn chỉnh sửa thông tin gì ạ?
    [ 🔄 Đổi trạng thái ]   [ 🚚 Gán mã vận đơn ]
    [ 💰 Sửa tiền COD ]     [ 📍 Sửa địa chỉ/SĐT ]
    [ 📝 Sửa ghi chú ]       [ ❌ Huỷ đơn này ]
    ```
- **Case C: Ambiguous Status Target:**
  - Query: "Đổi trạng thái đơn 45" (Target status not mentioned).
  - Response: Display status selection keyboard (8 buttons with clear Vietnamese labels and emojis).

#### 1.3 Supported Mutation Types
1. **Status Mutation:** Updates `orders.status` to one of 8 enum values (`CHO_LAM`, `DANG_LAM`, `DA_DONG_GOI`, `DA_TAO_DON`, `SHIPPER_DA_LAY`, `DA_GIAO`, `BOM_HANG`, `HUY_DON`).
2. **Tracking Code Mutation:** Updates `orders.tracking_code`. If user says "xoá mã vận đơn", clears the field.
3. **Notes Mutation:** Appends or replaces order notes (`orders.notes` or special note tracking).
4. **Amount & COD Mutation:** Updates `total_amount` and `cod_amount`. If order has a `deposit_amount`, bot automatically recalculates: `cod_amount = max(0, total_amount - deposit_amount)`.
5. **Customer Details Mutation:** Updates snapshot `customer_phone` (with 10-digit validation) or `shipping_address` on the order record.

#### 1.4 Two-Phase Preview & Confirmation Card
- Format:
  ```html
  📝 <b>XÁC NHẬN CHỈNH SỬA ĐƠN HÀNG #102</b>
  👤 <b>Khách hàng:</b> Nguyễn Văn Tuấn (<code>0912345678</code>)
  ────────────────────
  🔄 <b>THAY ĐỔI DỰ KIẾN:</b>
  • <b>Trạng thái:</b> ⏳ CHỜ LÀM  ➡️  ✅ <b>ĐÃ GIAO</b>
  • <b>Tiền COD thu:</b> 450.000 đ  ➡️  <b>400.000 đ</b> <i>(giảm 50.000 đ)</i>
  ────────────────────
  Bác kiểm tra kỹ thông tin rồi bấm nút bên dưới nhé:
  ```
- Inline buttons:
  - `[ ✅ Xác nhận lưu ]` (callback: `mut:cf:<draft_id>`)
  - `[ ❌ Huỷ bỏ / Giữ nguyên ]` (callback: `mut:ca:<draft_id>`)
- Behavior on confirm: Executes database update within transaction, updates `updated_at`, replies with success notification and refreshed order inspection card with 1-tap copy buttons.

---

### 2. Interactive Console App (Server Terminal)

#### 2.1 Purpose & Execution
- Standalone CLI application executed on the host: `python -m src.console` or entry script `python console.py`.
- Operates independently or alongside the running Telegram bot by directly accessing `cassette_store.db` (safe under SQLite WAL mode).

#### 2.2 Menu Structure & Commands
```
==================================================
  CASSETTE STORE BOT - SERVER MANAGEMENT CONSOLE
==================================================
[1] 📊 Tình trạng hệ thống & Cơ sở dữ liệu (Status)
[2] 👥 Quản lý Whitelist & Phân quyền (RBAC)
[3] 📦 Tra cứu nhanh đơn hàng gần nhất (Order Lookup)
[4] 💾 Sao lưu cơ sở dữ liệu lên GitHub (Backup Now)
[5] 🩺 Kiểm tra kết nối dịch vụ (Diagnostics)
[0] 🚪 Thoát console
==================================================
Chọn chức năng (0-5): 
```

- **[1] Status:** Displays bot process status, SQLite database file size, WAL size, total customers count, total orders count, last backup timestamp, and system uptime.
- **[2] Whitelist & RBAC Management:**
  - Submenu: (a) Xem danh sách người dùng & vai trò, (b) Thêm Super Admin, (c) Thêm Admin, (d) Xoá quyền / Thu hồi quyền, (e) Quay lại.
  - Validates Telegram numeric IDs, confirms before writing to database.
- **[3] Order Lookup:** Lists the 10 most recent orders with ID, date, customer name, phone, total amount, and status. Option to view raw order JSON.
- **[4] Backup Now:** Triggers immediate SQLite online snapshot, compresses with gzip, pushes to configured GitHub repo via REST API, and displays commit SHA and elapsed time.
- **[5] Diagnostics:** Runs 3 automated ping checks:
  1. 9router LLM Gateway (sends minimal probe request, measures latency).
  2. Telegram Bot API (`getMe` call verifying token and bot username).
  3. GitHub API (verifies PAT token validity and repo write permissions).

---

### 3. Multi-Tier RBAC & Telegram Admin Suite

#### 3.1 Permission Matrix

| Operation | Super Admin | Admin | Non-Whitelisted |
|-----------|:-----------:|:-----:|:---------------:|
| Free-text order ingestion | ✅ | ✅ | ❌ (Rejected at Gate) |
| Order search & inspection | ✅ | ✅ | ❌ |
| Order status / tracking updates | ✅ | ✅ | ❌ |
| NL order mutation (diff & confirm) | ✅ | ✅ | ❌ |
| View daily sales & order summary | ✅ | ✅ | ❌ |
| Trigger manual GitHub backup | ✅ | ✅ | ❌ |
| View system health & diagnostics | ✅ | ✅ | ❌ |
| Access Telegram `/admin` menu | ✅ | ✅ | ❌ |
| Promote / Demote other Admins | ✅ | ❌ (Forbidden) | ❌ |
| Modify bot settings / API keys | ✅ (Console only) | ❌ | ❌ |
| Revoke Super Admin permissions | ❌ (Root of trust protected) | ❌ | ❌ |

#### 3.2 Telegram `/admin` Dashboard Menu
- Triggered by `/admin` command.
- If user role < ADMIN: politely reject with "⛔ Bạn không có quyền truy cập menu quản trị."
- If user role == ADMIN or SUPER_ADMIN, send interactive card:
  ```html
  ⚙️ <b>TRUNG TÂM QUẢN TRỊ BOT</b>
  👤 <b>Vai trò của bạn:</b> [Super Admin / Admin]
  ────────────────────
  Bác/bạn chọn công cụ cần thao tác:
  ```
  Inline buttons:
  - `[ 📊 Báo cáo doanh thu ]` -> Quick summary of today, this week, this month.
  - `[ 💾 Sao lưu dữ liệu ]` -> Immediate trigger with live status notification.
  - `[ 🩺 Tình trạng bot ]` -> DB size, memory usage, LLM response latency.
  - `[ 👥 Quản lý người dùng ]` *(Only rendered for Super Admin)* -> Submenu to list and add/remove Admins.
  - `[ 🔙 Đóng bảng quản trị ]` -> Cleans up menu message.

#### 3.3 Safe Admin Delegation Flow
- **Adding an Admin:**
  1. Super Admin clicks `[ 👥 Quản lý người dùng ]` -> `[ ➕ Thêm Admin ]`.
  2. Bot enters conversation state: "Vui lòng nhập Telegram User ID của người bạn muốn phân quyền Admin (hoặc chuyển tiếp tin nhắn của người đó)."
  3. Super Admin enters numeric ID.
  4. Bot checks: ID must be positive integer; cannot already be an Admin.
  5. Confirmation step: "Xác nhận cấp quyền ADMIN cho User ID `123456789`?" `[ ✅ Đồng ý ]` `[ ❌ Huỷ ]`.
  6. On confirm: Inserts/updates `user_roles` table, refreshes runtime whitelist in memory, sends notification.
- **Protection Rules:**
  - The ID configured in `TELEGRAM_SUPER_ADMIN_ID` in `.env` is immutable; code forbids demoting or deleting this ID through Telegram or console.
  - Every delegation event logs: `timestamp`, `operator_id`, `target_id`, `new_role`.

---

### 4. Automated & Manual GitHub Database Backup

#### 4.1 Backup Architecture & Safety
- **Problem:** Copying `cassette_store.db` directly while SQLite is running in WAL mode risks corrupted headers or missing transactions stored in `-wal` and `-shm` files.
- **Solution:**
  1. Use SQLite Online Backup API:
     - Method: `VACUUM INTO 'temp_backup.db'` (native SQLite 3.27+) or `sqlite3.Connection.backup()`.
     - Creates a single, complete, transactionally consistent `.db` file containing all checkpointed data.
  2. In-memory Gzip Compression:
     - Compresses `temp_backup.db` into `temp_backup.db.gz`.
     - Typical compression ratio: 75% to 85% size reduction (a 5MB DB compresses to ~800KB).
  3. GitHub Upload via REST API:
     - Target endpoint: `PUT https://api.github.com/repos/{owner}/{repo}/contents/backups/{year_month}/{filename}`.
     - Authentication: GitHub Personal Access Token (Fine-grained or classic with `repo` scope) stored in `Settings.github_backup_token`.
     - Payload: Base64-encoded gzip content + descriptive commit message.
     - Cleans up temporary local snapshot files immediately.

#### 4.2 Backup Scheduling & Triggers
- **Automatic Scheduled Backup:**
  - Runs once daily at off-peak hours (e.g. 02:00 AM UTC+7) using PTB `JobQueue` (or background `asyncio` task loop).
  - Silent on success; sends high-priority Telegram alert to Super Admin only if backup fails.
- **Manual Trigger:**
  - Via Telegram `/admin` -> `[ 💾 Sao lưu dữ liệu ]`: Sends working message "⏳ Đang tạo bản sao lưu...", uploads, and edits message into confirmation card with commit hash, file size, and timestamp.
  - Via Server Terminal Console -> Option [4]: Runs synchronous CLI progress bar and prints commit URL.

#### 4.3 Backup Metadata & Retention Policy
- **Metadata Structure:**
  - File naming: `cassette_store_YYYYMMDD_HHMMSS.db.gz`
  - Accompanying commit message and GitHub file metadata:
    ```json
    {
      "timestamp": "2026-10-25T02:00:00+07:00",
      "db_version": "v1.1",
      "total_orders": 450,
      "total_customers": 320,
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "size_bytes_compressed": 412500,
      "trigger": "SCHEDULED_DAILY",
      "operator_id": null
    }
    ```
- **Retention & Pruning Policy:**
  - Daily backups: Retained for **30 days**.
  - Weekly backups (Sunday runs): Retained for **12 weeks**.
  - Monthly backups (1st of month): Retained for **12 months**.
  - Automated pruning task: Runs once a week, lists files in the backup directory via GitHub API, and deletes daily files older than 30 days that are not weekly/monthly checkpoints.

---

## Feature Dependencies

```
[Phase 01: Core SQLite & Whitelist] 
    └──required_by──> [RBAC: Super Admin vs Admin]
                          └──required_by──> [Telegram /admin Menu]
                          └──required_by──> [Console App Whitelist Management]

[Phase 01: SQLite WAL Engine]
    └──required_by──> [SQLite Online Backup API (VACUUM INTO)]
                          └──required_by──> [GitHub REST Backup Engine]
                                                ├──triggered_by──> [JobQueue Daily Scheduler]
                                                ├──triggered_by──> [Telegram /admin Button]
                                                └──triggered_by──> [Console App Menu [4]]

[Phase 02: 9router Extractor] & [Phase 04: Order Search / SQL]
    └──required_by──> [NL Intent Classifier (Search vs Mutate vs Ingest)]
                          └──required_by──> [NL Order Mutation Engine]
                                                └──requires──> [2-Phase Diff Preview Card]
                                                                   └──updates──> [Phase 03: Order Actions & Status]
```

### Dependency Notes

- **NL Order Mutation requires Phase 02 Extractor & Phase 04 Search:** Mutation first finds the target order using Phase 04 search/unaccent logic, parses the desired change using Phase 02 LLM gateway, and applies status/tracking updates via Phase 03 actions.
- **Telegram /admin Menu requires RBAC:** Admin commands must query the role table before executing sensitive operations; without RBAC, whitelisted non-admins would have access to destructive tools.
- **GitHub Backup requires SQLite Online Backup API:** Backing up directly from raw filesystem while WAL is open causes corruption; `VACUUM INTO` or `sqlite3.backup` is a strict prerequisite.
- **Console App operates independently of Telegram Polling:** Built directly on top of database connection and settings, ensuring server management remains available even if Telegram polling crashes or bot token is revoked.

---

## MVP Definition (Milestone v1.1)

### Launch With (v1.1 Target Deliverables)

- [ ] **NL Order Mutation Engine:** Parse mutation intents from natural Vietnamese chat, identify target order, and generate visual diff.
- [ ] **2-Phase Diff Confirmation Card:** Elderly-friendly HTML preview card showing Before ➡️ After values with 1-tap `[Xác nhận]` and `[Huỷ]` buttons.
- [ ] **Multi-Match & Ambiguity Fallbacks:** Disambiguation keyboard for multiple matching orders and 1-tap action buttons when mutation target is unstated.
- [ ] **Core Field Mutations:** Status change (8 statuses), tracking code update, note update, COD/total price modification, and phone/address update.
- [ ] **RBAC Persistence & Gate:** SQLite `user_roles` table with `SUPER_ADMIN` and `ADMIN` tiers; immutable Super Admin ID from `.env`.
- [ ] **Telegram `/admin` Control Suite:** Mobile dashboard for admins with stats, health check, backup trigger, and user delegation for Super Admin.
- [ ] **Server Interactive Console App:** Terminal menu on server host for DB status, whitelist admin, instant backup, and diagnostics.
- [ ] **GitHub REST Database Backup Engine:** Transaction-safe SQLite online snapshot, gzip compression, and direct GitHub API upload.
- [ ] **Backup Triggers & Scheduling:** Automated daily backup via PTB `JobQueue` + manual trigger in Telegram and Console.

### Add After Validation (v1.1.x)

- [ ] **Backup Automated Pruning:** Scheduled GitHub API job to prune daily backups older than 30 days.
- [ ] **Voice Note Mutation:** Support Telegram voice messages for order mutation (transcribe via Whisper -> NL mutation pipeline).
- [ ] **Audit Trail Viewer in Console:** Terminal viewer for order mutation history and admin role change logs.

### Future Consideration (v2+)

- [ ] **Database Restore CLI:** Command-line tool to download, verify SHA-256, and restore database directly from GitHub backup repo.
- [ ] **Multi-Shop Tenant Support:** Extend RBAC to support multiple store partitions in a single bot instance.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|:----------:|:-------------------:|:--------:|
| NL Order Mutation & Diff Card | HIGH | MEDIUM | **P1** |
| Ambiguity & Disambiguation Handling | HIGH | MEDIUM | **P1** |
| RBAC (Super Admin vs Admin) & Gate | HIGH | LOW | **P1** |
| Telegram `/admin` Management Menu | HIGH | MEDIUM | **P1** |
| SQLite WAL Online Snapshot & GitHub Backup | HIGH | MEDIUM | **P1** |
| Backup Triggers (Scheduled + Manual) | HIGH | LOW | **P1** |
| Server Interactive Console App | MEDIUM | MEDIUM | **P1** |
| Automated Backup Pruning (30-day retention) | MEDIUM | LOW | **P2** |
| Voice Note Mutation via Whisper | MEDIUM | HIGH | **P3** |
| Automated Database Restore Wizard | LOW | HIGH | **P3** |

**Priority key:**
- **P1:** Non-negotiable core for Milestone v1.1.
- **P2:** Enhancements to ship immediately following core stabilization.
- **P3:** Deferred to future milestone.

---

## Competitor & Alternative Architecture Analysis

| Feature | Standard E-commerce Bot | Custom Web Admin (SaaS) | Cassette Store Bot (v1.1 Approach) |
|---------|-------------------------|--------------------------|-----------------------------------|
| **Order Editing** | Rigid multi-step button wizard or webview form | Web form with input validation and desktop table view | **Natural Language chat message** ("đổi đơn anh Tuấn sang đã giao") + 2-phase Before/After diff card with 1-tap confirmation. |
| **Admin Interface** | Long slash command list (`/setstatus 102 DA_GIAO`) | Responsive web dashboard with login credentials | **Native Telegram `/admin` interactive card** with large touch buttons + terminal console for server administration. |
| **Access Control** | Single API token or public bot with customer accounts | Role-based permissions with JWT/OAuth2 cookies | **Telegram User ID whitelist + 2-tier RBAC (`SUPER_ADMIN` vs `ADMIN`)** anchored to immutable server config. |
| **Data Backup** | Cloud SQL managed backups (AWS RDS / GCP Cloud SQL) | Cron job running `mysqldump` or `pg_dump` to S3 | **Atomic SQLite `VACUUM INTO` + Gzip + GitHub REST API**, requiring zero external cloud subscriptions or git CLI configuration. |

---

## Sources

- [Python-Telegram-Bot Documentation (JobQueue & Handlers)](https://docs.python-telegram-bot.org/) — verified async scheduled job patterns and callback query mechanics.
- [SQLite Official Documentation - Online Backup API & VACUUM INTO](https://www.sqlite.org/backup.html) — verified transactional safety of `VACUUM INTO` under WAL mode.
- [GitHub REST API Documentation - Create or Update File Contents](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents) — verified payload limits (up to 100MB) and base64 REST commit schema.
- [Project Architecture & Milestones](.planning/PROJECT.md) — validated v1.0 foundation constraints and v1.1 milestone objectives.

---
*Feature research for: Cassette Store Telegram Chatbot (Milestone v1.1)*  
*Researched: 2026-10-25*
