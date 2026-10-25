# Stack Research: Milestone v1.1

**Domain:** Telegram Chatbot — NL Mutation, Telegram Admin Suite, In-App Log Viewer, Telegram DB Backup & Container Deployment (Docker / K8s)  
**Researched:** 2026-10-25  
**Confidence:** HIGH  

## Recommended Stack

Baseline v1.0 stack remains (`python-telegram-bot~=22.8`, `aiosqlite~=0.22.1`, `openai~=3.37.0`, `pydantic~=2.14.1`, `pydantic-settings~=2.16.1`). Additions focus strictly on containerization, Telegram-native administrative operations, automated backups, and log streaming.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **python:3.12-slim** | `3.12-slim` (Debian Bookworm) | Container base image | Standard glibc runtime. Avoids musl compile overhead for `pydantic-core` (Rust wheels). Minimal image size (~150MB) with complete compatibility for `aiosqlite` threads. |
| **python-telegram-bot[job-queue]** | `~=22.8` | Backup job scheduling | Official PTB extension bundling `APScheduler~=3.10.4`. Integrates directly into `ApplicationBuilder`. Provides `run_daily` with `ZoneInfo("Asia/Ho_Chi_Minh")`. Lifecycle-bound to bot polling. |
| **SQLite3 VACUUM INTO** | Stdlib (`sqlite3 >= 3.27`) | Safe online database snapshot | Atomic point-in-time snapshot executed asynchronously via `aiosqlite`. Copies DB while WAL mode is active without locking readers or writers. Zero external dependencies. |
| **gzip** | Stdlib | Snapshot compression | In-memory or stream compression of SQLite `.db` before Telegram upload. Compresses 10MB database to ~1-2MB. Zero external dependencies. |
| **Docker Multi-Stage Build** | Dockerfile spec 1.6+ | Container packaging | Separates builder (`pip install` into venv/user) from runner image. Enforces non-root user (`uid 10001:10001`) and controls volume mount permissions for `/app/data`. |
| **Kubernetes Manifests (RWO + Recreate)** | K8s API `apps/v1`, `v1` | Production orchestration | `Deployment` with `replicas: 1` and `strategy.type: Recreate`. Single `PersistentVolumeClaim` with `accessModes: [ReadWriteOnce]`. Prevents SQLite multi-writer corruption. |

### Supporting Libraries & Stdlib Modules

| Library / Module | Version | Purpose | When to Use |
|------------------|---------|---------|-------------|
| **logging.Handler + collections.deque** | Stdlib | In-Telegram log viewer | In-memory ring buffer (`RingBufferLogHandler`, maxlen=200). Captures recent bot activity; displays in Telegram chat on-demand via HTML `<pre><code>`. Zero external log stack. |
| **tempfile** | Stdlib | Temporary snapshot files | Generates isolated temporary files (`tempfile.NamedTemporaryFile`) for `VACUUM INTO` and gzip compression before sending document. |
| **zoneinfo** | Stdlib (`Python >= 3.9`) | Timezone awareness | Accurate scheduling of daily 02:00 AM VN backup (`ZoneInfo("Asia/Ho_Chi_Minh")`). |
| **enum.StrEnum** | Stdlib (`Python >= 3.11`) | RBAC role definitions | Typed admin role mapping: `SUPER_ADMIN = "super_admin"`, `ADMIN = "admin"`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **docker-compose** | v2.20+ | Local container testing | Runs container with `./data:/app/data` volume and local `.env`. |
| **ruff** | `>=0.9.0` | Code style & linting | Already configured in `pyproject.toml`. |
| **pytest** & **pytest-asyncio** | `>=8.3.0` | Test suite | Test RBAC decorators, mutation parser schemas, backup routines, and ring buffer handlers. |

---

## Installation

### pyproject.toml Update

Only 1 dependency addition required: `python-telegram-bot[job-queue]`. All other additions use Python stdlib or container runtime manifests.

```toml
[project]
name = "cassette-store"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "python-telegram-bot[job-queue]~=22.8",
    "aiosqlite~=0.22.1",
    "pydantic~=2.14.1",
    "pydantic-settings~=2.16.1",
    "openai~=3.37.0",
]
```

```bash
# Install updated dependencies
pip install "python-telegram-bot[job-queue]~=22.8"
```

---

## Technical Implementations & Architectural Decisions

### 1. Docker Multi-Stage Build (`Dockerfile`)

SQLite WAL mode requires container process to write to parent directory of database file (to create `-wal` and `-shm` lock files). Non-root user must own `/app/data`.

```dockerfile
# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root user
RUN groupadd -g 10001 botuser && \
    useradd -u 10001 -g botuser -s /bin/sh -m botuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Prepare app and data directories with permissions
RUN mkdir -p /app/data && chown -R botuser:botuser /app

COPY --chown=botuser:botuser . /app

USER botuser

VOLUME ["/app/data"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/app/data/cassette_store.db

CMD ["python", "-m", "src.main"]
```

