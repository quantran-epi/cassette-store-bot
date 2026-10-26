# Phase 8: Containerization & Kubernetes Deployment - Research

**Researched:** 2026-10-27
**Domain:** Docker Containerization, Multi-Arch CI/CD (GitHub Actions), Single-Replica Kubernetes Deployment, SQLite WAL Lifecycle & Health Probes
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 1. Healthcheck & Probes Strategy
- **D-01 (Cơ chế probe):** Dùng Heartbeat file (`/tmp/bot_heartbeat`) do PTB JobQueue cập nhật định kỳ + kiểm tra kết nối SQLite DB ping (`SELECT 1`). Không mở port mạng HTTP ra ngoài, an toàn tuyệt đối, phù hợp cả Docker container và K8s exec probe.
- **D-02 (Chu kỳ & Timeout):** JobQueue ghi heartbeat mỗi 30s. Probe script báo lỗi nếu file cũ hơn 90s hoặc DB ping timeout > 2s. K8s probe đặt `periodSeconds: 30`, `failureThreshold: 3` (tự khởi động lại pod sau ~1.5 phút nếu bị treo).
- **D-03 (Script triển khai):** Tạo file riêng `src/scripts/healthcheck.py` chỉ dùng Python stdlib (`os`, `time`, `sqlite3`, `sys`), không import thư viện ngoài nặng, chạy siêu nhẹ (<0.1s), trả về exit code 0 (healthy) hoặc 1 (unhealthy). Gọi qua lệnh: `python -m src.scripts.healthcheck`.
- **D-04 (K8s Probes):** Cấu hình cả `livenessProbe` và `readinessProbe` trong Deployment manifest gọi chung healthcheck script:
  - `readinessProbe`: `initialDelaySeconds: 5`, `periodSeconds: 15` để K8s đánh dấu Pod Ready nhanh.
  - `livenessProbe`: `initialDelaySeconds: 15`, `periodSeconds: 30`, `failureThreshold: 3` để tự động restart Pod khi treo.

#### 2. Graceful Shutdown & WAL Checkpoint
- **D-05 (Bắt tín hiệu SIGTERM/SIGINT):** Dùng hook vòng đời chính quy của python-telegram-bot: `ApplicationBuilder.post_shutdown(callback)`. Khi container nhận SIGTERM hoặc SIGINT, PTB tự động dừng nhận update mới, hoàn tất các handler đang chạy dở dang và gọi `post_shutdown`.
- **D-06 (Chiến lược WAL Checkpoint):** Trong `post_shutdown`, thực thi `PRAGMA wal_checkpoint(TRUNCATE);` để gom toàn bộ dữ liệu từ file `-wal` vào file `.db` chính và cắt dung lượng file `-wal` về 0 bytes trước khi đóng kết nối SQLite sạch sẽ. Khớp đúng yêu cầu DEP-05.
- **D-07 (Grace Period Budget):** Cấu hình `terminationGracePeriodSeconds: 30` trong Kubernetes Deployment và `stop_grace_period: 30s` trong `docker-compose.yml`. Đảm bảo đủ thời gian cho các request LLM đang xử lý (2-10s) và lệnh checkpoint WAL (<1s) hoàn tất trước khi bị hệ điều hành gửi SIGKILL.
- **D-08 (Logging lúc tắt):** Ghi log có cấu trúc vào stdout (trạng thái checkpoint, số trang ghi, thời gian thực thi) với exit code 0. Không gửi tin nhắn Telegram lúc shutdown để tránh rủi ro treo do network bị ngắt trước.

#### 3. Volume Layout & PVC Storage
- **D-09 (Cấu trúc thư mục Volume):** Thư mục mount thống nhất là `/app/data`. Database chính đặt tại `/app/data/cassette_store.db`, thư mục sao lưu snapshot đặt tại `/app/data/backups/`. Một volume duy nhất bảo toàn toàn bộ dữ liệu và file nén backup lịch sử.
- **D-10 (Non-root & Permissions):** Dockerfile tạo user `appuser` (UID 10001, GID 10001) và cấp quyền thư mục `/app/data`. Kubernetes Pod spec cấu hình `securityContext`:
  ```yaml
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
  ```
  K8s tự động gán quyền sở hữu volume cho GID 10001 mà không cần root `initContainer`.
- **D-11 (Thông số K8s PVC):** Dung lượng 2Gi, `accessModes: [ReadWriteOnce]` (RWO - bắt buộc vì SQLite là single-writer), không gán cứng `storageClassName` để tự động dùng default StorageClass của cluster (local-path, gp3, standard...).
- **D-12 (Docker Compose Volume):** Dùng Docker named volume `cassette_data:/app/data` làm mặc định, có kèm dòng comment hướng dẫn chuyển sang host bind mount (`./data:/app/data`) nếu muốn inspect file DB trực tiếp trên máy host.

#### 4. Image Build, GitHub Actions & All-in-One K8s Deploy
- **D-13 (Multi-stage Dockerfile tối ưu cache):**
  - Stage 1 (builder): Nền `python:3.12-slim`, copy riêng `pyproject.toml`, cài đặt dependencies qua `pip wheel` / `pip install --no-cache-dir --prefix=/install .` để tận dụng Docker cache layer khi sửa code src/.
  - Stage 2 (runtime): Nền `python:3.12-slim`, cài `tzdata` thiết lập `TZ=Asia/Ho_Chi_Minh`, copy thư viện từ stage 1, tạo non-root user `appuser` (UID 10001), tạo `/app/data` và `/app/data/backups`, copy mã nguồn, chạy dưới quyền `USER 10001`.
  - File `.dockerignore` triệt để: loại bỏ `.git`, `.venv`, `.planning`, `*.db*`, `backups/`, `__pycache__`, tests.
