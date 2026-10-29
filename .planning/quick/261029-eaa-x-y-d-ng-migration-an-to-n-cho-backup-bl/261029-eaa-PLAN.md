---
phase: quick-261029-eaa
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/services/legacy_importer.py
  - scripts/import_legacy_blob.py
  - tests/test_legacy_importer.py
autonomous: true
requirements: ["QUICK-261029-MIGRATE-LEGACY-BLOB"]
user_setup: []

must_haves:
  truths:
    - "Importer đọc file legacy JSON (backup/blob) bóc tách đúng customers và orders, bỏ qua COD, Trello và syncFailures"
    - "ID dạng chuỗi của legacy customer được remap chính xác sang INTEGER PRIMARY KEY của SQLite cho đơn hàng tương ứng"
    - "Importer idempotent: chạy lặp lại không sinh bản ghi trùng, đơn và khách đã có trong DB được giữ nguyên"
    - "Dữ liệu mới tạo trong SQLite không bị ghi đè hay mất mát khi chạy import"
    - "Toàn bộ thao tác ghi bọc trong SQLite transaction: có lỗi là rollback 100%, không để lại dữ liệu rác"
    - "Dry-run mode mô phỏng toàn bộ tiến trình, xuất thống kê số bản ghi tạo/tái sử dụng/bỏ qua mà không thay đổi DB"
  artifacts:
    - path: "src/services/legacy_importer.py"
      provides: "LegacyBlobImporter, ImportSummary, mapping and remap logic"
      contains: "class LegacyBlobImporter"
    - path: "scripts/import_legacy_blob.py"
      provides: "CLI runner cho migration với cờ --blob, --dry-run, --apply"
      contains: "def main"
    - path: "tests/test_legacy_importer.py"
      provides: "Unit & integration tests cho mapping, remap ID, idempotency, dry-run, rollback"
      min_lines: 100
  key_links:
    - from: "src/services/legacy_importer.py"
      to: "src/db/connection.py"
      via: "get_db_connection"
      pattern: "get_db_connection"
    - from: "src/services/legacy_importer.py"
      to: "src/services/tape_parser.py"
      via: "build_tape_columns"
      pattern: "build_tape_columns"
    - from: "scripts/import_legacy_blob.py"
      to: "src/services/legacy_importer.py"
      via: "LegacyBlobImporter.run"
      pattern: "LegacyBlobImporter"
---

<objective>
Xây dựng module và script migration an toàn chuyển đổi dữ liệu legacy từ JSON blob (`backup/blob`) sang SQLite hiện tại.

Mục đích: Khôi phục 602 khách hàng và 792 đơn hàng lịch sử từ hệ thống cũ vào cơ sở dữ liệu SQLite mới mà không làm xung đột ID, không làm hỏng dữ liệu mới, hỗ trợ chạy thử (dry-run) và tự động rollback khi gặp lỗi.
Đầu ra: Dịch vụ `src/services/legacy_importer.py`, script CLI `scripts/import_legacy_blob.py`, test suite `tests/test_legacy_importer.py`.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@src/db/schema.py
@src/db/connection.py
@src/models/order.py
@src/models/customer.py
@src/db/orders.py
@src/db/customers.py
@src/services/tape_parser.py

