# Project Research Summary

**Project:** Cassette Store Telegram Chatbot (Milestone v1.1)
**Domain:** Telegram Retail Order Management Chatbot (Low-Tech Cassette Merchant)
**Researched:** 2026-10-25
**Confidence:** HIGH

## Executive Summary

Milestone v1.1 upgrades the Cassette Store Telegram Chatbot from a text-ingestion prototype into an autonomous, phone-administered, and containerized retail management system. The core product serves an elderly, low-tech Vietnamese cassette merchant who operates entirely via Telegram on mobile. The system replaces server-side SSH, terminal commands, and complex web dashboards with native Telegram interfaces: 1-tap inline keyboards, conversational natural language order edits, mobile admin controls, and direct database backup delivery.

The recommended architectural approach builds strictly on the validated v1.0 foundation (python-telegram-bot~=22.8, aiosqlite~=0.22.1, openai~=3.37.0, pydantic~=2.14.1). Natural language order mutation implements a deterministic 3-way intent router (heuristic keyword cascade + structured LLM classification) paired with a mandatory human-in-the-loop Before ➡️ After visual diff preview card (120-second TTL). Administration uses dynamic two-tier RBAC (SUPER_ADMIN vs ADMIN) anchored by an immutable root ID in .env. Automated backups use SQLite native atomic VACUUM INTO command and standard library gzip to stream compressed .sqlite3.gz archives directly into the Super Admin private Telegram chat, eliminating third-party cloud storage or GitHub API dependencies.

The critical risks in this milestone center on data integrity and concurrency: multi-pod writes corrupting single-file SQLite databases in Kubernetes, live file copy corrupting active WAL transactions, and natural language speech-to-text slips executing destructive blind updates. These are mitigated by enforcing Kubernetes strategy.type: Recreate with single-replica local block storage (ReadWriteOnce), non-blocking VACUUM INTO point-in-time snapshots, optimistic timestamp locking on order updates, and non-root multi-stage Docker containers with explicit Vietnam timezone (Asia/Ho_Chi_Minh) configuration.

## Key Findings

### Recommended Stack

Milestone v1.1 retains the core v1.0 stack and adds exactly one new Python dependency (python-telegram-bot[job-queue]), leveraging Python standard library modules and container manifests for all remaining capabilities. See .planning/research/STACK.md for full specifications.

**Core technologies:**
- python-telegram-bot[job-queue]~=22.8: Bundles APScheduler~=3.10.4 for automated daily database backups at 02:00 AM VN time natively inside the bot polling lifecycle.
- SQLite3 VACUUM INTO (Stdlib): Atomic, point-in-time database snapshot while WAL mode is active without locking concurrent readers or writers; zero external dependencies.
- gzip & tempfile (Stdlib): In-memory and streaming compression reducing SQLite databases by 75–85% prior to Telegram document upload.
- Docker Multi-Stage Build (python:3.12-slim): Non-root user (appuser UID 10001) container packaging with standard glibc for Pydantic Rust wheels and /app/data volume permissions.
- Kubernetes Manifests (RWO + Recreate): Single-replica deployment strategy preventing dual-pod SQLite write-lock corruption and Telegram polling conflict errors.
- logging.Handler + collections.deque (Stdlib): Fixed-size in-memory ring buffer (1000 lines) powering on-demand /logs inspection in Telegram with zero log infrastructure overhead.

### Expected Features

Milestone v1.1 delivers high-leverage operational features tailored for low-tech elderly merchants while rejecting complex sysadmin anti-features. See .planning/research/FEATURES.md for detailed landscape.

**Must have (table stakes):**
- 3-Way Intent Routing: Classifies free-text messages into New Order, Search, or Mutate via fast regex verb filter + LLM structured fallback.
- Before ➡️ After Visual Diff Card: Destructive mutations previewed with high-contrast old vs new values, 120s TTL, and 1-tap confirm/cancel buttons.
- Core Field Mutations: Status update (8 states), tracking code, notes, COD/total recalculation, and customer phone/address updates with optimistic locking.
- Two-Tier RBAC & Gate: SQLite admin_users table with SUPER_ADMIN and ADMIN roles, anchored by immutable TELEGRAM_SUPER_ADMIN_ID in .env.
- Telegram Admin Suite: Mobile dashboard (/admin) for whitelist management, 1-tap 9router LLM model switching, and system metrics.
- In-App Log Viewer: Protected /logs command returning recent log lines wrapped in HTML <pre> tags.
- Atomic Telegram Backup: Non-blocking VACUUM INTO + gzip snapshot sent directly as .sqlite3.gz to Super Admin DM via scheduled daily job and manual /backup.
- Production Containerization: Multi-stage Dockerfile, Docker Compose with named volume, and Kubernetes manifests (PVC + Recreate Deployment).

