---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: NL Mutation, Telegram Admin, Telegram Backup & Container Deployment
status: completed
last_updated: "2026-10-27T00:40:00.000Z"
last_activity: 2026-10-27 -- Completed Phase 8 Containerization & Kubernetes Deployment (all 3 plans complete)
progress:
  total_phases: 8
  completed_phases: 8
  total_plans: 19
  completed_plans: 19
  percent: 100
stopped_at: Completed Phase 8 execution
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-25)

**Core value:** Người lớn tuổi nhập tự do một đoạn tin nhắn đặt hàng bất kỳ qua Telegram, bot dùng LLM tự bóc tách chính xác thông tin (khách, hàng hoá, tiền COD, hình thức), hiển thị nút bấm xác nhận trực quan và lưu trữ an toàn vào DB mà không cần thao tác biểu mẫu phức tạp.
**Current focus:** Phase 08 — containerization-kubernetes-deployment (COMPLETED)

## Current Position

Phase: 08 (containerization-kubernetes-deployment) — COMPLETED
Plan: 3 of 3
Status: All 3 plans complete, verified with 321 passing tests
Last activity: 2026-10-29 -- Completed quick task 261029-eaa: migrate legacy JSON blob safely into SQLite

Progress: [██████████] 100% (Phase 08)

## Performance Metrics

**Velocity:**

- Total plans completed: 16
- Average duration: 4.8m
- Total execution time: ~27m

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation, Persistence & Security Whitelist | 3 | - | - |
| 2. LLM Ingestion & Interactive Confirmation | 2 | - | - |
| 3. Ergonomic Order Management & Low-Tech Actions | 3 | - | - |
| 4. Natural Language Order Search | 3 | - | - |
| 5. Role-Based Access Control & Telegram Admin Suite | 1 | 4m | 4m |
| 6. Telegram Database Backup Engine & Scheduled Tasks | 2 | 10m | 5m |
| 7. Natural Language Order Mutation Pipeline | 4 | 21m | 5.2m |
| 8. Containerization & Kubernetes Deployment | 0 | - | - |

**Recent Trend:**

- Milestone v1.0 complete: 4 phases, 11 plans, 110 automated tests passing
- Trend: Stable

| Phase 05 P02 | 6min | 3 tasks | 9 files |
| Phase 06 P01 | 4min | 2 tasks | 2 files |
| Phase 06 P02 | 6min | 3 tasks | 7 files |
| Phase 07 P01 | 4m | 3 tasks | 9 files |
| Phase 07 P02 | 6m | 3 tasks | 9 files |
| Phase 07 P03 | 6m | 2 tasks | 4 files |
| Phase 07 P04 | 5m | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 07 P04]: Custom SQLite function `word_match(haystack, needle)` registered via Python regex `\bneedle\b` prevents substring false positives (e.g. 'Hà' vs 'Thanh').
- [Phase 07 P04]: Multi-field composite search checks unaccented customer_name + customer_phone + shipping_address + items_text + notes with token-level AND logic.
- [Phase 07 P04]: Complex conversational queries falling through local token matching delegate to Phase 4 `execute_natural_language_search` prioritizing active orders.
- [Phase 06 P02]: PTB JobQueue schedules daily backup at target HH:MM Asia/Ho_Chi_Minh without immediate execution on boot
- [Phase 06 P02]: Dynamic rescheduling clears existing job by name and registers new schedule without bot restart
- [Phase 06 P02]: /backup and adm:bkp:trigger strictly enforce SUPER_ADMIN role with progress feedback and document dispatch
- [Phase 06 P02]: Model switcher starts with empty default list, dynamically appends probed models, and protects active model from deletion
- [Phase 06 P02]: Whitelist user display names can be edited interactively via 60s TTL prompt
- [Phase 06 P01]: Hot backup via VACUUM INTO ? guarantees zero lockups and clean WAL checkpoint snapshot

### Quick Tasks Completed

