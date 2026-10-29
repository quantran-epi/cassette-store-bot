# Quick Task 261029-eaa: Xây dựng migration an toàn cho backup/blob Summary

Xây dựng module và script migration an toàn chuyển đổi dữ liệu legacy từ JSON blob (`backup/blob`) sang SQLite hiện tại.

## Thống kê thực thi

- **Customers**: 602 bản ghi (trích xuất từ payload.customer.customers).
- **Orders**: 792 bản ghi (trích xuất từ payload.order.orders).
- **Bỏ qua**: Toàn bộ codPayments, syncFailures, appContext, trelloCardId.
- **Idempotency**: Dựa trên số điện thoại khách hàng và mã vận đơn (tracking_code) / ngày tạo (created_at).
- **Transaction**: Gói trong transaction SQLite đơn (`BEGIN IMMEDIATE`), tự động `ROLLBACK` khi có bất kỳ ngoại lệ nào.
- **Dry-run**: Mặc định an toàn, chỉ chạy thật khi truyền cờ `--apply`.

## Files Changed

- `src/services/legacy_importer.py`: Core parser, mapper, remap ID logic, và `LegacyBlobImporter` engine.
- `scripts/import_legacy_blob.py`: CLI script hỗ trợ `--blob`, `--dry-run`, `--apply`, `--db`.
- `scripts/__init__.py`: Package marker cho CLI module execution.
- `tests/test_legacy_importer.py`: Bộ 7 test cases bao quát parser, field mapping, foreign key remap, dry-run, idempotency, rollback on failure, và preservation of existing new data.

## Verification

- `python -m pytest tests/test_legacy_importer.py -v`: 7/7 passed in 0.35s.
- `python -m pytest tests/test_db_orders.py tests/test_customer_classification_runtime.py -v`: 19/19 passed in 7.65s (zero regression).
- `python -m scripts.import_legacy_blob --blob D:/personal/cassette-store-bot/backup/blob --dry-run`: 602 customers simulated, 792 orders simulated, 0 errors.

## Self-Check: PASSED
- `src/services/legacy_importer.py` exists
- `scripts/import_legacy_blob.py` exists
- `tests/test_legacy_importer.py` exists