**Should have (differentiators):**
- Elderly-Friendly High-Contrast Diff Card: Changes highlighted with emojis, strikethroughs, and bold text; unchanged fields suppressed.
- Ambiguity Fallback Action Pills: Incomplete edit requests prompt 1-tap buttons ([📦 Đổi trạng thái], [🚚 Gán mã vận đơn], [💰 Sửa COD], etc.).
- Multi-Match Order Disambiguation Picker: Matching multiple orders renders 1-tap selection keyboard showing ID, name, items, and status badge.
- Zero-Third-Party Telegram Document Delivery: Unlimited, free, encrypted offsite backups delivered to owner phone without AWS S3 or GitHub PATs.
- Self-Healing Root Super Admin: Root admin is immutable in code and automatically restored in the database upon startup.

**Defer (v2+ / Anti-Features):**
- Terminal Console CLI (prompt_toolkit): Excluded; merchant operates 100% on mobile Telegram.
- GitHub Contents API Backup: Excluded; token rotation and repo bloat avoided via Telegram native document delivery.
- Web-Based Admin Dashboard (FastAPI/React): Excluded; eliminates port exposure, SSL certs, and web auth maintenance.
- Direct NL Mutation Without Confirmation: Excluded; fatal for low-tech elderly users vulnerable to voice-to-text noise.
- Multi-Replica Kubernetes Scaling: Excluded; SQLite is single-node, single-writer.

### Architecture Approach

The architecture adopts a 4-layer modular structure integrating Telegram Bot handlers, core application domain services, SQLite persistence, and container runtime boundaries. Free-text messages pass through a Group -1 security gate checking an in-memory RBAC cache before reaching the 3-Way Intent Router. NL mutations generate temporary in-memory drafts that require 1-tap Telegram callback confirmation before executing parameterized atomic SQL updates. See .planning/research/ARCHITECTURE.md for component diagrams and data flows.

**Major components:**
1. 3-Way Intent Router (src/services/router.py): 3-tier cascade (active conversation state -> regex prefix heuristic -> LLM structured classification) preventing misrouted orders or false mutations.
2. NL Order Mutation Service (src/services/order_mutation.py): Resolves candidate orders, extracts mutation deltas via 9router LLM, formats visual diff preview cards, and enforces optimistic concurrency locks on database writes.
3. RBAC & Admin Suite (src/bot/rbac.py & src/bot/handlers/admin.py): @require_role decorator, dynamic admin whitelist management, runtime LLM model switching, and ring buffer log tailing.
4. Telegram Backup Engine (src/services/backup.py): Standalone snapshot service running VACUUM INTO + gzip compression, scheduled via PTB JobQueue at 02:00 AM VN time and triggered manually via /backup.
5. Container & Process Lifecycle (Dockerfile, k8s/, main.py): Single-replica Recreate deployment, /app/data directory mount, non-root user execution, and SIGTERM trap ensuring PRAGMA wal_checkpoint(TRUNCATE).

### Critical Pitfalls

See .planning/research/PITFALLS.md for root-cause analyses and recovery strategies.

1. **Multi-Replica & RollingUpdate SQLite Corruption:** Standard K8s RollingUpdate spawns overlapping pods attaching to the same SQLite file, deadlocking writes and corrupting database headers.
   *Prevention:* Enforce replicas: 1 and strategy.type: Recreate in Kubernetes; use local block storage with ReadWriteOnce (RWO).
2. **Live File Copy Corruption & 50MB Backup Ceiling:** Copying active WAL files produces torn pages; uncompressed databases eventually exceed Telegram 50MB upload limit.
   *Prevention:* Mandatory VACUUM INTO atomic snapshot; stdlib gzip compression (>75% size reduction); proactive 48MB size guard before bot.send_document.
