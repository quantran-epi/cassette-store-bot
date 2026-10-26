# Phase 8: Containerization & Kubernetes Deployment - Context

**Gathered:** 2026-10-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Đóng gói ứng dụng Cassette Store Telegram Chatbot thành Docker container chuẩn hóa, cấu hình persistent volume cho SQLite WAL, thiết lập quy trình tự động build & push Docker Hub qua GitHub Actions, và tạo bộ manifest triển khai Kubernetes all-in-one (1 lệnh apply) kèm Docker Compose chuẩn production với cam kết single-replica an toàn.

</domain>

<decisions>
## Implementation Decisions

### 1. Healthcheck & Probes Strategy
- **D-01 (Cơ chế probe):** Dùng Heartbeat file (`/tmp/bot_heartbeat`) do PTB JobQueue cập nhật định kỳ + kiểm tra kết nối SQLite DB ping (`SELECT 1`). Không mở port mạng HTTP ra ngoài, an toàn tuyệt đối, phù hợp cả Docker container và K8s exec probe.
- **D-02 (Chu kỳ & Timeout):** JobQueue ghi heartbeat mỗi 30s. Probe script báo lỗi nếu file cũ hơn 90s hoặc DB ping timeout > 2s. K8s probe đặt `periodSeconds: 30`, `failureThreshold: 3` (tự khởi động lại pod sau ~1.5 phút nếu bị treo).
- **D-03 (Script triển khai):** Tạo file riêng `src/scripts/healthcheck.py` chỉ dùng Python stdlib (`os`, `time`, `sqlite3`, `sys`), không import thư viện ngoài nặng, chạy siêu nhẹ (<0.1s), trả về exit code 0 (healthy) hoặc 1 (unhealthy). Gọi qua lệnh: `python -m src.scripts.healthcheck`.
- **D-04 (K8s Probes):** Cấu hình cả `livenessProbe` và `readinessProbe` trong Deployment manifest gọi chung healthcheck script:
  - `readinessProbe`: `initialDelaySeconds: 5`, `periodSeconds: 15` để K8s đánh dấu Pod Ready nhanh.
  - `livenessProbe`: `initialDelaySeconds: 15`, `periodSeconds: 30`, `failureThreshold: 3` để tự động restart Pod khi treo.

### 2. Graceful Shutdown & WAL Checkpoint
- **D-05 (Bắt tín hiệu SIGTERM/SIGINT):** Dùng hook vòng đời chính quy của python-telegram-bot: `ApplicationBuilder.post_shutdown(callback)`. Khi container nhận SIGTERM hoặc SIGINT, PTB tự động dừng nhận update mới, hoàn tất các handler đang chạy dở dang và gọi `post_shutdown`.
- **D-06 (Chiến lược WAL Checkpoint):** Trong `post_shutdown`, thực thi `PRAGMA wal_checkpoint(TRUNCATE);` để gom toàn bộ dữ liệu từ file `-wal` vào file `.db` chính và cắt dung lượng file `-wal` về 0 bytes trước khi đóng kết nối SQLite sạch sẽ. Khớp đúng yêu cầu DEP-05.
- **D-07 (Grace Period Budget):** Cấu hình `terminationGracePeriodSeconds: 30` trong Kubernetes Deployment và `stop_grace_period: 30s` trong `docker-compose.yml`. Đảm bảo đủ thời gian cho các request LLM đang xử lý (2-10s) và lệnh checkpoint WAL (<1s) hoàn tất trước khi bị hệ điều hành gửi SIGKILL.
- **D-08 (Logging lúc tắt):** Ghi log có cấu trúc vào stdout (trạng thái checkpoint, số trang ghi, thời gian thực thi) với exit code 0. Không gửi tin nhắn Telegram lúc shutdown để tránh rủi ro treo do network bị ngắt trước.

### 3. Volume Layout & PVC Storage
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

### 4. Image Build, GitHub Actions & All-in-One K8s Deploy
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & Requirements Specifications
- `.planning/PROJECT.md` — Toàn bộ bối cảnh dự án, tech stack, constraints và key decisions.
- `.planning/REQUIREMENTS.md` §DEP — Yêu cầu kỹ thuật chi tiết của 5 requirements: DEP-01, DEP-02, DEP-03, DEP-04, DEP-05.
- `.planning/ROADMAP.md` §Phase 8 — Mục tiêu phase, tiêu chí thành công (Success Criteria) và danh sách requirements.

### Existing Codebase Patterns
- `src/config.py` — Khai báo Pydantic Settings, biến môi trường, whitelist parsing và DB path.
- `main.py` — Điểm khởi động bot, vòng đời `asyncio.run(init_database)` và `app.run_polling()`.
- `src/bot/app.py` — Cấu hình PTB `ApplicationBuilder`, `post_init`, `JobQueue`, đăng ký handlers.
- `src/services/backup.py` — Quy trình `execute_backup`, tạo file snapshot SQLite và đường dẫn lưu trữ.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/config.py`: Đã hỗ trợ cấu hình `sqlite_db_path` từ biến môi trường `SQLITE_DB_PATH`.
- `src/bot/app.py`: Đã có JobQueue nền (`daily_backup_job_callback`, `JOB_REMINDER_NAME`). Có thể dễ dàng thêm job cập nhật heartbeat file mỗi 30s.
- `src/db/connection.py`: Hàm `get_db_connection` đã cấu hình WAL mode và SQLite custom functions (`unaccent`, `word_match`, `tape_count`).

### Established Patterns
- Single-process async architecture: Bot chạy long-polling qua PTB v20+, không mở port HTTP.
- Strict security & Whitelist: Nhận Telegram IDs từ biến môi trường và đồng bộ vào bảng admin users.
- Database WAL persistence: SQLite chạy WAL mode yêu cầu đồng bộ checkpoint an toàn trước khi dừng process.

### Integration Points
- `src/bot/app.py`: Bổ sung `post_shutdown` hook vào `ApplicationBuilder` để chạy checkpoint WAL. Thêm background job ghi heartbeat vào `/tmp/bot_heartbeat`.
- `src/scripts/healthcheck.py`: Module mới kiểm tra heartbeat timestamp và ping DB.
- Dockerfile & `.dockerignore`: Tạo tại root dự án.
- `docker-compose.yml`: Tạo tại root dự án.
- `.github/workflows/docker-publish.yml`: CI/CD workflow tự động build & push Docker Hub.
- `k8s/all-in-one.yaml`: Bộ manifest Kubernetes tổng hợp 1 file.

</code_context>

<specifics>
## Specific Ideas

- Người dùng yêu cầu build hiệu quả nhất, push code lên GitHub tự động build & push lên Docker Hub, và tạo 1 file duy nhất cho Kubernetes để chỉ cần chạy `kubectl apply -f k8s/all-in-one.yaml`.
- K8s deployment bắt buộc cấu hình `strategy.type: Recreate` và `replicas: 1` để bảo vệ SQLite khỏi tình trạng multi-pod concurrent writes.

</specifics>

<deferred>
## Deferred Ideas

- None — Thảo luận tập trung 100% vào phạm vi Containerization & Kubernetes Deployment (Phase 8).

</deferred>

---

*Phase: 8-Containerization & Kubernetes Deployment*
*Context gathered: 2026-10-27*
