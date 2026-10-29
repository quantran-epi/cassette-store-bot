# Quick Task 261029-eaa: Xây dựng migration an toàn cho backup/blob Summary

Xây dựng module và script migration an toàn chuyển đổi dữ liệu legacy từ JSON blob (`backup/blob`) sang SQLite hiện tại.

## Thống kê thực thi

- **Customers**: 602 bản ghi nguồn; dry-run trên DB hiện tại dự kiến tạo 601 và tái sử dụng 1 khách trùng số điện thoại.
- **Orders**: 792 bản ghi nguồn; dry-run dự kiến tạo đủ 792 đơn.
- **Bỏ qua**: Toàn bộ codPayments, syncFailures, appContext, trelloCardId.
- **Idempotency**: Customer tái sử dụng theo số điện thoại; order nhận marker `legacy_id` chính xác nên chạy lại không tạo trùng và không bỏ nhầm đơn mới trùng mã vận đơn.
- **Transaction**: Gói trong transaction SQLite đơn (`BEGIN IMMEDIATE`), tự động `ROLLBACK` khi có bất kỳ ngoại lệ nào; từ chối apply nếu connection đang có transaction.
- **Dry-run**: Mặc định an toàn, chỉ chạy thật khi truyền cờ `--apply`.

## Files Changed

- `src/services/legacy_importer.py`: Core parser, mapper, remap ID logic, và `LegacyBlobImporter` engine.
- `scripts/import_legacy_blob.py`: CLI script hỗ trợ `--blob`, `--dry-run`, `--apply`, `--db`.
- `scripts/__init__.py`: Package marker cho CLI module execution.
- `tests/test_legacy_importer.py`: Bộ 13 test bao quát parser validation, field mapping, embedded snapshot, mặt hàng rỗng, foreign key remap, dry-run, idempotency, transaction guard, rollback và bảo toàn dữ liệu mới.

## Verification

- `python -m pytest tests/test_legacy_importer.py -v`: 7/7 passed in 0.35s.
- `python -m pytest tests/test_db_orders.py tests/test_customer_classification_runtime.py -v`: 19/19 passed in 7.65s (zero regression).
- `python -m scripts.import_legacy_blob --blob D:/personal/cassette-store-bot/backup/blob --dry-run`: 602 customers simulated, 792 orders simulated, 0 errors.

## Self-Check: PASSED
- `src/services/legacy_importer.py` exists
- `scripts/import_legacy_blob.py` exists
- `tests/test_legacy_importer.py` exists