# Đặc thù dữ liệu legacy (backup/blob)
- Cấu trúc: `{"schemaVersion": 1, "payload": {"customer": {"customers": [...]}, "order": {"orders": [...]}, "codPayments": [...], "syncFailures": [...], "appContext": {...}}}`.
- Chỉ đọc `payload.customer.customers` và `payload.order.orders`. Bỏ qua toàn bộ `codPayments`, `syncFailures`, `appContext`, `trelloCardId`, `doneInTrello`.
- Customer ID cũ là string hash (vd `Hướng87unULTK7J`), DB mới dùng `INTEGER PRIMARY KEY AUTOINCREMENT`.
- Order ID cũ là string slug (vd `3. Hiếu-Hà NộicjRF8_7PV6`), liên kết qua `customerId` dạng chuỗi cũ.
- Status cũ: `Đã giao thành công` -> `DA_GIAO`, `Đã tạo đơn` -> `DA_TAO_DON`, `Đã chuyển hoàn` / `Chờ chuyển hoàn` -> `BOM_HANG`.
- Payment method: `Chuyển khoản trước` -> `CHUYEN_KHOAN`, `COD` -> `COD`.
- Ngày tạo cũ: `createdDate` (ISO format `2025-06-13T13:19:18.616Z`) phải được lưu vào cột `created_at` và `updated_at` của SQLite thay vì để mặc định `CURRENT_TIMESTAMP`.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Xây dựng bộ parser & mapper dữ liệu legacy sang domain models kèm remap ID và kiểm tra trùng lặp</name>
  <files>src/services/legacy_importer.py</files>
  <behavior>
    - Parse file JSON blob, chỉ bóc tách danh sách customers và orders từ payload; bỏ qua các nhánh COD, Trello, syncFailures, appContext.
    - Map trường Customer: `name` -> name, `mobile` -> phones list, `address` -> addresses list, lưu thông tin phụ (difficulty, area, VIP, blacklist, legacy_id) vào `notes`.
    - Map trường Order: `paymentAmount` -> total_amount, `codAmount` -> cod_amount, `shippingCode` -> tracking_code, `placedItems` -> items_text (dùng build_tape_columns trích xuất phôi/thể loại/số lượng băng), `createdDate` -> created_at.
    - Ánh xạ status tiếng Việt sang OrderStatus enum: 'Đã giao thành công' -> DA_GIAO, 'Đã tạo đơn' -> DA_TAO_DON, 'Đã chuyển hoàn'/'Chờ chuyển hoàn' -> BOM_HANG.
    - Duy trì bảng tra cứu ID trong bộ nhớ: `legacy_customer_id -> sqlite_customer_id`.
    - Chiến lược Idempotent: tra cứu customer theo số điện thoại đã chuẩn hoá; tra cứu order theo tracking_code hoặc (phone + created_at) để tránh duplicate khi chạy lại.
  </behavior>
  <action>
    Tạo file `src/services/legacy_importer.py`. Định nghĩa dataclass `ImportSummary` chứa các chỉ số: `customers_created`, `customers_reused`, `orders_created`, `orders_skipped`, `errors`.
    Viết các hàm helper thuần túy:
    - `parse_legacy_blob(blob_path_or_content: str | Path | dict) -> tuple[list[dict], list[dict]]`: trích xuất customers và orders thô.
    - `map_legacy_customer(raw_cust: dict) -> Customer`: chuyển đổi sang domain model `Customer`.
    - `map_legacy_order(raw_order: dict, customer_id_map: dict[str, int], customer_snapshot: Customer | None) -> dict`: chuyển đổi sang dict chuẩn bị INSERT vào bảng `orders` của SQLite kèm ngày `created_at` gốc và kết quả từ `build_tape_columns`.
    - Không chứa phụ thuộc vào Trello hay COD table. Giữ code đơn giản, không viết abstraction thừa.
  </action>
  <verify>
    <automated>pytest tests/test_legacy_importer.py -k "test_mapping or test_parser" -v</automated>
  </verify>
  <done>
    Các hàm mapping chuyển đổi chính xác dữ liệu từ sample legacy JSON sang format SQLite, xử lý chuẩn status, ngày tháng, và phone/address list.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Xây dựng Import Engine với SQLite transaction, chế độ Dry-Run và CLI runner</name>
  <files>src/services/legacy_importer.py, scripts/import_legacy_blob.py</files>
  <behavior>
    - Chế độ dry_run=True: duyệt qua toàn bộ dữ liệu, đối chiếu DB hiện có, tính toán số lượng sẽ thêm/bỏ qua, không commit bất kỳ thay đổi nào vào DB.
    - Chế độ dry_run=False: mở transaction SQLite duy nhất (`BEGIN IMMEDIATE`), ghi lần lượt customers và orders đã remap ID; nếu bất kỳ lỗi nào xảy ra trong quá trình, tự động `ROLLBACK` toàn bộ, DB giữ nguyên trạng thái trước khi chạy.
    - Bảo toàn dữ liệu mới: không xoá bảng, không update đè lên các đơn hàng mới đang có trong SQLite.
    - CLI runner hỗ trợ các đối số: `--blob <path>`, `--dry-run` (mặc định), `--apply` (thực thi thật).
  </behavior>
  <action>
    Trong `src/services/legacy_importer.py`, cài đặt class `LegacyBlobImporter`:
    - Phương thức `async def run(self, db: aiosqlite.Connection, dry_run: bool = True) -> ImportSummary`.
    - Tạo map phone -> existing customer_id từ DB để reuse customer có sẵn.
    - Tạo set tracking_codes và composite keys từ bảng `orders` hiện tại để skip các đơn đã import hoặc đã tồn tại.
    - Khi `dry_run=False`, bọc trong transaction bằng `try...except`: thực hiện các câu lệnh INSERT trực tiếp chỉ định rõ các cột (bao gồm `created_at`, `updated_at`, `tape_quantity`, `tapes_json`, `tape_genre_json`, `tape_artist_json`), sau đó `await db.commit()`. Khi lỗi bắt exception, gọi `await db.rollback()` và raise lại lỗi có ngữ cảnh.
    Tạo file `scripts/import_legacy_blob.py` dùng `argparse` và `asyncio.run` để gọi `LegacyBlobImporter`, in báo cáo định dạng bảng rõ ràng ra terminal.
  </action>
  <verify>
    <automated>pytest tests/test_legacy_importer.py -k "test_dry_run or test_transaction_rollback or test_idempotent" -v</automated>
  </verify>
  <done>
    Import engine chạy mượt mà trên database SQLite cả ở chế độ dry-run lẫn apply thật; rollback hoạt động an toàn khi gặp exception mô phỏng.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Viết bộ kiểm thử tự động toàn diện cho quá trình migration</name>
  <files>tests/test_legacy_importer.py</files>
  <behavior>
    - Kiểm tra mapping logic: chuyển đổi ngày ISO, status tiếng Việt, tách items_text và cấu trúc phôi.
    - Kiểm tra remap ID: order được gắn đúng customer_id integer mới sau khi customer được tạo.
    - Kiểm tra tính idempotent: chạy import 2 lần liên tiếp trên cùng DB, lần 2 có 0 customer mới và 0 order mới, không phát sinh trùng lặp.
    - Kiểm tra rollback: mô phỏng lỗi gián đoạn ở giữa quá trình import đơn hàng, kiểm tra DB không bị dính bất kỳ bản ghi rác nào.
    - Kiểm tra bảo vệ dữ liệu hiện có: DB đã có sẵn customer và order mới, chạy migration không làm thay đổi hay mất dữ liệu đã có.
    - Kiểm tra dry-run: chạy dry-run xong kiểm tra bảng customers và orders trong DB vẫn hoàn toàn không có thêm bản ghi nào.
  </behavior>
  <action>
    Tạo `tests/test_legacy_importer.py` dùng fixture `test_db` từ `conftest.py`.
    Viết các test case:
    1. `test_legacy_parser_extracts_only_customers_and_orders`: assert không chứa key codPayments, appContext.
    2. `test_mapping_customer_and_order_fields`: assert chuyển đổi đúng status DA_GIAO, BOM_HANG, DA_TAO_DON, phone, address list.
    3. `test_customer_id_remapping`: tạo mock blob 2 khách 3 đơn, assert foreign key `customer_id` trong orders trỏ đúng integer id của customers trong SQLite.
    4. `test_importer_dry_run_leaves_database_untouched`: chạy với dry_run=True, assert summary có số liệu nhưng DB count = 0.
    5. `test_importer_idempotency`: chạy apply 2 lần, assert lần 2 số lượng created = 0, reused/skipped = N.
    6. `test_transaction_rollback_on_failure`: inject failure khi insert order thứ 2, assert DB count sau exception vẫn bằng 0.
    7. `test_existing_new_data_preserved`: tạo trước customer và order ngày hôm nay, chạy import blob cũ, assert dữ liệu mới vẫn nguyên vẹn.
  </action>
  <verify>
    <automated>pytest tests/test_legacy_importer.py -v</automated>
  </verify>
  <done>
    Toàn bộ test suite trong `tests/test_legacy_importer.py` vượt qua 100% với thời gian chạy dưới 15 giây.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| File JSON legacy -> Memory parser | File blob đầu vào có thể bị hỏng cú pháp, thiếu trường hoặc sai kiểu dữ liệu |