- **D-14 (GitHub Actions CI/CD đẩy Docker Hub):**
  - Workflow `.github/workflows/docker-publish.yml` tự động chạy khi push code lên nhánh `main` hoặc push git tag `v*`.
  - Thiết lập Docker Buildx + QEMU để build multi-arch (`linux/amd64`, `linux/arm64`).
  - Đăng nhập Docker Hub bằng GitHub Secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`).
  - Tự động tag image: `latest` và git commit sha / version tag, sau đó push lên Docker Hub.
- **D-15 (All-in-One Kubernetes Manifest):**
  - Tạo file duy nhất `k8s/all-in-one.yaml` chứa đầy đủ cấu hình phân tách bằng `---`:
    - `ConfigMap`: Chứa biến không nhạy cảm (`TZ`, `SQLITE_DB_PATH=/app/data/cassette_store.db`, `NINE_ROUTER_BASE_URL`, `NINE_ROUTER_MODEL_ID`).
    - `Secret`: Chứa mẫu các biến bảo mật dạng `stringData` (`TELEGRAM_BOT_TOKEN`, `NINE_ROUTER_API_KEY`, `TELEGRAM_WHITELIST_USER_IDS`, `TELEGRAM_SUPER_ADMIN_ID`).
    - `PersistentVolumeClaim`: 2Gi RWO.
    - `Deployment`: `replicas: 1`, `strategy.type: Recreate`, mount volume `/app/data`, `securityContext` non-root UID 10001 + `fsGroup: 10001`, liveness + readiness probe, grace period 30s.
  - Người dùng chỉ cần cập nhật token vào Secret và chạy 1 lệnh duy nhất:
    `kubectl apply -f k8s/all-in-one.yaml`

### Claude's Discretion
- Chi tiết cấu trúc multi-stage Dockerfile và cờ biên dịch tối ưu dung lượng image.
- Chi tiết các nhãn (labels) metadata trong Kubernetes manifest (`app: cassette-store-bot`).

### Deferred Ideas (OUT OF SCOPE)
None — thảo luận tập trung 100% vào Containerization & Kubernetes Deployment (Phase 8).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **DEP-01** | `Dockerfile` tối ưu multi-stage trên nền `python:3.12-slim`, chạy với non-root user (UID 10001) và cấu hình múi giờ `TZ=Asia/Ho_Chi_Minh` | Multi-stage build (builder / runtime), non-root `appuser` (UID/GID 10001), cài `tzdata` + symlink `/etc/localtime`, `.dockerignore` triệt để. |
| **DEP-02** | Thư mục dữ liệu `/app/data` được cấu hình volume mount để bảo toàn file SQLite chính và các file WAL (`-wal`, `-shm`) khi container khởi động lại | K8s PVC RWO 2Gi mount vào `/app/data`, Docker Compose named volume `cassette_data:/app/data`, đường dẫn DB `/app/data/cassette_store.db` và backups `/app/data/backups`. |
| **DEP-03** | File cấu hình `docker-compose.yml` chuẩn production với biến môi trường, health check, chính sách restart và volume mount dữ liệu bền vững | Compose v2/v3 spec: `restart: unless-stopped`, `stop_grace_period: 30s`, `healthcheck: test: ["CMD", "python", "-m", "src.scripts.healthcheck"]`, env mapping từ `.env`. |
| **DEP-04** | Bộ manifest Kubernetes chuẩn: `Deployment` (enforce `replicas: 1` và `strategy.type: Recreate`), PersistentVolumeClaim (RWO), ConfigMap và Secret | File `k8s/all-in-one.yaml` all-in-one: single-pod strict enforcement via `replicas: 1` + `strategy: { type: Recreate }`, `runAsNonRoot: true`, `fsGroup: 10001`, liveness/readiness exec probes. |
| **DEP-05** | Cơ chế tắt container an toàn (graceful shutdown) bắt tín hiệu `SIGTERM`/`SIGINT`, thực thi `PRAGMA wal_checkpoint(TRUNCATE)` và đóng kết nối DB sạch sẽ | PTB `ApplicationBuilder.post_shutdown` hook + aiosqlite `PRAGMA wal_checkpoint(TRUNCATE)` + pod `terminationGracePeriodSeconds: 30`. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.12+ (or 3.13) + SQLite (sqlite3 / aiosqlite) + python-telegram-bot (v20+ async).
- **Zero Webhook / HTTP port exposure**: Bot chạy chế độ long-polling (`Application.run_polling()`). Không mở port HTTP, không cần Nginx/ngrok/FastAPI.
- **SQLite WAL safety**: SQLite là single-writer. Tuyệt đối không scale horizontal pod (`replicas: 1` + `Recreate`). Checkpoint WAL sạch khi shutdown.
- **Bảo mật**: Whitelist Telegram User IDs, không lưu token/secret vào image, pass qua K8s Secret hoặc Docker Compose `.env`.
- **Độ tin cậy & UX**: Tự khởi động lại nếu tiến trình polling hoặc kết nối DB bị treo thông qua file heartbeat + healthcheck probe.

## Summary

Phase 8 là giai đoạn hoàn thiện việc đóng gói và triển khai sản phẩm Cassette Store Telegram Chatbot lên môi trường sản xuất. Mục tiêu chính là cung cấp quy trình đóng gói container Docker siêu nhẹ, bảo mật cao và vận hành bền bỉ trên cả Docker Compose cục bộ lẫn cụm Kubernetes chuyên nghiệp.

Điểm mấu chốt kỹ thuật của phase nằm ở việc bảo đảm toàn vẹn dữ liệu cho SQLite khi chạy trong môi trường container có vòng đời động (ephemeral lifecycle). Với cơ chế ghi nhận WAL (Write-Ahead Logging), nếu container bị kill đột ngột (`SIGKILL`), các trang dữ liệu trong `-wal` có thể chưa được checkpoint đầy đủ hoặc file locks bị bỏ dở. Phase 8 giải quyết triệt để vấn đề này thông qua 3 trụ cột:
1. **Single-replica constraint:** Cấu hình Kubernetes `replicas: 1` kết hợp chiến lược rollout `strategy.type: Recreate` (giết pod cũ trước khi tạo pod mới) nhằm loại trừ hoàn toàn nguy cơ 2 pods cùng ghi vào một file SQLite qua shared volume.
2. **Graceful Shutdown & WAL Checkpoint (DEP-05):** Đăng ký hook `ApplicationBuilder.post_shutdown` trong PTB để đón bắt tín hiệu `SIGTERM`/`SIGINT`. Trước khi tiến trình dừng, bot kích hoạt lệnh `PRAGMA wal_checkpoint(TRUNCATE)` để thu hồi toàn bộ trang log vào file `.db` chính và cắt kích thước file `-wal` về 0 byte.
3. **Heartbeat Health Probes (DEP-03, DEP-04):** Bot không mở port HTTP nên các probe kiểm tra sức khỏe được triển khai dạng `exec` script (`python -m src.scripts.healthcheck`). PTB JobQueue ghi nhận mốc thời gian vào `/tmp/bot_heartbeat` mỗi 30s; script probe kiểm tra độ trễ heartbeat (<90s) và thực hiện ping nhanh SQLite (`SELECT 1`, timeout 2s) bằng Python stdlib siêu nhẹ.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| **Container Runtime Packaging** | Infrastructure / Docker | Python Runtime | Dockerfile multi-stage đóng gói Python dependencies và application code, thiết lập user non-root UID 10001 và timezone Asia/Ho_Chi_Minh. |
| **CI/CD Multi-Arch Publishing** | CI/CD (GitHub Actions) | Docker Hub Registry | Tự động hóa build multi-arch (`linux/amd64`, `linux/arm64`) qua QEMU/Buildx và push image tag lên Docker Hub. |
| **Persistent Storage & Volume Mount** | Kubernetes PVC / Compose Volume | Local Host Filesystem | Mount `/app/data` cố định để bảo toàn file SQLite chính (`cassette_store.db`), các file WAL (`-wal`, `-shm`) và snapshots sao lưu (`backups/`). |
| **Orchestration & Pod Lifecycle** | Kubernetes Deployment | Docker Compose | Cam kết `replicas: 1` và `strategy.type: Recreate` để tránh xung đột ghi SQLite đồng thời; quản lý grace period 30s. |
| **Health Checking & Probes** | Local Process Exec Probe | PTB JobQueue & SQLite | Heartbeat file `/tmp/bot_heartbeat` kết hợp SQLite connection ping; không mở port HTTP. |
| **Graceful Shutdown & WAL Checkpoint** | Application Layer (`src/bot/app.py`) | SQLite Engine | PTB `post_shutdown` hook bắt SIGTERM/SIGINT, hoàn tất handlers dở dang, chạy `PRAGMA wal_checkpoint(TRUNCATE)` và đóng kết nối sạch sẽ. |

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| **Docker Buildx / QEMU** | Docker 24.0+ / Buildx 0.10+ | Multi-arch container image builder | Chuẩn công nghiệp build multi-arch `linux/amd64` và `linux/arm64` chạy trơn tru trên cả máy Mac Apple Silicon, server x86 và Raspberry Pi. [VERIFIED: Docker Official] |
| **python:3.12-slim** | Debian 12 (bookworm) slim | Base container image | Dung lượng tối ưu (~130MB), đi kèm thư viện C tiêu chuẩn (glibc) cần thiết cho SQLite extension và wheel prebuilt của Python. [VERIFIED: Docker Official] |
| **Kubernetes API** | `apps/v1`, `v1` | K8s manifest schema | Chuẩn triển khai container hiện đại. Hỗ trợ đầy đủ `Deployment`, `PersistentVolumeClaim`, `ConfigMap`, `Secret`, `securityContext` và `exec` probes. [VERIFIED: K8s Docs] |
| **Docker Compose** | Compose Spec (v2+) | Local / single-node orchestration | Chuẩn declarative cho môi trường single-host production hoặc developer staging. [VERIFIED: Docker Docs] |

### Supporting
| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| **tzdata** | OS package (apt-get) | Timezone data in Linux container | Bắt buộc cài đặt để Python `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` định thời gian đúng tại Việt Nam (UTC+7). [VERIFIED: Debian pkg] |
| **python stdlib (`sqlite3`, `time`, `os`, `sys`)** | Python 3.12+ stdlib | Healthcheck script runtime | Dùng trong `src/scripts/healthcheck.py` để probe container không tốn memory và không có external dependency. [VERIFIED: Python Docs] |
| **docker/build-push-action** | `v6` | GitHub Actions Buildx workflow action | Action chính thức từ Docker Inc. để build và push image lên Docker Hub có layer cache tự động qua GHA cache. [VERIFIED: GitHub Marketplace] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **Python slim (`python:3.12-slim`)** | `python:3.12-alpine` | Alpine dùng `musl-libc` thường gây lỗi tương thích binary wheel với một số thư viện C (aiosqlite/pydantic/cffi) và thiếu tzdata cấu hình chuẩn. `slim` an toàn và tương thích 100%. |
| **Heartbeat File Exec Probe** | Lightweight HTTP Server (e.g. aiohttp/FastAPI) | Mở thêm HTTP port làm tăng attack surface, tiêu tốn CPU/RAM vô ích cho một Telegram bot không nhận webhook bên ngoài. File heartbeat + DB ping là mô hình chuẩn cho daemon process. |
| **Deployment with Recreate** | StatefulSet | StatefulSet mang tính chất phức tạp không cần thiết cho 1 pod đơn lẻ và yêu cầu Headless Service. `Deployment` kèm `replicas: 1` + `strategy: Recreate` đơn giản hơn và đạt đúng cam kết single-replica an toàn. |

## Package Legitimacy Audit

> Phase 8 không cài đặt thêm package Python bên ngoài mới nào vào `pyproject.toml`. Các công cụ triển khai sử dụng Docker, Kubernetes, GitHub Actions và Python standard library (`sqlite3`, `time`, `os`, `sys`).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| None (Zero new packages) | N/A | N/A | N/A | N/A | [OK] | Approved |

**Packages removed due to [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
[Developer / Git Repo]
        │
        ├── git push main / tag v*
        ▼
[GitHub Actions CI/CD]
        │  - Docker Buildx + QEMU
        │  - Multi-arch (amd64 / arm64)
        │  - Push image
        ▼
[Docker Hub Registry]
   (image: latest, sha-*)
        │
        ├── docker-compose pull / kubectl apply
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Host / Kubernetes Node                                                 │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Container / Pod: cassette-store-bot                              │  │
│  │ User: appuser (UID 10001) | TZ: Asia/Ho_Chi_Minh                 │  │
│  │                                                                  │  │
│  │  ┌───────────────────────┐         ┌───────────────────────────┐ │  │
│  │  │ PTB Application Event │         │ Background JobQueue       │ │  │
│  │  │ Loop (Polling Telegram│         │  - Daily Backup (02:00)   │ │  │
│  │  │ Handlers & LLM)       │         │  - Heartbeat Job (30s)    │ │  │
│  │  └──────────┬────────────┘         └─────────────┬─────────────┘ │  │
│  │             │                                    │               │  │
│  │             │ (Writes)                           │ (Touches)     │  │
│  │             ▼                                    ▼               │  │
│  │  ┌───────────────────────┐         ┌───────────────────────────┐ │  │
│  │  │ aiosqlite connection  │         │ File: /tmp/bot_heartbeat  │ │  │
│  │  │ (WAL Mode enabled)    │         │ (mtime updated every 30s) │ │  │
│  │  └──────────┬────────────┘         └─────────────▲─────────────┘ │  │
│  │             │                                    │               │  │
│  │  ═══════════╪════════════════════════════════════╪════════════   │  │
│  │  Probes:    │                  ┌─────────────────┴─────────────┐ │  │
│  │             └─────────────────►│ Exec: python -m               │ │  │
│  │   liveness / readiness         │ src.scripts.healthcheck       │ │  │
│  │   probe checks both            │ (Heartbeat < 90s & DB Ping)   │ │  │
│  │                                └───────────────────────────────┘ │  │
│  │  Graceful Shutdown:                                              │  │
│  │   SIGTERM ──► PTB post_shutdown ──► PRAGMA wal_checkpoint(TRUNCATE)│  │
│  │               (Finish tasks)        Close DB cleanly             │  │
│  └─────────────────────┬────────────────────────────────────────────┘  │
│                        │ Mount: /app/data                              │
│                        ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Persistent Storage (PVC 2Gi RWO / Docker Named Volume)           │  │
│  │   ├── cassette_store.db      (Primary SQLite DB file)            │  │
│  │   ├── cassette_store.db-wal  (WAL journal file)                  │  │
│  │   ├── cassette_store.db-shm  (Shared memory index)               │  │
│  │   └── backups/               (Gzip snapshot archives .sqlite3.gz)│  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
cassette-store/
├── Dockerfile                          # Multi-stage container build (UID 10001, TZ VN)
├── .dockerignore                       # Exclude git, venv, data, planning, caches
├── docker-compose.yml                  # Production compose setup with named volume & healthcheck
├── .github/
│   └── workflows/
│       └── docker-publish.yml          # Buildx multi-arch CI/CD pushing to Docker Hub
├── k8s/
│   └── all-in-one.yaml                 # Consolidated manifest (ConfigMap, Secret, PVC, Deployment)
├── src/
│   ├── bot/
│   │   └── app.py                      # Added heartbeat job + post_shutdown WAL checkpoint
│   └── scripts/
│       ├── __init__.py
│       └── healthcheck.py              # Zero-dep stdlib healthcheck probe script
└── tests/
    └── test_deployment_artifacts.py    # Verification tests for healthcheck, shutdown & manifests
```

