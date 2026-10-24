---
status: testing
phase: 02-llm-ingestion-interactive-confirmation
source: [02-VERIFICATION.md]
started: 2026-10-24T00:00:00Z
updated: 2026-10-24T00:00:00Z
---

## Current Test

number: 1
name: Visual UX on Mobile Telegram
expected: |
  Send a messy Vietnamese free-text order on a phone Telegram client.
  Confirm HTML preview card renders clearly with bold labels, mono phone tag, itemized product list, and separate Total / COD amounts.
awaiting: user response

## Tests

### 1. Visual UX on Mobile Telegram
expected: |
  Send a messy Vietnamese free-text order on a phone Telegram client.
  Confirm HTML preview card renders clearly with bold labels, mono phone tag, itemized product list, and separate Total / COD amounts.
result: [pending]

### 2. Immediate Button Tap Feedback
expected: |
  Tap [✅ Xác nhận lưu] or [❌ Huỷ bỏ].
  Verify Telegram acknowledges instantly (answer_callback_query) without the ~30s spinner wheel.
result: [pending]

### 3. Photo Caption Ingestion on Real Telegram
expected: |
  Send a photo of a cassette tape with order text in caption.
  Verify card renders with tape preview, and upon confirmation, order row has non-empty photos_json with highest-resolution file_id.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