### 2. Kubernetes Manifests: Single-Writer Safety

SQLite in WAL mode allows multiple readers within same OS process/threads, but only ONE writer process on same volume. Multiple container instances will corrupt database.

#### Deployment Strategy: Recreate
Default K8s strategy is `RollingUpdate`. RollingUpdate starts new Pod before terminating old Pod. If both attach to single ReadWriteOnce PVC or write to same SQLite DB, attachment fails or DB corrupts. `Recreate` is mandatory.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cassette-store-bot
  labels:
    app: cassette-store-bot
spec:
  replicas: 1  # STRICT: SQLite single-writer constraint
  strategy:
    type: Recreate  # Terminate old pod before mounting RWO PVC to new pod
  selector:
    matchLabels:
      app: cassette-store-bot
  template:
    metadata:
      labels:
        app: cassette-store-bot
    spec:
      securityContext:
        fsGroup: 10001
      containers:
        - name: bot
          image: cassette-store-bot:v1.1
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: cassette-store-config
            - secretRef:
                name: cassette-store-secret
          volumeMounts:
            - name: db-storage
              mountPath: /app/data
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
      volumes:
        - name: db-storage
          persistentVolumeClaim:
            claimName: cassette-store-pvc
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: cassette-store-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

### 3. Telegram Document Backup Mechanism

No external APIs (no GitHub REST, no S3). Uses `aiosqlite` `VACUUM INTO` + stdlib `gzip` + `bot.send_document`.

```python
import gzip
import os
import tempfile
from datetime import datetime
from pathlib import Path
import aiosqlite
from telegram import Bot

async def backup_sqlite_to_telegram(
    db: aiosqlite.Connection,
    bot: Bot,
    super_admin_chat_id: int
) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_db_path = Path(tmp_dir) / f"snapshot_{timestamp}.db"
        gz_db_path = Path(tmp_dir) / f"cassette_backup_{timestamp}.sqlite3.gz"

        # 1. Atomic snapshot without locking active WAL connections
        await db.execute("VACUUM INTO ?", (str(raw_db_path),))

        # 2. Compress via stdlib gzip
        with open(raw_db_path, "rb") as f_in, gzip.open(gz_db_path, "wb") as f_out:
            while chunk := f_in.read(64 * 1024):
                f_out.write(chunk)

        # 3. Send document directly to Super Admin
        caption = f"📦 *Sao lưu cơ sở dữ liệu tự động*\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\nKích thước: {os.path.getsize(gz_db_path) / 1024:.1f} KB"
        with open(gz_db_path, "rb") as doc_file:
            await bot.send_document(
                chat_id=super_admin_chat_id,
                document=doc_file,
                filename=f"cassette_backup_{timestamp}.sqlite3.gz",
                caption=caption,
                parse_mode="Markdown"
            )
```

### 4. Scheduling: PTB JobQueue vs Asyncio Task

#### Primary Recommendation: PTB JobQueue (`python-telegram-bot[job-queue]`)
Bundles `APScheduler`. Integrates natively with PTB `Application`:

```python
import datetime
from zoneinfo import ZoneInfo
from telegram.ext import ApplicationBuilder, ContextTypes

async def daily_backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.bot_data["db"]
    super_admin_id = context.bot_data["settings"].super_admin_ids[0]
    await backup_sqlite_to_telegram(db, context.bot, super_admin_id)

def register_backup_schedule(application) -> None:
    vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    backup_time = datetime.time(hour=2, minute=0, tzinfo=vn_tz)
    application.job_queue.run_daily(
        daily_backup_job,
        time=backup_time,
        name="daily_sqlite_backup"
    )
```

#### Minimal Alternative: Native Asyncio Task Loop (Zero Extra Dependencies)
If `APScheduler` is disallowed, a 20-line native task loop runs directly in `post_init`:

```python
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

async def asyncio_backup_runner(app) -> None:
    vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    while True:
        now = datetime.now(vn_tz)
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        await asyncio.sleep(sleep_seconds)
        try:
            db = app.bot_data["db"]
            admin_id = app.bot_data["settings"].super_admin_ids[0]
            await backup_sqlite_to_telegram(db, app.bot, admin_id)
        except Exception as e:
            logging.error(f"Scheduled backup failed: {e}")
```

*Recommendation:* Use `python-telegram-bot[job-queue]`. It handles missed triggers, job inspection, manual re-scheduling, and graceful shutdown cleanly with 1 dependency declaration.

### 5. In-Telegram Log Viewer (Memory Ring Buffer)

Stdlib `logging.Handler` implementation with fixed memory ceiling:

```python
import collections
import logging

class RingBufferLogHandler(logging.Handler):
    def __init__(self, capacity: int = 200):
        super().__init__()
        self.buffer = collections.deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.append(msg)
        except Exception:
            self.handleError(record)

    def get_recent_logs(self, limit: int = 25) -> list[str]:
        return list(self.buffer)[-limit:]
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **python:3.12-slim** | **python:3.12-alpine** | Only if minimal disk space is strictly paramount (<50MB). Avoid on Python: Alpine uses `musl` libc, causing compilation issues with Rust wheels (`pydantic-core`) and potential DNS/threading latency. |
| **PTB[job-queue]** | **asyncio.sleep loop** | When absolutely zero new pip packages are permitted. Native asyncio loop works for a single static schedule, but lacks job management, retry intervals, and pause/resume buttons. |
| **Telegram Document Backup** | **GitHub REST API / AWS S3** | Only if long-term offsite multi-year archival is required by enterprise compliance. For a small shop, sending `.gz` directly to Telegram Super Admin is instant, free, encrypted, and accessible on phone. |
| **Kubernetes Recreate Strategy** | **RollingUpdate Strategy** | Never with SQLite. RollingUpdate attempts to run 2 pods concurrently mounting the same volume, causing PVC lock failures or DB corruption. |
| **In-Memory RingBuffer Log Handler** | **Prometheus + Grafana / Loki** | Only for high-scale microservice clusters. For single-bot Telegram operator, ring buffer viewed directly via `/logs` menu provides immediate operational visibility with zero infrastructure overhead. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Alpine Linux base image (`python:3.12-alpine`)** | Lacks standard glibc. Fails to install pre-built manylinux wheels for `pydantic-core`; triggers slow in-container Rust/C compilation; causes subtle SQLite async worker thread crashes. | `python:3.12-slim`. |
| **Multiple Kubernetes replicas (`replicas > 1`)** | SQLite does not support distributed multi-process concurrent writers across network mounts. Leads directly to `database is locked` errors and data corruption. | Single replica (`replicas: 1`) with `strategy: Recreate`. |
| **Kubernetes RollingUpdate deployment** | Starts new Pod before terminating old Pod. Dual-attach conflict on ReadWriteOnce volume. | `strategy: type: Recreate`. |
| **External database (PostgreSQL / MySQL)** | Massive infrastructure overhead, connection pooling maintenance, operational friction for single-store retail bot. | Embedded SQLite WAL mode. |
| **Celery / Redis / RQ** | Requires separate broker service, worker daemon, and monitoring for a task that runs once every 24 hours. | `python-telegram-bot[job-queue]` or native asyncio task. |
| **shutil.copyfile on live SQLite DB** | In WAL mode, copying the `.db` file while writes occur results in torn pages or missing uncommitted WAL data. | SQLite `VACUUM INTO` command via `aiosqlite`. |
| **Terminal Console CLI (prompt_toolkit)** | Out of scope for milestone v1.1. Operator manages 100% via Telegram inline UI; interactive server terminal adds process interleaving bugs. | Telegram Admin Suite with RBAC. |

---

## Stack Patterns by Variant

**If deployed on bare VPS / Single Host:**
- Use `docker-compose.yml` with host volume `./data:/app/data`.
- Simple `.env` file management.
- Container restart policy: `restart: unless-stopped`.

**If deployed on Kubernetes cluster (K8s / K3s):**
- Use provided manifests (`Deployment`, `PVC`, `ConfigMap`, `Secret`).
- Ensure storage class supports `ReadWriteOnce`.
- Enforce `replicas: 1` and `strategy: Recreate`.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `python:3.12-slim` | Debian 12 (Bookworm), glibc 2.36 | Seamless compatibility with Pydantic v2 wheels and Python 3.12 async. |
| `python-telegram-bot[job-queue]==22.8` | `APScheduler~=3.10.4`, `pytz`, `httpx~=0.28.1` | Native extension for PTB v22.8; runs cleanly in Python 3.12 event loop. |
| `aiosqlite==0.22.1` | `sqlite3 >= 3.27` | Native support for `VACUUM INTO` statement. |
| `Docker Engine >= 24.0` | Compose file v2 / multi-stage build | Supports non-root user volume ownership and BuildKit syntax. |
| `Kubernetes >= 1.25` | `apps/v1`, `v1` | Supports standard `ReadWriteOnce` PVC and `Recreate` deployment strategy. |

---

## Sources

- [Docker Official Python Images](https://hub.docker.com/_/python) — verified `python:3.12-slim` specifications and glibc compatibility.
- [PyPI - python-telegram-bot](https://pypi.org/project/python-telegram-bot/) — verified v22.8 `[job-queue]` extra with `APScheduler~=3.10.4`.
- [SQLite Official Documentation - VACUUM INTO](https://www.sqlite.org/lang_vacuum.html#vacuuminto) — verified atomic online backup behavior in active WAL mode.
- [Kubernetes Official Docs - Deployments Strategy](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy) — verified `type: Recreate` for single-instance stateful workloads with RWO volume constraints.