### Pattern 1: Multi-stage Dockerfile with Pre-cached Wheels
**What:** Phân tách rõ ràng stage build (cài đặt `setuptools`, build wheel/prefix) và stage runtime (chỉ chứa binary và source code cần thiết, stripped layer).
**When to use:** DEP-01, tối ưu tốc độ build và kích thước image, bảo đảm non-root execution.
**Example:**
```dockerfile
# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Minimal Runtime
FROM python:3.12-slim AS runtime

# Cấu hình múi giờ Việt Nam và biến môi trường Python chuẩn container
ENV TZ=Asia/Ho_Chi_Minh \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages:$PYTHONPATH"

# Cài đặt tzdata để zoneinfo hoạt động chính xác
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Tạo non-root user appuser (UID 10001, GID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Sao chép installed packages từ builder
COPY --from=builder /install /install

# Tạo thư mục làm việc và thư mục dữ liệu với quyền sở hữu cho appuser
WORKDIR /app
RUN mkdir -p /app/data /app/data/backups && \
    chown -R appuser:appgroup /app

# Sao chép mã nguồn ứng dụng
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup main.py ./

USER 10001

CMD ["python", "main.py"]
```

### Pattern 2: Application Lifecycle Hook for Graceful Shutdown
**What:** PTB cung cấp `ApplicationBuilder.post_shutdown(coroutine)`. Hook này được gọi sau khi `Application.stop()` và `Application.shutdown()` hoàn tất xử lý các update đang dở dang. Tại đây, gọi `PRAGMA wal_checkpoint(TRUNCATE)` để thu hồi WAL và đóng kết nối an toàn.
**When to use:** DEP-05, bảo vệ SQLite khỏi tình trạng checkpoint dang dở khi container tắt.
**Example:**
```python
# Trong src/bot/app.py
async def post_shutdown_cleanup(app: Application) -> None:
    """Execute clean WAL checkpoint and close database resources on SIGTERM/SIGINT."""
    logger.info("Initiating graceful shutdown sequence...")
    settings = app.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db")
    
    try:
        # Checkpoint WAL truncate to write all pages to main DB file and resize WAL to 0
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            res = await cursor.fetchall()
            logger.info("SQLite WAL checkpoint completed successfully: %s", res)
    except Exception as e:
        logger.error("Error during WAL checkpoint in post_shutdown: %s", e)
    finally:
        logger.info("Graceful shutdown completed. Process ready to exit.")
```

