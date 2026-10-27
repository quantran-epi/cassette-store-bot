---
phase: 261027-m8x
plan: 01
subsystem: order-mutation-and-ui
tags: [mutation, llm, static-edit, telegram, sqlite, order-actions]
requires:
  - src/bot/keyboards.py
  - src/bot/handlers/order_actions.py
  - src/services/mutation_extractor.py
  - src/bot/handlers/mutation.py
  - src/db/orders.py
provides:
  - Static order edit via inline keyboard buttons and action_state text prompts
  - LLM Text-to-SQL order identification isolating customer name from address noise
  - Context-aware mutation delta extraction with <current_order> preservation
affects:
  - Order mutation flow (chat and disambiguation)
  - Order detail card actions
tech-stack:
  added: []
  patterns: [2-phase LLM order mutation, action_state prompt editing, optimistic lock update]
key-files:
  created: []
  modified:
    - src/bot/keyboards.py
    - src/bot/handlers/order_actions.py
    - src/bot/app.py
    - src/services/mutation_extractor.py
    - src/bot/handlers/mutation.py
    - src/db/orders.py
    - tests/test_orders_ui.py
    - tests/test_mutation_extractor.py
    - tests/test_mutation_handler_flow.py
decisions:
  - Added [✏️ Sửa thông tin] menu on order detail card for direct static field editing without LLM
  - Separated NL mutation into Phase 1 (target order discovery via Text-to-SQL) and Phase 2 (delta extraction with <current_order> context)
  - During disambiguation, preserved original user text and extracted delta only after specific order was chosen, ensuring partial address patches keep existing administrative hierarchy
metrics:
  completed: 2026-10-27
---

# Quick Task 261027-m8x: LLM Mutation Flow Refactoring & Static Order Edit Summary

Implemented static field-by-field order editing from order detail cards, and refactored the natural language mutation pipeline into a two-phase architecture: Phase 1 isolates the candidate order using Text-to-SQL queries (preventing false matches like 'Hà' vs 'Hà Nội'), and Phase 2 extracts deltas with full `<current_order>` context so partial updates (e.g., street name replacement) preserve existing address details.

## Changes Completed

1. **Static Order Edit**:
   - `build_order_edit_menu_keyboard` in `src/bot/keyboards.py`.
   - `[✏️ Sửa thông tin]` button in `build_order_detail_keyboard`.
   - `handle_order_action_callback` and `handle_action_state_text` in `src/bot/handlers/order_actions.py` for field prompts and updates via `mutate_order_with_lock`.
   - Callback pattern registered in `src/bot/app.py`.

2. **2-Phase LLM Mutation Flow**:
   - `search_target_orders_for_mutation` in `src/services/mutation_extractor.py` using Text-to-SQL to find target orders based on old customer/order info while ignoring new values and prioritizing active lifecycle states.
   - Refactored `handle_mutation_flow` and `handle_mutation_selection` in `src/bot/handlers/mutation.py` to supply `<current_order>` to `extract_mutation_delta`.
   - Prioritized `customer_name` matches in `find_orders_for_mutation` in `src/db/orders.py`.

3. **Tests**:
   - Added static edit flow and validation tests to `tests/test_orders_ui.py`.
   - Added target order search and context extraction tests to `tests/test_mutation_extractor.py` and `tests/test_mutation_handler_flow.py`.
