# Phase 8: Containerization & Kubernetes Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-27
**Phase:** 8-containerization-kubernetes-deployment
**Areas discussed:** Healthcheck & Probes, Graceful Shutdown & WAL Checkpoint, Volume Layout & PVC Storage, Image Build & Docker Hub Workflow

---

## Healthcheck & Probes

| Option | Description | Selected |
|--------|-------------|----------|
| Heartbeat File + DB Probe | Bot ghi timestamp vào file /tmp/bot_heartbeat định kỳ và probe script test nhanh SELECT 1 DB. Không mở port mạng, an toàn tuyệt đối, phù hợp Docker exec và K8s exec probe. | ✓ |
| Internal HTTP Server (/healthz) | Mở endpoint HTTP nội bộ http://127.0.0.1:8080/healthz trong asyncio loop. K8s dùng httpGet probe chuẩn, Docker dùng python/curl. | |
| Process Only (pgrep) | Chỉ kiểm tra PID process python còn sống. Đơn giản nhất nhưng không phát hiện được treo loop hay kẹt lock SQLite. | |

**User's choice:** Heartbeat File + DB Probe (Recommended)
**Notes:** Giữ nguyên kiến trúc bot không mở port HTTP ra ngoài, an toàn tuyệt đối.

| Option | Description | Selected |
|--------|-------------|----------|
| 30s Update / 90s Stale | JobQueue cập nhật heartbeat mỗi 30s. Probe script báo lỗi nếu file cũ hơn 90s hoặc DB kẹt. K8s probe interval 30s, failureThreshold 3. | ✓ |
| 60s Update / 180s Stale | Cập nhật mỗi 60s, báo lỗi sau 180s (3 phút). Tiết kiệm I/O. | |
| 15s Update / 45s Stale | Cập nhật mỗi 15s, báo lỗi sau 45s. Quá nhạy cảm dễ restart nhầm. | |

**User's choice:** 30s Update / 90s Stale (Recommended)
**Notes:** Cân bằng giữa tốc độ phát hiện lỗi và độ trễ hợp lý.

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated Python Stdlib Script | File riêng src/scripts/healthcheck.py chỉ dùng Python stdlib (os, time, sqlite3), không import thư viện ngoài, chạy siêu nhẹ <0.1s. | ✓ |
| Shell + sqlite3 CLI | Lệnh shell bash/sh kết hợp sqlite3 CLI. Cần cài thêm package sqlite3 vào Docker image. | |
| main.py --check flag | Tích hợp cờ python main.py --check. Khởi động chậm hơn vì import toàn bộ telegram framework. | |

**User's choice:** Dedicated Python Stdlib Script (Recommended)
**Notes:** Tách riêng script stdlib để Docker HEALTHCHECK và K8s exec probe gọi siêu nhanh và nhẹ.

| Option | Description | Selected |
|--------|-------------|----------|
| Both Liveness & Readiness | Cả Liveness và Readiness đều gọi chung script healthcheck nhưng khác timing (readiness 5s, liveness 15s). | ✓ |
| Liveness Only | Chỉ cấu hình LivenessProbe vì bot Telegram chạy long-polling nhận tin nhắn, không có Ingress/Service. | |
| Differentiated Script Modes | Tách cờ riêng --ready và --live. | |

**User's choice:** Both Liveness & Readiness (Recommended)
**Notes:** Tuân thủ chuẩn K8s deployment pattern.

---

## Graceful Shutdown & WAL Checkpoint

| Option | Description | Selected |
|--------|-------------|----------|
| PTB post_shutdown Hook | Dùng post_shutdown hook chính quy của python-telegram-bot (ApplicationBuilder.post_shutdown). Chờ các handler đang chạy hoàn tất rồi gọi post_shutdown để checkpoint DB sạch sẽ. | ✓ |
| Custom signal.signal in main.py | Tự đăng ký signal.signal(SIGTERM, ...) trong main.py để bắt trước. Dễ xung đột với PTB loop. | |
| atexit Handler Wrapper | Dùng context manager async với atexit handler bọc toàn bộ tiến trình. | |

**User's choice:** PTB post_shutdown Hook (Recommended)
**Notes:** Chuẩn idiomatic PTB v20+.

| Option | Description | Selected |
|--------|-------------|----------|
| wal_checkpoint(TRUNCATE) | Thực thi PRAGMA wal_checkpoint(TRUNCATE) gom toàn bộ dữ liệu vào .db và cắt file -wal về 0 bytes. Đảm bảo an toàn tuyệt đối khi pod di chuyển. | ✓ |
| wal_checkpoint(FULL) | Chỉ gọi PRAGMA wal_checkpoint(FULL), không cắt ngắn file -wal. | |
| Default db.close() only | Chỉ đóng kết nối thông thường để SQLite tự xử lý checkpoint mặc định (PASSIVE). | |

**User's choice:** wal_checkpoint(TRUNCATE) (Recommended)
**Notes:** Khớp hoàn hảo yêu cầu DEP-05.

| Option | Description | Selected |
|--------|-------------|----------|
| 30 Seconds | terminationGracePeriodSeconds: 30 trên K8s và stop_grace_period: 30s trên docker-compose. Đủ thời gian cho in-flight LLM calls và WAL checkpoint. | ✓ |
| 60 Seconds | Cấu hình 60s. Dư dả thời gian kể cả khi đang có tác vụ backup. | |
| 10 Seconds | Mặc định Docker. Dễ ngắt đột ngột request LLM dài. | |