### Pattern 3: Zero-Dependency Healthcheck Probe
**What:** Script `src/scripts/healthcheck.py` kiểm tra 2 điều kiện:
1. File heartbeat `/tmp/bot_heartbeat` tồn tại và có `time.time() - mtime < 90` (JobQueue vẫn đang schedule đều mỗi 30s).
2. SQLite query `SELECT 1` với timeout 2.0s thành công.
Nếu thỏa mãn cả 2, thoát `sys.exit(0)`. Nếu không, in lỗi ra stderr và thoát `sys.exit(1)`.
**When to use:** D-01, D-02, D-03 trong Dockerfile `HEALTHCHECK`, Docker Compose `healthcheck`, K8s `livenessProbe` và `readinessProbe`.

### Anti-Patterns to Avoid
- **Chạy container dưới quyền `root`:** Rủi ro bảo mật nghiêm trọng. Bắt buộc tạo user `appuser` (UID 10001) và set `USER 10001` trong Dockerfile, kết hợp `runAsNonRoot: true` trong Kubernetes pod securityContext.
- **Dùng RollingUpdate strategy cho SQLite pod trong Kubernetes:** Nếu dùng `RollingUpdate`, K8s sẽ tạo Pod mới trước khi Pod cũ bị tắt (`maxSurge > 0`), dẫn đến 2 Pod cùng mount một PersistentVolume và ghi đồng thời vào file SQLite (`SQLITE_BUSY` hoặc hỏng lock WAL). Bắt buộc dùng `strategy.type: Recreate`.
- **Gán cứng `storageClassName` trong Kubernetes manifest:** Mỗi cluster (k3s, minikube, EKS, GKE, bare-metal) có tên StorageClass mặc định khác nhau (`local-path`, `standard`, `gp3`). Gán cứng sẽ khiến PVC rơi vào trạng thái `Pending`. Hãy để trống để K8s tự bind default StorageClass.
- **Mở port HTTP không cần thiết chỉ để làm healthcheck:** Làm phình codebase, tăng nguy cơ tấn công mạng. Exec probe đọc file heartbeat cục bộ là phương án tối giản, nhẹ và an toàn nhất cho Telegram long-polling daemon.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Multi-Arch Compilation** | Tự chạy build script trên nhiều máy | Docker Buildx (`docker/setup-buildx-action`) + QEMU (`docker/setup-qemu-action`) | Buildx tự động cross-compile `linux/amd64` và `linux/arm64` trong 1 pipeline duy nhất và tự động tạo OCI multi-arch image manifest trên Docker Hub. |
| **Container Heartbeat & Health Tracking** | Tự dựng micro HTTP server (FastAPI/aiohttp) trong bot process | File touch mtime (`/tmp/bot_heartbeat`) qua PTB `JobQueue.run_repeating` + Python stdlib probe script | Zero memory overhead, không mở port mạng, kiểm tra trực tiếp cả trạng thái event loop (JobQueue) lẫn khả năng đọc ghi SQLite. |
| **Volume Permission Management** | Chạy pod dưới quyền root hoặc thêm `initContainer` chown phức tạp | Kubernetes `securityContext.fsGroup: 10001` | Kubernetes tự động đệ quy gán group ownership của mounted volume cho GID 10001 khi pod khởi động. |
| **Process Signal Handling** | Tự override `signal.signal(SIGTERM, ...)` trong Python code | PTB built-in lifecycle hook `ApplicationBuilder.post_shutdown` | PTB đã xử lý chuẩn luồng nhận tín hiệu, dừng polling, hủy các tasks dở dang rồi mới kích hoạt `post_shutdown`. Tránh xung đột signal handler với asyncio event loop. |

