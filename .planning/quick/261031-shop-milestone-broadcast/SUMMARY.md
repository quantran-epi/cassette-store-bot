---
status: complete
date: 2026-10-31
slug: shop-milestone-broadcast
description: Shop milestone celebration broadcast with fireworks effect and flexible admin configuration
---

# Quick Task Summary: Shop Milestone Celebration Broadcast

## Outcomes
1. **Schema & Models (`milestone_rules`, `milestone_logs`)**:
   - `period`: `week`, `month`, `year`, `all_time`.
   - `target_type`: `order_count`, `revenue`.
   - `target_value`: integer.
   - `only_delivered`: 1 (chỉ đơn `DA_GIAO`) | 0 (mọi đơn trừ `BOM_HANG`, `HUY_DON`).
   - `message_template`: lời chúc mừng kèm placeholder `{current_value}`, `{target_value}`, `{period_label}`.
   - `effect_enabled`: 1 (bật pháo hoa) | 0.
   - `is_active`: 1 | 0.
   - Deduplication qua `milestone_logs` với `UNIQUE(rule_id, period_key)`.

2. **Telegram Fireworks Effect**:
   - Tích hợp `message_effect_id = "5046509860389126442"` (Party Popper 🎉) trong `broadcast_to_whitelist`.
   - Tự động fallback nếu client/bot không hỗ trợ hiệu ứng.

3. **Admin UI (`/admin -> 🎯 Mốc chúc mừng`)**:
   - Xem danh sách mốc, trạng thái bật/tắt, tiến độ thực tế so với mục tiêu.
   - Wizard tạo mốc 4 bước trực quan: Chọn chu kỳ -> Chọn loại chỉ số -> Chọn điều kiện đơn -> Chọn/nhập số.
   - AI gợi ý mẫu lời chúc hào hứng, cho phép admin dùng ngay, nhờ AI đổi mẫu khác hoặc tự gõ lời chúc riêng.
   - Sửa lời chúc, bật/tắt pháo hoa, tạm dừng/kích hoạt, xoá mốc.

4. **Kích hoạt tự động (Hooks)**:
   - Khi tạo đơn mới: quét các mốc `only_delivered=0`.
   - Khi đơn đổi sang `DA_GIAO` (qua chi tiết đơn, sửa nhanh, hoặc bulk status): quét các mốc `only_delivered=1`.

5. **Verification**:
   - Toàn bộ 488 tests pass 100%. Lint ruff clean.