| Importer service -> Live SQLite DB | Ghi hàng loạt bản ghi có thể làm hỏng index, gây deadlock hoặc mất dữ liệu hiện tại |
| CLI execution -> File system | Script chạy từ terminal có thể vô tình chạy chế độ apply khi chưa kiểm tra |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-261029-01 | Tampering | `parse_legacy_blob` | mitigate | Validate cấu trúc JSON trước khi duyệt; dùng `.get()` kèm giá trị mặc định cho mọi trường tùy chọn; bỏ qua các key không liên quan |
| T-261029-02 | Data Loss | `LegacyBlobImporter.run` | mitigate | Mặc định `dry_run=True`; khi apply, bọc toàn bộ trong single transaction `BEGIN IMMEDIATE` + `ROLLBACK` khi có bất kỳ ngoại lệ nào |
| T-261029-03 | Elevation / Corruption | `map_legacy_order` | mitigate | Sử dụng parameterized SQL queries (`?`) cho 100% câu lệnh INSERT/SELECT, không dùng string interpolation tránh SQL injection |
| T-261029-04 | Inconsistency | Remap ID logic | mitigate | Lưu map `legacy_id -> new_int_id` trong dictionary bộ nhớ, kiểm tra ràng buộc FOREIGN KEY trước khi insert đơn |
</threat_model>

<verification>
1. Chạy unit & integration test: `pytest tests/test_legacy_importer.py -v`
2. Chạy test toàn bộ hệ thống để bảo đảm không có regression: `pytest tests/test_db_orders.py tests/test_customer_classification_runtime.py -v`
3. Kiểm tra dry-run với file blob thực tế (nếu file tồn tại): `python -m scripts.import_legacy_blob --blob backup/blob --dry-run`
</verification>

<success_criteria>
- Kế hoạch migration được phân chia thành 3 task rõ ràng, tuân thủ nguyên tắc YAGNI, không thêm abstraction thừa.
- File plan mô tả chi tiết: chỉ nhập customers và orders, loại bỏ COD/Trello/syncFailures, bảo vệ dữ liệu mới, idempotent, remap ID string sang integer, rollback khi lỗi và dry-run mode.
</success_criteria>

<output>
Tạo `.planning/quick/261029-eaa-x-y-d-ng-migration-an-to-n-cho-backup-bl/261029-eaa-SUMMARY.md` sau khi hoàn thành thực thi
</output>