| Date | Task Slug | Description | Status |
|------|-----------|-------------|--------|
| 2026-10-25 | `order-notes-maintenance-notifications-reminders` | Order notes to orders table, Super Admin maintenance mode + broadcast, lifecycle event broadcasts, NL reminders system | Complete ✓ |
| 2026-10-25 | `261025-vo9-fix-reminder-weekday-parsing-and-enhance` | Fix reminder weekday parsing on Sundays and enhance high-contrast uppercase labels across all order cards | Complete ✓ |
| 2026-10-26 | `261026-e7m-ch-nh-lu-ng-tra-c-u-nl-h-tr-aggregate-c-` | Mixed aggregate + order-list NL search: full aggregates, stable DB pagination with "Xem thêm", read-only SQL hardening | Complete ✓ |
| 2026-10-26 | `261026-hnn-fix-photo-album-bug-on-order-creation-se` | Album nhiều ảnh lưu đủ ảnh (debounce nền), tra khách deterministic, `tape_count` cho câu hỏi số băng, prompt khung giờ/thứ, chặn summary "thiếu danh sách chi tiết" | Complete ✓ |
| 2026-10-26 | `261026-tpe-structured-tape-quantity-and-type` | 3 cột băng có cấu trúc (`tape_quantity`, `tapes_json`, `tape_genre_json`), bóc tách lúc tạo/sửa đơn, đơn cũ NULL, prompt đếm băng/khung giờ | Complete ✓ |
| 2026-10-26 | `261026-kt4-add-tape-artist-json-as-separate-structu` | Tách `tape_artist_json` khỏi thể loại; sửa lỗi tên ca sĩ lọt vào nhãn phôi; chặn filter NULL khớp mọi đơn; bắt buộc công bố đơn cũ thiếu dữ liệu | Complete ✓ |
| 2026-10-27 | `20261027-order-delete-and-shipping-helper` | Xoá đơn xác nhận 2 bước, trợ giúp tạo đơn vận chuyển copy 1 chạm, auto chuyển DA_TAO_DON khi nhập mã, chuẩn hoá địa chỉ LLM, chat sửa draft preview | Complete ✓ |
| 2026-10-27 | `261027-c2n-th-m-t-nh-n-ng-cho-ph-p-admin-g-i-file-b` | Super Admin gửi file backup `.sqlite3.gz`, bot validate + xem trước, xác nhận mới import, snapshot an toàn trước ghi đè, rollback khi lỗi | Complete ✓ |
| 2026-10-27 | `261027-e0b-th-m-tutorial-t-ng-b-c-trong-bot-cho-ng-` | Tutorial 6 trang cho người già qua `/help` và nút `❓ Trợ giúp`, nút Tiếp/Quay lại/Thử ngay, gộp text help về một nguồn | Complete ✓ |
| 2026-10-27 | `261027-fay-draft-order-context-and-typing` | Sửa đơn nháp gửi thẻ `<current_order>` cho LLM (câu mơ hồ hiểu đúng, items trả full list); `run_with_typing` giữ "đang nhập…" mỗi 4s cho tới khi có kết quả | Complete ✓ |
| 2026-10-27 | `261027-g5f-draft-reminder-routing` | Draft: giờ hẹn giao/gửi đi vào `new_reminder_at`/`new_reminder_note` thay vì đè ghi chú, `clear_reminder` xoá lịch nhắc, prompt có mốc thời gian VN | Complete ✓ |
| 2026-10-27 | `261027-h7d-th-m-quick-search-kh-ng-qua-llm-n-t-n-ch` | Nút `⏳ Đơn chờ làm` không qua LLM: list đơn theo trạng thái gom theo ngày tạo VN, 10 đơn/trang, chip lọc trạng thái ở đáy mọi list card, reply keyboard 3x2, tutorial trang 2 | Complete ✓ |
| 2026-10-27 | `261027-htn-fix-mixed-search-summary-claiming-no-mat` | Summary MIXED tự bịa "không bán \<X\> nào": truyền `matched_order_count` (số đơn khớp của câu list) vào prompt summarizer + luật cấm khẳng định vắng mặt, không đổi AGGREGATE-only | Complete ✓ |
| 2026-10-27 | `261027-jb2-refactor-nl-order-search-to-plan-json-wi` | Tra cứu NL dùng JSON plan có nhãn: tối đa 1 list + 3 aggregate, chạy đủ mọi ý, summary nhận envelope có purpose/results và list purpose/count, card có heading xác định | Complete ✓ |
| 2026-10-27 | `261027-m8x-llm-mutation-flow-and-static-edit` | Sửa đơn static qua menu nút bấm trên thẻ đơn; tách luồng mutation LLM 2 phase: tìm đơn bằng Text-to-SQL (không nhầm Hà Nội khi tìm chị Hà) + bóc delta có `<current_order>` giữ nguyên địa chỉ cũ | Complete ✓ |
| 2026-10-27 | `261027-sqh-fix-order-reminder-message-timestamp-and` | Tin nhắn nhắc việc thêm rõ `HẸN LÚC` + `GHI CHÚ LÚC` (đổi UTC sang VN); chuẩn hoá toàn bộ divider thành 14 ký tự (`DIVIDER`), chống vỡ dòng màn hình nhỏ | Complete ✓ |
| 2026-10-28 | `261028-l0t-th-m-ph-n-lo-i-kh-ch-h-ng-khi-hi-n-th-n-` | Separate frequency/spending highlights; DA_GIAO-only aggregates, batch list hydration; 92 focused tests passed; latest full suite has backup-restore failure | Feature verified; suite issue |
| 2026-10-28 | `261028-n4r-simplify-customer-spending-labels-and-re` | Spending line shows tier icon and actual amount only; replace one-purchase keycap with shopping bag; 76 focused tests passed, offline dispatcher observed | Complete; uncommitted |
| 2026-10-29 | `261029-eaa-x-y-d-ng-migration-an-to-n-cho-backup-bl` | Legacy JSON blob migration: customers/orders only, remap ID, idempotent marker, transaction rollback, dry-run CLI | Verified; apply chưa chạy |
| 2026-10-29 | `261029-qye-unify-natural-language-search-under-text` | Hợp nhất toàn bộ tra cứu về Text-to-SQL; sửa lỗi tìm tên có dấu cách/danh xưng; phân biệt rạch ròi trường tên vs địa chỉ; hỗ trợ combine đa chiều | Complete ✓ |
| 2026-10-30 | `261030-c9j-th-m-menu-ch-nh-s-a-n-v-i-tr-ng-th-i-m-t` | Thêm menu ✏️ Sửa đơn, chế độ mutation một lần 120 giây; giữ fast path tạo đơn và nháp; code 6ed081a; 134 focused tests và Ruff pass | Hoàn tất; test biên chưa commit |
| 2026-10-31 | `261031-f38-bulk-status-change-returning-customer-ic` | Icon khách quay lại `🔂` (≥2 đơn bất kỳ trạng thái); menu chính thêm `🔄 Đổi trạng thái` (bỏ `❓ Trợ giúp`); flow đổi trạng thái hàng loạt 3 bước (checkbox + dán mã VĐN + xem chi tiết riêng) | Complete ✓ |
| 2026-10-31 | `261031-order-detail-collapse-mode` | Chi tiết đơn thu gọn mặc định kèm nút mở rộng; bỏ chip lọc và nút nhập đơn ở chân list; gạch nối giữa các item; thêm ngày giờ tạo đơn; divider dạng bullet | Complete ✓ |
| 2026-10-31 | `261031-shop-milestone-broadcast` | Mốc chúc mừng broadcast tự động kèm pháo hoa Telegram; cấu hình tuần/tháng/năm/toàn bộ, số đơn/doanh thu, lọc đơn DA_GIAO hoặc mọi đơn; admin wizard & AI gợi ý lời chúc | Complete ✓ |