## Common Pitfalls

### Pitfall 1: Multi-Pod Concurrent Writes on SQLite WAL
**What goes wrong:** Database xuất hiện lỗi `database is locked` (`SQLITE_BUSY`) hoặc file `-shm` bị corrupt khi cập nhật phiên bản ứng dụng trên Kubernetes.
**Why it happens:** Khi deploy phiên bản mới bằng chiến lược mặc định `RollingUpdate`, K8s tạo Pod v2 trước khi huỷ Pod v1. Nếu Volume cho phép đa kết nối hoặc cluster mount volume cùng lúc, cả 2 pods cùng chạy bot polling và ghi vào cùng 1 file DB.
**How to avoid:** Trong file `k8s/all-in-one.yaml`, thiết lập rõ ràng:
```yaml
spec:
  replicas: 1
  strategy:
    type: Recreate
```
Chiến lược `Recreate` bảo đảm Pod cũ bị terminate hoàn toàn và giải phóng volume lock trước khi Pod mới được tạo.
**Warning signs:** Log Kubernetes xuất hiện 2 pod cùng lúc có trạng thái `Running` / `Terminating`, kèm log lỗi `aiosqlite.OperationalError: database is locked`.

### Pitfall 2: Telegram Duplicate Polling Conflicts (HTTP 409 Conflict)
**What goes wrong:** Bot liên tục log lỗi `telegram.error.Conflict: Terminated by other getUpdates request; make sure that only one bot instance is running`.
**Why it happens:** Hai instance container cùng mang một `TELEGRAM_BOT_TOKEN` chạy song song (do replica > 1 hoặc container cũ chưa dừng hẳn trước khi container mới polling).
**How to avoid:**
1. Kubernetes: Enforce `replicas: 1` và `strategy.type: Recreate`.
2. Docker Compose: Đặt tên container cố định `container_name: cassette-store-bot`.
3. Kiểm tra token duy nhất cho môi trường triển khai.
**Warning signs:** Lỗi HTTP 409 Conflict xuất hiện ngay khi bot khởi động.