**User's choice:** 30 Seconds (Recommended)
**Notes:** Chuẩn production K8s timeout budget.

| Option | Description | Selected |
|--------|-------------|----------|
| Stdout Logging Only | Ghi log chi tiết (kết quả PRAGMA checkpoint, số trang ghi, thời gian) vào stdout. Không gửi tin nhắn Telegram lúc shutdown để tránh deadlock. | ✓ |
| Telegram Alert + Stdout | Gửi tin nhắn Telegram thông báo cho Super Admin trước khi thoát. | |
| Log File in Data Volume | Ghi log ra file riêng trong /app/data/shutdown.log. | |

**User's choice:** Stdout Logging Only (Recommended)
**Notes:** Đảm bảo thoát nhanh và an toàn, không phụ thuộc kết nối mạng bên ngoài lúc pod terminating.

---

## Volume Layout & PVC Storage

| Option | Description | Selected |
|--------|-------------|----------|
| Unified /app/data with /backups subfolder | DB đặt tại /app/data/cassette_store.db, backups đặt tại /app/data/backups/. Một volume mount duy nhất /app/data bảo toàn cả DB và snapshot backup. | ✓ |
| Subfolders /data/db and /data/backups | Tách riêng 2 thư mục con riêng biệt bên trong volume. | |
| DB Only in Volume | Chỉ lưu DB trong volume, backups lưu tạm /tmp và xóa sau khi gửi Telegram. | |

**User's choice:** Unified /app/data with /backups subfolder (Recommended)
**Notes:** Một volume duy nhất tối giản cấu hình PVC và docker-compose.

| Option | Description | Selected |
|--------|-------------|----------|
| securityContext fsGroup: 10001 | Dockerfile tạo appuser (UID/GID 10001). K8s Pod spec cấu hình securityContext: runAsNonRoot: true, runAsUser: 10001, runAsGroup: 10001, fsGroup: 10001. K8s tự động gán quyền ghi volume. | ✓ |
| Root initContainer for Chown | Dùng K8s initContainer chạy root để chown -R 10001:10001 /app/data. | |
| Root User in Container | Chạy container dưới quyền root. (Vi phạm DEP-01). | |

**User's choice:** securityContext fsGroup: 10001 (Recommended)
**Notes:** Best practice Kubernetes non-root container storage.

| Option | Description | Selected |
|--------|-------------|----------|
| 2Gi RWO with Default StorageClass | Dung lượng 2Gi, accessModes: ReadWriteOnce (RWO), dùng default StorageClass của cluster. | ✓ |
| 5Gi RWO with Default StorageClass | Dung lượng 5Gi RWO. | |
| 1Gi RWO Minimum | Dung lượng 1Gi RWO. | |

**User's choice:** 2Gi RWO with Default StorageClass (Recommended)
**Notes:** Đủ sức chứa dữ liệu nhiều năm cho shop bán băng cassette.

| Option | Description | Selected |
|--------|-------------|----------|
| Named Volume with Bind Mount Note | Dùng Docker named volume (cassette_data:/app/data) làm mặc định, kèm chú thích bind mount (./data:/app/data). | ✓ |
| Host Bind Mount Default | Dùng Host Bind Mount (./data:/app/data) làm mặc định. | |
| Anonymous Volume | Dùng volume tự sinh bởi Docker. | |

**User's choice:** Named Volume with Bind Mount Note (Recommended)
**Notes:** Tránh lỗi permission và I/O sync trên Docker Desktop.

---

## Image Build & Docker Hub Workflow

**User's direct requirement:**
- "build làm sao cho hiệu quả nhất, cần build và public image lên docker hub và cần gen 1 file đủ tất cả thông tin k8s để chỉ cần kubectl apply -f , hiểu không"
- "build kiểu gì tốt nhất là được, push code lên github tự build và đẩy docker hub"

**Decisions Captured:**
1. **Multi-stage Dockerfile tối ưu cache:** Tách layer dependencies (copy riêng `pyproject.toml` để pip install trước) và mã nguồn `src/` (copy sau). Nền `python:3.12-slim`, non-root user `appuser` (UID 10001), timezone `TZ=Asia/Ho_Chi_Minh`. `.dockerignore` loại bỏ triệt để file rác.
2. **GitHub Actions CI/CD đẩy Docker Hub:** Workflow `.github/workflows/docker-publish.yml` tự động chạy khi push code `main` hoặc tạo git tag. Dùng Docker Buildx build multi-arch (`linux/amd64`, `linux/arm64`) và push lên Docker Hub với tag `latest` và commit SHA.
3. **All-in-One K8s Manifest 1 lệnh:** File duy nhất `k8s/all-in-one.yaml` chứa đủ Namespace, ConfigMap, Secret, PVC (2Gi RWO) và Deployment (replicas: 1, strategy Recreate). Chỉ cần 1 lệnh: `kubectl apply -f k8s/all-in-one.yaml`.

---

## Claude's Discretion

- Tự động cấu hình Dockerfile compiler cờ và caching tối ưu.
- Đặt tên nhãn metadata tiêu chuẩn trong K8s manifest (`app: cassette-store-bot`).

## Deferred Ideas

None — Thảo luận tập trung 100% vào phạm vi Containerization & Kubernetes Deployment (Phase 8).
