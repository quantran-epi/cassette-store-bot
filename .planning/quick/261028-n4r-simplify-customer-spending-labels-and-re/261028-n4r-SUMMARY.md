---
phase: 261028-n4r
plan: 01
subsystem: telegram-customer-ui
tags: [telegram, formatter, customer-classification, pytest]
requires: []
provides:
  - Simplified spend classification line with tier icon and bold actual amount
  - Shopping-bag icon for exactly one completed purchase
affects: [order-cards, order-preview, customer-search, customer-profile]
tech-stack:
  added: []
  patterns: [shared HTML formatter, offline PTB dispatcher verification]
key-files:
  created: []
  modified:
    - src/bot/keyboards.py
    - tests/test_orders_ui.py
    - tests/test_ingest.py
    - tests/test_customer_search.py
    - tests/test_customer_classification_runtime.py
decisions:
  - Keep existing spend thresholds and icons while removing range labels and parentheses.
  - Keep frequency wording and completed-order counts unchanged; replace only one-purchase icon.
metrics:
  duration: 7m
  completed: 2026-10-28
---

# Quick Task 261028-n4r: Simplify Customer Spending Labels Summary

Shared customer formatter now emits tier icon plus bold `CHI TIÊU:` and bold dot-formatted amount, with `🛍️` for exactly one completed purchase.

## Changes

- Preserved spend thresholds/icons: `<1m` `🪙`, `1m-<3m` `🥉`, `3m-<10m` `🥈`, `>=10m` `🥇`.
- Removed spend tier-range wording and parenthesized amount.
- Replaced one-purchase `1️⃣` marker with `🛍️`; frequency text and count remain unchanged.
- Updated exact formatter, order card, preview, search, profile, and offline dispatcher assertions.

## Verification

- `python -m pytest tests/test_orders_ui.py tests/test_ingest.py tests/test_customer_search.py -q && python -m pytest tests/test_customer_classification_runtime.py -q` — 76 passed.
- `python -m ruff check src/bot/keyboards.py tests/test_orders_ui.py tests/test_ingest.py tests/test_customer_search.py tests/test_customer_classification_runtime.py` — passed.
- `python -m pytest tests/test_customer_classification_runtime.py::test_classification_through_dispatcher -q -s -p no:cacheprovider` — passed; observed real `Application.process_update` send/edit output with `🥇 <b>CHI TIÊU:</b> <b>10.000.000 đ</b>` and `🪙 <b>CHI TIÊU:</b> <b>0 đ</b>` using temporary SQLite and offline transport.
- `git diff --check` — passed.

## Deviations from Plan

None. Formatter and declared tests only; no DB, model, handler, schema, or dependency changes.

## Known Stubs

None introduced.

## Self-Check: PASSED

All five declared modified files exist. Summary exists. No commit created per parent instruction.