### Pitfall 3: Volume Permissions Mismatch (Permission Denied on /app/data)
**What goes wrong:** Container crash với lỗi `PermissionError: [Errno 13] Permission denied: '/app/data/cassette_store.db'`.
**Why it happens:** Khi mount volume từ host (Docker) hoặc PersistentVolume (K8s), thư mục mount mặc định thuộc sở hữu của `root:root` (UID 0). Do container chạy dưới quyền `appuser` (UID 10001), tiến trình không có quyền ghi.
**How to avoid:**
- Dockerfile: `mkdir -p /app/data && chown -R appuser:appgroup /app/data`.
- Kubernetes: Cấu hình `podSecurityContext`:
  ```yaml
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
  ```
  `fsGroup: 10001` ra lệnh cho K8s kubelet tự động chown thư mục mounted volume sang GID 10001.
**Warning signs:** Crash ngay tại bước `init_database` lúc khởi động bot.

### Pitfall 4: Liveness Probe Killing Bot During Heavy LLM Extraction
**What goes wrong:** Pod bị Kubernetes tự động restart liên tục khi đang xử lý tin nhắn tạo đơn có danh sách dài.
**Why it happens:** `livenessProbe` đặt timeout hoặc failure threshold quá ngắn trong khi Python event loop bị chiếm dụng hoặc probe DB ping bị block.
**How to avoid:**
- Probe heartbeat file do JobQueue cập nhật nền độc lập với handler chat.
- Đặt ngưỡng chịu lỗi an toàn: `initialDelaySeconds: 15`, `periodSeconds: 30`, `failureThreshold: 3` (tổng thời gian chịu đựng 90s trước khi kill).
- Script probe kiểm tra timeout kết nối DB với giới hạn 2 giây.
**Warning signs:** Kubernetes events báo `Liveness probe failed: ... Container cassette-store-bot failed liveness probe, will be restarted`.

## Code Examples

### 1. Zero-Dependency Healthcheck Script (`src/scripts/healthcheck.py`)
```python
"""Container healthcheck probe script using only Python standard library.

Checks:
1. Heartbeat file existence and freshness (< 90 seconds).
2. SQLite database connectivity ping (SELECT 1 with 2s timeout).
Exit 0 if healthy, exit 1 if unhealthy.
"""

import os
import sqlite3
import sys
import time

HEARTBEAT_FILE = "/tmp/bot_heartbeat"
MAX_HEARTBEAT_AGE = 90  # seconds (JobQueue writes every 30s)
DB_PING_TIMEOUT = 2.0   # seconds


def check_heartbeat() -> bool:
    """Verify heartbeat file exists and has been modified recently."""
    if not os.path.exists(HEARTBEAT_FILE):
        sys.stderr.write(f"Healthcheck FAIL: Heartbeat file {HEARTBEAT_FILE} does not exist\n")
        return False

    try:
        mtime = os.path.getmtime(HEARTBEAT_FILE)
        age = time.time() - mtime
        if age > MAX_HEARTBEAT_AGE:
            sys.stderr.write(f"Healthcheck FAIL: Heartbeat stale ({age:.1f}s > {MAX_HEARTBEAT_AGE}s)\n")
            return False
    except OSError as e:
        sys.stderr.write(f"Healthcheck FAIL: Error reading heartbeat file: {e}\n")
        return False

    return True


def check_database() -> bool:
    """Verify SQLite database responds to a simple query."""
    db_path = os.environ.get("SQLITE_DB_PATH", "/app/data/cassette_store.db")
    if not os.path.exists(db_path):
        # Initial boot before table creation - pass if heartbeat is healthy
        return True

    try:
        conn = sqlite3.connect(db_path, timeout=DB_PING_TIMEOUT)
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        res = cursor.fetchone()
        conn.close()
        if not res or res[0] != 1:
            sys.stderr.write("Healthcheck FAIL: Unexpected result from DB ping\n")
            return False
    except Exception as e:
        sys.stderr.write(f"Healthcheck FAIL: Database ping failed: {e}\n")
        return False

    return True


def main() -> None:
    if not check_heartbeat():
        sys.exit(1)
    if not check_database():
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### 2. PTB Heartbeat Background Job & Post Shutdown Hook (`src/bot/app.py`)
```python
# Job callback in src/bot/app.py
HEARTBEAT_PATH = "/tmp/bot_heartbeat"
JOB_HEARTBEAT_NAME = "bot_liveness_heartbeat"

