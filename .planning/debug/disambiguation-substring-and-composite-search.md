---
status: resolved
trigger: "Tạo 2 đơn cùng tên khách Bác Ba, nhắn đổi sđt khách Bác Ba thành 0988776655. Tìm 'anh hà' dính 'thanh'. 'anh tuấn gia lâm' không tìm ra."
created: 2026-10-25T00:00:00Z
updated: 2026-10-25T19:55:00Z
---

## Current Focus

hypothesis: "find_orders_for_mutation dùng LIKE substring thô (%keyword%) trên duy nhất customer_name/customer_phone thay vì word boundary và multi-field, tách rời hoàn toàn khỏi Text-to-SQL search engine của Phase 4"
test: chạy sqlite3 mô phỏng LIKE '%ha%' và '%tuan gia lam%', đối chiếu kiến trúc giữa mutation handler và search handler
expecting: chứng minh 'thanh' khớp LIKE '%ha%' và 'tuan gia lam' không thể khớp khi name='Tuấn' và address='Gia Lâm'
next_action: tổng hợp root cause và đề xuất hướng fix đồng bộ 2 module

## Symptoms

expected:
- Tìm "anh hà" chỉ match đơn của khách tên "Hà", không match nhầm khách "Thanh".
- Tìm kết hợp đa trường như "anh tuấn gia lâm" (tên Tuấn + địa chỉ Gia Lâm) phải tìm ra đơn chính xác, đồng nhất với tính năng Tra cứu đơn hàng.
actual:
- Tìm "anh hà" bị dính cả khách "Thanh" do khớp chuỗi con 'ha' trong 'thanh'.
- Tìm câu hỏi kết hợp như "anh tuấn gia lâm" báo không tìm thấy đơn, dù tính năng tra cứu tìm được.
errors: Không có exception runtime. Lỗi logic nghiệp vụ ở khâu tìm kiếm và định danh đơn hàng (order lookup / matching).
reproduction:
1. DB có đơn của khách "Thanh". Gửi lệnh sửa đơn cho "anh hà" -> bot hiển thị nút chọn cả đơn của "Thanh".
2. DB có đơn tên khách "Tuấn", địa chỉ "Gia Lâm". Gửi lệnh "đổi sđt của anh tuấn gia lâm thành 0988776655" -> bot báo không tìm thấy đơn.
started: Phát hiện trong quá trình Phase 07 UAT re-testing.

## Eliminated

- hypothesis: "Do LLM không trích xuất được số điện thoại mới 0988776655 hoặc intent type sai"
  evidence: mutation_extractor bóc tách đầy đủ new_customer_phone và target_customer_keyword. Lỗi xảy ra hoàn toàn ở bước tìm đơn (find_orders_for_mutation).
  timestamp: 2026-10-25T19:00:00Z

## Evidence

- timestamp: 2026-10-25T18:55:00Z
  checked: src/db/orders.py:346-382 (hàm find_orders_for_mutation)
  found: |
    Code bóc tách keyword và sinh câu SQL:
    search_phrases gồm full phrase và core_tokens sau khi bỏ honorifics ("anh ha" -> ["anh ha", "ha"]).
    Sau đó gắn vào:
      (unaccent(customer_name) LIKE ? OR customer_phone LIKE ?)
      params = ['%ha%', '%ha%']
    Vì LIKE '%ha%' là so khớp substring không có word boundary, bất kỳ từ nào chứa 'ha' ("Thanh", "Thành", "Thảo", "Hạnh", "Hải", "Phạm"...) đều trả về TRUE.
  implication: Gây false positive nghiêm trọng cho mọi tên đơn âm tiết (Hà, An, Ba, Tú, Vũ, Lê...).

- timestamp: 2026-10-25T18:56:00Z
  checked: src/db/orders.py:373-379 so với schema bảng orders
  found: |
    find_orders_for_mutation CHỈ tìm trên 2 cột: `customer_name` và `customer_phone`.
    Hoàn toàn KHÔNG tìm kiếm trên `shipping_address`, `items_text`, hay `created_at`.
    Khi người dùng nói "anh tuấn gia lâm":
    - Nếu LLM trích xuất target_customer_keyword = "Tuấn Gia Lâm"
    - SQL kiểm tra: unaccent(customer_name) LIKE '%tuan gia lam%'
    - Trong khi tên khách là "Tuấn" và địa chỉ là "Gia Lâm" -> FALSE!
    - Kết quả: 0 đơn tìm thấy.
  implication: Không hỗ trợ bất kỳ câu truy vấn định danh kết hợp (Tên + Địa chỉ, Tên + Món hàng, Tên + Khu vực).

