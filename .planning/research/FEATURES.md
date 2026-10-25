# Feature Research

**Domain:** Telegram Retail Order Management Chatbot (Low-Tech Cassette Merchant)
**Researched:** 2026-10-25
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features required for basic operations in milestone v1.1. Missing any makes the workflow incomplete, fragile, or unsafe for elderly operators.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **3-Way Intent Routing (New Order vs Search vs Mutate)** | Free-text message must land on right subsystem; cannot mistakenly create duplicate order when user intended edit, or trigger read-only search when updating status. | MEDIUM | Fast regex verb filter (`đổi`, `sửa`, `cập nhật`, `gán`, `huỷ`) + active state check + LLM structured classification fallback (`intent: "NEW_ORDER" \| "SEARCH" \| "MUTATE"`). |
| **Order Identification & Ambiguity Disambiguation** | User refers to order loosely ("đổi đơn anh Tuấn", "sửa đơn 12"). Bot must pinpoint correct record without guessing when multiple records match. | MEDIUM | Reuses Phase 04 unaccent search and order lookup. If multiple orders match, renders 1-tap selection keyboard showing order ID, customer name, items, and date badge. |
| **Before ➡️ After Visual Diff Card** | Low-tech users fear destructive edits; must see exact old value vs proposed new value before applying changes to database. | MEDIUM | Formatted HTML card showing only mutated fields: `Trạng thái: ⏳ CHỜ LÀM ➡️ ✅ ĐÃ GIAO` or `COD: 350.000 đ ➡️ 300.000 đ`. Unchanged fields suppressed. |
| **Two-Phase Confirmation with 120s TTL** | Accidental taps or stale drafts left in chat must expire safely without corrupting DB. | LOW | In-memory pending mutation draft stored in `context.bot_data` with Unix timestamp TTL (120 seconds). Buttons: `[✅ Xác nhận sửa]` and `[❌ Huỷ giữ nguyên]`. |
| **Core Field Mutations (Status, Tracking, Notes, COD/Total, Phone/Address)** | Everyday shop adjustments: package packaged, tracking code assigned, customer changed phone/address, or discount given. | MEDIUM | Atomic SQLite transactions updating order table. Phone validated with 10-digit regex. Status checked against 8 database enum values. Recalculates `cod_amount = max(0, total_amount - deposit_amount)`. |
| **Role-Based Access Control (SUPER_ADMIN vs ADMIN)** | Store owner needs to delegate day-to-day order processing to staff/family without letting staff edit whitelist, view system logs, or change models. | LOW | SQLite `user_roles` table (`user_id`, `role`). Root Super Admin ID anchored in `.env` (`TELEGRAM_SUPER_ADMIN_ID`), immutable at runtime. Group -1 gate enforces RBAC. |
| **Telegram Whitelist Management via Inline Buttons** | Super Admin must add or revoke bot access on mobile directly in Telegram without SSH/terminal access. | MEDIUM | `/admin` submenu: List active users with role badges, 1-tap `[➕ Thêm Admin]`, 1-tap `[❌ Thu hồi quyền]`. Super Admin root ID protected against deletion. |
| **LLM Model Switching via Telegram Menu** | 9router gateway routes to multiple LLM models (e.g. Gemini, DeepSeek, Claude, GPT); admin needs 1-tap model switcher when one provider degrades. | LOW | Inline button list of configured models (`[⚡ gemini-2.5-flash (Hiện tại)]`, `[🧠 deepseek-chat]`). Updates runtime config instantly without server restart. |
| **Log Viewer (`/logs` with tail lines)** | Super Admin needs to diagnose runtime errors or check recent activities directly on phone without server terminal. | LOW | Protected command `/logs [n=20]`. Reads last N lines of application log file (in-memory ring buffer or `tail` read), wrapped in `<pre>` HTML blocks. |
| **Atomic SQLite Snapshot (`VACUUM INTO` + gzip)** | Backing up live SQLite while in WAL mode via raw OS copy corrupts database files; snapshot must be transactionally isolated. | MEDIUM | Standard Python stdlib `aiosqlite` executes `VACUUM INTO 'snapshot.db'`, compressed via stdlib `gzip` into `cassette_store_YYYYMMDD_HHMMSS.sqlite3.gz`. Non-blocking. |
| **Manual `/backup` Command Sending Document to Super Admin DM** | Store owner needs instant on-demand backup before updating bot or traveling. | LOW | Protected command `/backup` (Super Admin only). Generates gzip snapshot, sends directly as Telegram Document file to owner's private chat with size and order stats. |
| **Automated Daily Backup Job** | Unattended protection against host drive corruption or VPS termination. | LOW | PTB `JobQueue` scheduled daily at 02:00 AM UTC+7. Creates snapshot and silently dispatches `.sqlite3.gz` to Super Admin DM. Alerts on failure. |
| **Containerization (Multi-Stage Dockerfile & Docker Compose)** | Consistent deployment across Mac local dev, VPS, and cloud without Python version or SQLite C-extension mismatches. | MEDIUM | Multi-stage Dockerfile (build wheel dependencies, runtime python-slim non-root user), `docker-compose.yml` with named persistent volume mounted at `/data`. |
| **Kubernetes Deployment Manifests** | Cloud-native deployment for K3s/K8s environments with persistent storage and secret injection. | MEDIUM | `Deployment` (single-replica `Recreate` strategy to prevent multi-writer SQLite lock), `PersistentVolumeClaim` (ReadWriteOnce), `ConfigMap`, and `Secret`. |