async def heartbeat_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job updating heartbeat timestamp file for container healthcheck."""
    try:
        now_ts = str(time.time())
        # Atomic write / touch
        with open(HEARTBEAT_PATH, "w", encoding="utf-8") as f:
            f.write(now_ts)
    except Exception as e:
        logger.warning("Failed to update heartbeat file: %s", e)


async def post_shutdown_callback(app: Application) -> None:
    """Graceful shutdown hook: execute WAL checkpoint and flush SQLite journals."""
    logger.info("Bot shutting down. Initiating clean SQLite WAL checkpoint...")
    settings = app.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db")

    start_t = time.perf_counter()
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            res = await cursor.fetchall()
            dur = (time.perf_counter() - start_t) * 1000
            logger.info("WAL checkpoint TRUNCATE completed in %.2fms, result: %s", dur, res)
    except Exception as e:
        logger.error("Failed executing WAL checkpoint during shutdown: %s", e)
    finally:
        logger.info("Shutdown sequence finished cleanly.")
```

### 3. Production `docker-compose.yml`
```yaml
services:
  cassette-bot:
    build:
      context: .
      dockerfile: Dockerfile
    image: cassette-store-bot:latest
    container_name: cassette-store-bot
    restart: unless-stopped
    stop_grace_period: 30s
    environment:
      - TZ=Asia/Ho_Chi_Minh
      - SQLITE_DB_PATH=/app/data/cassette_store.db
    env_file:
      - .env
    volumes:
      - cassette_data:/app/data
      # To inspect DB directly on host, comment out named volume and use:
      # - ./data:/app/data
    healthcheck:
      test: ["CMD", "python", "-m", "src.scripts.healthcheck"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

volumes:
  cassette_data:
    name: cassette_store_data
```

### 4. GitHub Actions CI/CD (`.github/workflows/docker-publish.yml`)
```yaml
name: Docker Image CI/CD

on:
  push:
    branches: [ "main" ]
    tags: [ "v*" ]
  workflow_dispatch:

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract metadata (tags, labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.DOCKERHUB_USERNAME }}/cassette-store-bot
          tags: |
            type=raw,value=latest,enable={{is_default_branch}}
            type=ref,event=branch
            type=ref,event=tag
            type=sha,format=short

      - name: Build and push multi-arch image
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 5. All-in-One Kubernetes Manifest (`k8s/all-in-one.yaml`)
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: cassette-store
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: bot-config
  namespace: cassette-store
data:
  TZ: "Asia/Ho_Chi_Minh"
  SQLITE_DB_PATH: "/app/data/cassette_store.db"
  NINE_ROUTER_BASE_URL: "https://api.9router.com/v1"
  NINE_ROUTER_MODEL_ID: "gpt-4o-mini"
---
apiVersion: v1
kind: Secret
metadata:
  name: bot-secret
  namespace: cassette-store
type: Opaque
stringData:
  TELEGRAM_BOT_TOKEN: "YOUR_TELEGRAM_BOT_TOKEN"
  NINE_ROUTER_API_KEY: "YOUR_9ROUTER_KEY"
  TELEGRAM_WHITELIST_USER_IDS: "123456789,987654321"
  TELEGRAM_SUPER_ADMIN_ID: "123456789"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: bot-data-pvc
  namespace: cassette-store
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cassette-store-bot
  namespace: cassette-store
  labels:
    app: cassette-store-bot
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: cassette-store-bot
  template:
    metadata:
      labels:
        app: cassette-store-bot
    spec:
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
      containers:
        - name: bot
          image: cassette-store-bot:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: bot-config
            - secretRef:
                name: bot-secret
          volumeMounts:
            - name: data-volume
              mountPath: /app/data
          livenessProbe:
            exec:
              command:
                - python
                - -m
                - src.scripts.healthcheck
            initialDelaySeconds: 15
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            exec:
              command:
                - python
                - -m
                - src.scripts.healthcheck
            initialDelaySeconds: 5
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 2
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
      volumes:
        - name: data-volume
          persistentVolumeClaim:
            claimName: bot-data-pvc
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Chạy bot thủ công bằng `python main.py` trên VPS/screen/tmux | Container hóa chuẩn OCI Docker với multi-stage build | Phase 8 (2026-10) | Cách ly hoàn toàn môi trường, bảo đảm tính nhất quán runtime giữa dev/prod, không phụ thuộc phiên bản Python hệ điều hành host. |
| Hardcode token/secret vào file `.env` nằm trong image | Quản lý Secret qua Kubernetes Secret / Compose env injection | Phase 8 (2026-10) | Chống rò rỉ token Telegram và API key khi push image lên Docker Hub. Image public an toàn tuyệt đối. |
| Docker container chạy mặc định dưới quyền `root` | Phân quyền `appuser` (UID 10001) + `securityContext.fsGroup` | Phase 8 (2026-10) | Tuân thủ tiêu chuẩn bảo mật ASVS / container hardening (chống container breakout). |
| Shutdown đột ngột (`kill -9` / unhandled SIGTERM) | Bắt SIGTERM qua PTB `post_shutdown` + `PRAGMA wal_checkpoint(TRUNCATE)` | Phase 8 (2026-10) | Dọn dẹp sạch sẽ WAL journal trước khi pod biến mất, chống phân mảnh và nguy cơ hỏng cơ sở dữ liệu SQLite. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Người dùng có tài khoản Docker Hub và cấu hình secrets `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` trên GitHub repository. | GitHub Actions CI/CD | Workflow CI/CD trên GitHub Actions sẽ fail ở bước login Docker Hub nếu secrets chưa được cấu hình. (Người dùng có thể nhập secret hoặc chạy local compose). |
| A2 | Kubernetes cluster mục tiêu có sẵn default StorageClass hỗ trợ chế độ ReadWriteOnce (RWO). | All-in-One Kubernetes Manifest | PVC có thể ở trạng thái `Pending` nếu cluster không có default StorageClass. (Khắc phục đơn giản bằng việc bổ sung `storageClassName: <tên_storage_class>` nếu cần). |

## Open Questions

1. **Tên repository Docker Hub của người dùng:**
   - *What we know:* Workflow GitHub Actions cần tên namespace/image để push (ví dụ: `quan/cassette-store-bot`).
   - *What's unclear:* Tên username chính xác của user trên Docker Hub.
   - *Recommendation:* Trong workflow mẫu, dùng biến dynamic `${{ secrets.DOCKERHUB_USERNAME }}/cassette-store-bot` để tự động ăn khớp với bất kỳ tài khoản Docker Hub nào mà người dùng nhập vào GitHub Secrets.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| **Docker Engine** | Local image build & testing | ✓ | 24.0.2 | GitHub Actions runner có sẵn Docker mới nhất |
| **kubectl** | Kubernetes manifest validation & deploy | ✓ | Client v1.27.2 | — |
| **Python** | Local script & test execution | ✓ | 3.13.7 (Host) / 3.12 (Container) | — |
| **pytest** | Automated test suite execution | ✓ | 9.1.1 (trong `.venv/bin/pytest`) | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (`.venv/bin/pytest`) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/pytest tests/test_backup_engine.py -x` |
| Full suite command | `.venv/bin/pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **DEP-01** | Dockerfile tồn tại, có multi-stage builder, non-root user 10001, TZ VN, và .dockerignore đầy đủ | Unit / Static Spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_dockerfile_and_dockerignore -x` | ❌ Wave 0 |
| **DEP-02** | Volume mount cấu trúc `/app/data`, đường dẫn DB và backups trỏ đúng thư mục | Unit / Spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_volume_layout_spec -x` | ❌ Wave 0 |
| **DEP-03** | `docker-compose.yml` hợp lệ, cấu hình đúng healthcheck, restart, stop_grace_period 30s và named volume | Unit / Spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_docker_compose_config -x` | ❌ Wave 0 |
| **DEP-04** | Manifest `k8s/all-in-one.yaml` chứa đủ ConfigMap, Secret, PVC 2Gi RWO, Deployment replicas=1, strategy=Recreate, exec probes | Unit / Spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_k8s_manifest_specs -x` | ❌ Wave 0 |
| **DEP-05** | Script `src/scripts/healthcheck.py` pass/fail đúng điều kiện; `post_shutdown` hook thực thi `PRAGMA wal_checkpoint(TRUNCATE)` thành công | Integration / Mock | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_healthcheck_script_and_graceful_shutdown -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_deployment_artifacts.py -x`
- **Per wave merge:** `.venv/bin/pytest` (toàn bộ 160+ unit & integration tests)
- **Phase gate:** Full suite green trước khi đóng phase.

### Wave 0 Gaps
- [ ] `tests/test_deployment_artifacts.py` — kiểm tra tính hợp lệ của Dockerfile, docker-compose.yml, k8s/all-in-one.yaml, script healthcheck và shutdown logic.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| **V1 Architecture & Threat Modeling** | Yes | Enforce single-replica constraint (`replicas: 1`, `strategy.type: Recreate`) để bảo đảm data integrity cho SQLite. |
| **V4 Access Control** | Yes | Container chạy hoàn toàn dưới user non-root (`UID 10001`), pod áp đặt `runAsNonRoot: true`. |
| **V14 Configuration** | Yes | Tách biệt hoàn toàn config (`ConfigMap`) và secret (`Secret`). Không commit file `.env` hoặc token Telegram vào Docker image hay git repo (`.dockerignore`). |

### Known Threat Patterns for Containerized Telegram Bot

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Container breakout to host | Elevation of Privilege | Chạy non-root UID 10001, drop capabilities, `readOnlyRootFilesystem` hoặc hạn chế quyền ghi chỉ trong `/app/data` và `/tmp`. |
| Token leak in public Docker registry | Information Disclosure | Secrets truyền qua environment injection tại thời điểm runtime (`envFrom` K8s Secret hoặc Docker Compose `env_file`), tuyệt đối không `COPY .env` trong Dockerfile. |
| Denial of Service by frozen event loop | Denial of Service | Exec liveness probe giám sát file heartbeat mỗi 30s; tự động restart container nếu bot bị treo quá 90s. |
| SQLite data corruption due to dual writers | Tampering | RWO volume access mode, `replicas: 1` và `strategy.type: Recreate`. |

## Sources

### Primary (HIGH confidence)
- [Official python-telegram-bot docs] - `ApplicationBuilder.post_shutdown` coroutine hook lifecycle.
- [Official SQLite docs] - `PRAGMA wal_checkpoint(TRUNCATE)` behavior and return columns.
- [Kubernetes official documentation] - Deployment spec (`strategy: { type: Recreate }`), `podSecurityContext` (`fsGroup`), `exec` liveness/readiness probes.
- [Docker official documentation] - Multi-stage build patterns, non-root users, Docker Compose spec.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Các công cụ Docker, K8s, GitHub Actions và SQLite WAL đã được kiểm chứng chuẩn xác trong môi trường thực tế.
- Architecture: HIGH - Mô hình single-replica Recreate kết hợp heartbeat exec probe giải quyết triệt để đặc tính SQLite daemon.
- Pitfalls: HIGH - Xác định rõ ràng các rủi ro xung đột lock SQLite, HTTP 409 conflict và permission denied non-root.

**Research date:** 2026-10-27  
**Valid until:** 2026-12-31