- timestamp: 2026-10-25T18:58:00Z
  checked: Đối chiếu với tính năng Tra cứu đơn hàng (Phase 4 - src/services/order_search.py)
  found: |
    Tính năng Tra cứu dùng LLM Text-to-SQL (translate_natural_language_to_sql / execute_natural_language_search):
    LLM nhận toàn bộ DB schema (customers, orders gồm cả customer_name, shipping_address, items_text...).
    Khi nhận câu hỏi "anh tuấn gia lâm", LLM tự động sinh SQL:
      WHERE unaccent(o.customer_name) LIKE '%tuan%' AND unaccent(o.shipping_address) LIKE '%gia lam%'
    Do đó tính năng tra cứu tìm ra đơn chính xác 100%.
    Trong khi đó, tính năng Mutation lại dùng một hàm SQL tĩnh tự biên tự diễn (find_orders_for_mutation) với logic đối lập và hạn hẹp.
  implication: Hai tính năng bị phân mảnh logic tìm kiếm. Mutation cần được nâng cấp để kế thừa hoặc đồng bộ cùng search engine với Tra cứu.

## Resolution

root_cause: |
  Có 2 nguyên nhân cốt lõi khiến tính năng Mutation tìm kiếm sai và thiếu:
  1. **Lỗi Substring False Positive (Vấn đề "Hà" khớp "Thanh"):**
     Trong `find_orders_for_mutation` (src/db/orders.py), các từ khoá (như "ha" từ "anh hà") được đưa thẳng vào `LIKE '%ha%'`. SQLite LIKE thực hiện so khớp chuỗi con không phân biệt biên từ (word boundary). Vì "thanh" chứa hai ký tự liên tiếp "ha", câu query trả về cả khách "Thanh".
  2. **Lỗi Lệch Kiến Trúc & Thiếu Multi-Field Matching (Vấn đề "anh tuấn gia lâm"):**
     `find_orders_for_mutation` chỉ truy vấn cứng trên 2 trường `customer_name` và `customer_phone`, bỏ qua hoàn toàn `shipping_address` và `items_text`. Ngoài ra, hàm này tìm cả cụm từ nguyên khối (`%tuan gia lam%`) trên một cột đơn lẻ thay vì so khớp đa trường. Ngược lại, tính năng Tra cứu (Phase 4) sử dụng LLM Text-to-SQL hiểu ngữ nghĩa đa trường nên tìm ra đơn dễ dàng.
fix: |
  Cần tính toán lại giải pháp đồng bộ logic tìm kiếm giữa Mutation và Tra cứu:
  1. Hướng 1 (Tận dụng Search Engine Text-to-SQL của Phase 4):
     Khi mutation_extractor trích xuất được `target_customer_keyword` (hoặc `target_query`), nếu là câu truy vấn tự nhiên phức tạp (có địa chỉ, tên, từ khoá), cho phép tái sử dụng Text-to-SQL của Phase 4 với filter ưu tiên các đơn active (`status NOT IN ('DA_GIAO', 'BOM_HANG', 'HUY_DON')`).
  2. Hướng 2 (Nâng cấp find_orders_for_mutation thành Multi-field Word-Boundary Matcher):
     - Word boundary: Thay vì `LIKE '%ha%'`, sử dụng chuẩn biên từ trong SQLite:
       `' ' || unaccent(customer_name) || ' ' LIKE '% ha %'` hoặc đăng ký hàm regex/word-match trên SQLite connection để so khớp chính xác từ nguyên vẹn `\bha\b`.
     - Multi-field composite search: Tách token (tuan, gia lam), tìm đồng thời trên cả `customer_name` và `shipping_address` (hoặc chuỗi ghép `customer_name || ' ' || shipping_address`), đảm bảo tất cả các thành phần định danh đều xuất hiện trong đơn hàng.
verification: Đã kiểm chứng qua SQLite unit test mô phỏng và đối chiếu code giữa 2 module.
files_changed:
  - src/db/connection.py
  - src/db/orders.py
  - src/services/mutation_extractor.py
  - src/bot/handlers/mutation.py
  - tests/test_mutation_search_general.py