---

### Differentiators (Competitive Advantage)

Features providing high leverage for low-tech elderly operators and zero-maintenance single-operator stores.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Elderly-Friendly High-Contrast Diff Card** | Removes fear of technology for elderly users by visually emphasizing changes with emojis, bold text, and strikethroughs. | LOW | Visual diff generator showing only changed fields in bold/italic with clear change arrows. Unchanged fields kept out of clutter. |
| **Ambiguity Fallback to 1-Tap Action Pill Buttons** | When user gives incomplete input (e.g., "sửa đơn 12" without specifying what to change), bot displays instant action buttons for all editable fields. | LOW | Dynamic inline keyboard: `[📦 Đổi trạng thái]`, `[🚚 Gán mã vận đơn]`, `[💰 Sửa tiền COD]`, `[📍 Sửa địa chỉ/SĐT]`, `[📝 Thêm ghi chú]`. Zero typing required. |
| **Status Target Suggestion Pills** | When user says "đổi trạng thái đơn chú Hùng" without stating target status, bot renders 8 status pills grouped ergonomically. | LOW | Inline grid of 8 lifecycle statuses with recognizable emojis (`⏳ Chờ làm`, `🔨 Đang làm`, `📦 Đã gói`, `🚚 Shipper lấy`, `✅ Đã giao`, `⚠️ Bom`, `❌ Huỷ`). |
| **Zero-Third-Party Telegram Document Backup** | Replaces external cloud storage/GitHub API with Telegram's unlimited, secure native document storage in Super Admin's private chat. | LOW | Uses existing bot token and Telegram Bot API `send_document`. Zero extra API keys, zero cloud storage bills, zero token rotation hassles. |
| **1-Tap Instant Rollback / Cancel** | If operator accidentally taps edit or changes mind, 1-tap `[❌ Huỷ giữ nguyên]` immediately clears draft and restores previous view. | LOW | Discards temporary draft in `context.bot_data`, confirms with "Đã huỷ thao tác, đơn hàng giữ nguyên". |
| **Immutable Root-of-Trust Super Admin** | Store owner can never be locked out of bot by junior admin mistakes or DB corruption. | LOW | Hardcoded check in RBAC gate: `user_id == settings.telegram_super_admin_id` always overrides DB and cannot be deleted via Telegram. |
| **Single-Replica SQLite Safe Deployment** | Prevents SQLite database corruption in Kubernetes by enforcing `strategy.type: Recreate` and volume mount safeguards. | LOW | K8s manifest configures single replica pod with volume locks; prevents split-brain SQLite WAL corruption. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features explicitly excluded to protect simplicity, safety, and project constraints.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| **Interactive Terminal Console Application** | Traditional sysadmin tool for local VPS maintenance. | Operator is elderly merchant on phone, not a Linux sysadmin; SSH/terminal introduces complexity, requires terminal emulator, and fragments control plane. | 100% native Telegram Admin Suite via `/admin` and `/logs` with inline buttons. Zero terminal interaction needed. |
| **GitHub Contents API Database Backup** | Free version-controlled cloud storage. | Requires generating and rotating GitHub Personal Access Tokens, manages git commit trees, breaks if token expires, exposes DB if repo misconfigured. | Native Telegram backup via `send_document` to Super Admin DM. Fast, free, encrypted in transit, zero third-party dependencies. |
| **Web-Based Admin Dashboard (FastAPI/React)** | Modern UI for analytics and management. | Requires opening public web ports, setting up HTTPS certificates (Let's Encrypt), managing cookie/JWT auth, and maintaining separate frontend codebase. | Native Telegram `/admin` interactive keyboard menu + existing 2x2 reply keyboard. |
| **Direct NL Mutation Without Confirmation** | Saves 1 tap ("just update it immediately"). | Fatal for elderly low-tech users; voice-to-text slips or ambiguous wording could silently wipe customer address, cancel order, or corrupt prices. | Strict 2-phase Before ➡️ After preview card with 120s TTL and prominent `[✅ Xác nhận]` / `[❌ Huỷ]` buttons. |
| **In-place Customer Master Overwrite on Order Mutation** | Editing address on an order updates the customer's permanent record automatically. | If customer orders a gift to a relative's address, changing that order's address ruins their permanent home address on future orders. | Mutate order snapshot only; offer optional button `[Lưu làm địa chỉ mặc định]` only if customer explicitly requests. |
| **Multi-Replica Kubernetes Scaling (Horizontal Pod Autoscaling)** | High availability pattern in standard K8s setups. | SQLite is single-node local file; running multiple pods on shared NFS/EFS causes catastrophic database corruption. | Single-replica `Recreate` deployment strategy with local persistent volume (ReadWriteOnce). Low throughput (<100 orders/day) needs no multi-pod scaling. |
| **Two-Way Carrier API Integration (GHTK, GHN, ViettelPost)** | Automatic shipping order creation and live webhook tracking. | High API maintenance, carrier contract credentials required, fragile webhook endpoints. | Operator creates order in external shipping app and pastes tracking code into Telegram bot (or uses 1-tap copy buttons). |

---

## Feature Dependencies

```
[Phase 01: Core SQLite & Whitelist]
    └──required_by──> [RBAC: Super Admin vs Admin]
                          ├──required_by──> [Telegram /admin Suite & Whitelist Menu]
                          ├──required_by──> [LLM Model Switcher]
                          └──required_by──> [Log Viewer (/logs)]

[Phase 01: SQLite WAL Engine]
    └──required_by──> [Atomic SQLite Snapshot (VACUUM INTO + gzip)]
                          ├──triggered_by──> [Scheduled Daily JobQueue]
                          └──triggered_by──> [Manual /backup Command (Super Admin DM)]

[Phase 02: LLM Gateway] & [Phase 04: Order Search / SQL]
    └──required_by──> [3-Way Intent Router (New vs Search vs Mutate)]
                          └──required_by──> [NL Order Mutation Extractor]
                                                └──requires──> [Before/After Diff Preview Card (120s TTL)]
                                                                   └──updates──> [Phase 03: Order Actions & Status]

[Project Codebase]
    └──required_by──> [Multi-stage Dockerfile]
                          ├──packaged_into──> [Docker Compose (Local/VPS)]
                          └──deployed_via──> [Kubernetes Manifests (PVC + Recreate Deployment)]
```

### Dependency Notes

- **NL Order Mutation requires Phase 02 LLM Gateway & Phase 04 Search:** Mutation first finds target order using unaccent search and order lookup, parses desired change using LLM extractor, and applies field updates via Phase 03 order lifecycle actions.
- **Telegram Admin Suite requires Phase 01 Whitelist & RBAC:** Admin commands (`/admin`, `/backup`, `/logs`) must verify user role before executing sensitive operations; without RBAC, whitelisted regular operators could trigger administrative mutations.
- **Telegram Backup requires SQLite WAL Engine:** Running raw copy while WAL is active corrupts database headers; `VACUUM INTO` creates clean checkpointed snapshot without locking active bot reads/writes.
- **Container Deployment requires Single-Replica SQLite Constraint:** Deployment manifests must enforce single pod replica (`strategy: Recreate`) and persistent volume mounts to prevent concurrent write collisions on SQLite.

---

## MVP Definition

### Launch With (Milestone v1.1 Target Deliverables)

Core features required to fulfill milestone v1.1.

- [x] **3-Way Intent Router:** Fast keyword filter + LLM classifier routing incoming free-text to New Order, Search, or Mutate.
- [x] **NL Order Mutation Engine:** Extract mutation target and field changes from natural Vietnamese chat.
- [x] **Before ➡️ After Visual Diff Card:** Clear visual diff card with 120s TTL and 1-tap `[✅ Xác nhận]` / `[❌ Huỷ]` buttons.
- [x] **Disambiguation & Ambiguity Fallbacks:** 1-tap selection keyboard for multiple matching orders; 1-tap action pill buttons when edit target field is unspecified.
- [x] **Core Field Mutation Execution:** Status update (8 states), tracking code update, notes update, COD/total price adjustment, and customer phone/address modification.
- [x] **RBAC Persistence & Gate:** SQLite `user_roles` table with `SUPER_ADMIN` and `ADMIN` tiers, anchored by immutable `TELEGRAM_SUPER_ADMIN_ID` in `.env`.
- [x] **Telegram Admin Suite:** Interactive `/admin` dashboard with 1-tap whitelist management, LLM model switcher, and system status metrics.
- [x] **Telegram Log Viewer:** Protected `/logs` command returning last N lines of bot logs in formatted `<pre>` text.
- [x] **Telegram Database Backup:** Atomic `VACUUM INTO` + gzip snapshot sent directly as `.sqlite3.gz` document to Super Admin DM via scheduled daily job and manual `/backup`.
- [x] **Multi-Stage Dockerfile & Docker Hub Guide:** Lightweight non-root container image with build instructions and push workflow.
- [x] **Docker Compose & Kubernetes Manifests:** `docker-compose.yml` with named volume; K8s `Deployment` (Recreate), `PersistentVolumeClaim`, `ConfigMap`, and `Secret`.

### Add After Validation (v1.1.x)

Features to add once core v1.1 features are stable in production.

- [ ] **Voice Note Order Mutation:** Transcribe Vietnamese voice notes via Whisper API into text and feed into 3-way intent router.
- [ ] **Automated Backup Rotation Notification:** Daily backup receipt summarizing daily order count, revenue, and database size delta.
- [ ] **Granular Audit Log for Admin Actions:** Store admin action history (who added which admin, who changed model) in dedicated SQLite table.

### Future Consideration (v2+)

Features deferred until multi-store or multi-tenant needs arise.

- [ ] **In-Chat Database Restore Wizard:** Allow Super Admin to reply to a backup `.sqlite3.gz` file with `/restore` to roll back database.
- [ ] **Multi-Shop Tenant Partitions:** Extend schema with `store_id` for multi-store support on single bot instance.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 3-Way Intent Routing (New vs Search vs Mutate) | HIGH | MEDIUM | **P1** |
| NL Order Mutation & Visual Diff Card (120s TTL) | HIGH | MEDIUM | **P1** |
| Ambiguity Fallback & Disambiguation Keyboards | HIGH | MEDIUM | **P1** |
| RBAC (Super Admin vs Admin) & Gate Enforcement | HIGH | LOW | **P1** |
| Telegram Admin Suite (`/admin` Whitelist & Model Switcher) | HIGH | MEDIUM | **P1** |
| Telegram Log Viewer (`/logs`) | MEDIUM | LOW | **P1** |
| SQLite Atomic Snapshot (`VACUUM INTO` + gzip) | HIGH | MEDIUM | **P1** |
| Scheduled Daily & Manual `/backup` to Super Admin DM | HIGH | LOW | **P1** |
| Multi-Stage Dockerfile & Docker Hub Push Guide | HIGH | MEDIUM | **P1** |
| Docker Compose & Kubernetes Manifests | HIGH | MEDIUM | **P1** |
| Voice Note Mutation via Whisper API | MEDIUM | HIGH | **P2** |
| Backup Rotation Summary Receipt | LOW | LOW | **P2** |
| In-Chat Database Restore Wizard | MEDIUM | HIGH | **P3** |
| Multi-Shop Tenant Partitions | LOW | HIGH | **P3** |

**Priority key:**
- **P1:** Must have for Milestone v1.1 delivery.
- **P2:** Nice-to-have enhancements post-stabilization.
- **P3:** Deferred to v2+ roadmap.

---

## Competitor Feature Analysis

| Feature | Standard E-commerce Bot | Custom Web Admin (SaaS) | Cassette Store Bot (v1.1 Milestone) |
|---------|-------------------------|--------------------------|-------------------------------------|
| **Order Editing** | Rigid multi-step button wizard or webview form | Web form with input fields and desktop data table | **Natural language chat** ("đổi đơn anh Tuấn sang đã giao") + 2-phase Before/After diff card with 1-tap confirm/cancel. |
| **Admin Management** | Text slash commands (`/setrole 123 admin`) or external web portal | Web portal with JWT auth, password resets, and user tables | **Native Telegram `/admin` interactive keyboard** with 1-tap whitelist management and model switcher. |
| **Database Backup** | Cloud provider snapshots (AWS RDS, GCP Cloud SQL) | S3 buckets via cron scripts with AWS access keys | **Direct Telegram Document delivery to Super Admin DM** via `VACUUM INTO` + gzip. Zero external cloud dependencies. |
| **Log Inspection** | CloudWatch, Datadog, or SSH terminal `journalctl` | Grafana / Kibana / Loggly web dashboards | **Direct Telegram `/logs` command** returning tail lines in `<pre>` HTML blocks. |
| **Deployment** | Complex multi-tier CI/CD pipelines to AWS ECS/EKS | PaaS deployments (Heroku, Render, Fly.io) | **Lightweight multi-stage Dockerfile**, `docker-compose.yml`, and clean Kubernetes manifests with persistent SQLite volume. |

---

## Sources

- [Telegram Bot API Documentation - sendDocument](https://core.telegram.org/bots/api#senddocument) — verified document sending limits (up to 50MB) and caption support for backup delivery.
- [SQLite Documentation - VACUUM INTO](https://www.sqlite.org/lang_vacuum.html#vacuuminto) — verified transactional atomic snapshot mechanism without blocking concurrent reads/writes in WAL mode.
- [Python Telegram Bot Documentation - JobQueue](https://docs.python-telegram-bot.org/en/stable/telegram.ext.jobqueue.html) — verified background job scheduling for daily automated backups.
- [Kubernetes Documentation - StatefulSet vs Deployment with PVC](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy) — verified `strategy: Recreate` for single-replica SQLite persistent volume attachments.
- [Project Documentation - Milestone v1.1 Scope](cassette-store-bot/.planning/PROJECT.md) — verified core target features and explicit out-of-scope boundaries (no console app, no GitHub backup).

---
*Feature research for: Telegram Retail Order Management Chatbot (Milestone v1.1)*
*Researched: 2026-10-25*