3. **Destructive Blind Updates & Intent Collisions:** LLMs misinterpret queries or voice-to-text typos, overwriting customer addresses or zeroing COD without operator review.
   *Prevention:* Deterministic 3-way intent router; mandatory 2-phase Before ➡️ After visual diff preview card with 120s TTL; multi-match disambiguation keyboards.
4. **Stale Diff Race Conditions in Multi-Operator Teams:** Operator A confirms a stale mutation after Operator B already updated or cancelled the order.
   *Prevention:* Optimistic concurrency check comparing order.updated_at on update; immediate inline keyboard button stripping on first tap.
5. **RBAC Privilege Escalation & Admin Lockout:** Replaying callback query data bypasses command-level role gates; clearing DB locks owner out.
   *Prevention:* Centralized @require_role decorating both command and callback handlers; immutable root TELEGRAM_SUPER_ADMIN_ID in .env with startup self-healing.
6. **Container Root Execution, UTC Drift & Unhandled SIGTERM:** Containers running as root cause host permission conflicts; UTC default shifts order dates by 7 hours; unhandled SIGTERM causes abrupt SIGKILL and uncheckpointed WAL state.
   *Prevention:* Non-root appuser (UID 10001); install tzdata and enforce TZ=Asia/Ho_Chi_Minh; exec form CMD ["python", "-m", "src.main"] with graceful WAL checkpoint shutdown trap.

---

## Implications for Roadmap

Based on research dependencies and architectural layering, Milestone v1.1 maps cleanly into 4 sequential phases:

### Phase 1: Foundation, Dynamic RBAC & Telegram Admin Suite
**Rationale:** Administration and access control must be established first. Dynamic RBAC (admin_users table and in-memory cache) upgrades the Group -1 security gate, provides the foundation for /admin controls, and secures sensitive commands (/backup, /logs) needed by subsequent phases.
**Delivers:** SQLite admin_users table & migration, src/bot/rbac.py (@require_role, Role enum, root admin anchor), dynamic Group -1 security gate, /admin interactive keyboard menu (whitelist CRUD, LLM model switcher), and in-memory ring buffer log handler (/logs).
**Addresses:** RBAC Persistence & Gate, Telegram Whitelist Management, LLM Model Switching, In-App Log Viewer.
**Avoids:** Pitfall 5 (RBAC privilege escalation & root Super Admin database lockout).

### Phase 2: Telegram Database Backup Engine & Scheduled Tasks
**Rationale:** Backup infrastructure must be operational before introducing natural language order mutation (which performs destructive database writes). Backups require the RBAC Super Admin gate from Phase 1.
**Delivers:** src/services/backup.py (VACUUM INTO + gzip compression + 48MB size check), manual /backup command delivering .sqlite3.gz to Super Admin DM, PTB JobQueue daily scheduled backup at 02:00 AM VN time, and /admin backup trigger integration.
**Uses:** python-telegram-bot[job-queue]~=22.8, SQLite VACUUM INTO, Python stdlib gzip, tempfile, and zoneinfo.
**Avoids:** Pitfall 2 (Live database snapshot corruption & Telegram 50MB backup failures) and PII leakage.

### Phase 3: 3-Way Intent Router & Natural Language Order Mutation
**Rationale:** Core feature milestone requiring Phase 1 user identity context, Phase 2 backup safety net, and v1.0 search/extraction engines. Combines intent routing, delta extraction, and ergonomic visual confirmation.
**Delivers:** OrderMutationDelta Pydantic schemas, src/services/router.py (3-way classifier cascade), multi-match order disambiguation picker, high-contrast Before ➡️ After visual diff formatter (120s TTL), mutation confirmation callback handlers (mut:*), and atomic apply_order_mutation database transaction with optimistic locking.
**Addresses:** 3-Way Intent Routing, NL Order Mutation, Visual Diff Cards, Ambiguity Action Pills, Core Field Mutations.
**Avoids:** Pitfall 3 (Intent collision & destructive blind updates) and Pitfall 4 (Stale diffs & race conditions).

### Phase 4: Containerization, Kubernetes Manifests & Production Deployment
**Rationale:** Packages the complete application into production-ready deployment artifacts with persistent volume guarantees, timezone correctness, and process termination safety.
**Delivers:** Multi-stage Dockerfile (python:3.12-slim, non-root user UID 10001, tzdata Asia/Ho_Chi_Minh), docker-compose.yml with named /app/data volume, Kubernetes manifests (deployment.yaml with strategy: Recreate and replicas: 1, pvc.yaml RWO, configmap.yaml, secret.yaml), Docker Hub publishing documentation, and SIGTERM graceful shutdown handler with PRAGMA wal_checkpoint(TRUNCATE).
**Addresses:** Containerization, Kubernetes Deployment, Production Operations.
**Avoids:** Pitfall 1 (Multi-replica & network storage SQLite corruption) and Pitfall 6 (Root execution, UTC timezone drift & unhandled SIGTERM).

---

### Phase Ordering Rationale

- **RBAC before Backup & Mutation:** Backups contain the entire SQLite database with customer PII; mutation allows altering financial and status data. Both must be strictly protected by the RBAC gate and root Super Admin anchor.
- **Backup before Mutation:** Destructive updates should never be introduced into a live store system without an automated, verified, and on-demand backup mechanism already active.
- **Mutation before Containerization:** Application logic and service boundaries must be completely finalized and unit-tested before packaging into Docker containers and Kubernetes manifests.
- **Containerization last:** Encapsulates the entire verified system, binds persistent volume storage, and guarantees production runtime invariants (non-root, timezone, single replica).

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 3 (3-Way Intent Router & NL Mutation):** Needs detailed prompt engineering and Vietnamese regex pattern tuning to ensure zero intent collision between casual search queries, voice-to-text transcripts, and mutation verbs.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (RBAC & Admin Suite):** Standard Python decorator pattern, SQLite CRUD table, and PTB inline callback menus.
- **Phase 2 (Telegram Backup Engine):** Standard SQLite VACUUM INTO + stdlib gzip + PTB JobQueue documentation.
- **Phase 4 (Containerization & Deployment):** Established multi-stage Docker build, Docker Compose, and Kubernetes single-pod Recreate deployment patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified PTB v22.8 [job-queue] extra with APScheduler~=3.10.4, SQLite VACUUM INTO spec, Python stdlib gzip, and Debian python:3.12-slim glibc compatibility. |
| Features | HIGH | Requirements directly derived from operator low-tech constraints, anti-features explicitly mapped, and UI card/button workflows established in v1.0. |
| Architecture | HIGH | Clean 4-layer decoupling; intent router separated from Telegram handlers; stateless callbacks with in-memory TTL drafts; single-writer SQLite WAL lifecycle. |
| Pitfalls | HIGH | Multi-replica SQLite corruption, live file copy failure, UTC timezone drift, and stale diff race conditions thoroughly documented with concrete code mitigations. |

**Overall confidence:** HIGH

### Gaps to Address

- **Vietnamese Voice-to-Text Mutation Noise:** Low-tech merchants frequently use voice-to-text dictation on Telegram which may omit punctuation or garble phonetically similar numbers (e.g. "bốn" vs "bốn mươi").
  *Handling during planning/execution:* Include diverse Vietnamese colloquial test cases in Phase 3 test suite; prompt LLM mutation extractor with few-shot examples of conversational shop slang.
- **In-Memory Draft Eviction Under High Concurrency:** If multiple admins initiate unconfirmed mutations simultaneously, memory usage could grow if TTL cleanups fail.
  *Handling during planning/execution:* Implement deterministic eviction helper clearing expired drafts (time.time() > expires_at) whenever a new mutation draft is registered.

---

## Sources

### Primary (HIGH confidence)
- python-telegram-bot Official Documentation & PyPI: Verified v22.8 release, [job-queue] extension, and ApplicationBuilder lifecycle hooks.
- SQLite Official Documentation: Verified VACUUM INTO atomic snapshot behavior in active WAL mode and locking mechanics.
- Telegram Bot API Documentation: Verified sendDocument limits (50MB for bots), inline button callback specifications, and error hierarchies.
- Docker & Kubernetes Official Documentation: Verified multi-stage Dockerfile best practices, non-root user configuration, and strategy.type: Recreate for single-replica stateful storage.

### Secondary (MEDIUM confidence)
- APScheduler 3.x Documentation: Verified run_daily timezone scheduling with ZoneInfo("Asia/Ho_Chi_Minh").
- OpenAI Python SDK Documentation: Verified structured outputs parsing and custom base_url routing for 9router.

---
*Research completed: 2026-10-25*
*Ready for roadmap: yes*
