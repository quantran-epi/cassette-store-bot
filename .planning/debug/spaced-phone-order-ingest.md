---
status: awaiting_human_verify
trigger: "lỗi nghiêm trọng, nếu tin nhắn đơn hàng mới có sđt có dấu cách ở giữa các số hoặc không đúng form, không nhận diện được đơn"
created: 2026-11-12
updated: 2026-11-12
---

## Current Focus

hypothesis: Confirmed: both deterministic extraction fallbacks matched only contiguous digits and lacked whole-number boundaries.
next_action: Commit verified fix and push main as requested; user live-workflow verification remains pending.
verification_scope: Offline mocked LLM/Telegram with synthetic data only; no restart or production API/DB access.

## Symptoms

expected: Recognize new-order text with normally formatted valid Vietnamese mobile numbers; reject invalid numbers without inventing digits.
actual: Spaced/formatted phones were lost when LLM omitted phone or failed; overlong numbers could be truncated into valid-looking phones.
errors: None supplied.
timeline: Unknown.
reproduction: Synthetic orders with 0912 345 678, +84 912 345 678, or 09123456789, with mocked partial/failed LLM responses.

## Evidence

- Existing model handled separators, but both fallback paths used contiguous-only unbounded regex and duplicated normalization.
- Before source fix, new regression tests failed; after fix, focused extraction/ingestion suite passed 176 cases in isolated worktree.
- Tests cover normal whitespace, tabs, NBSP, dots, dashes, parentheses, +84/84/0084, malformed lengths/prefixes, neighboring quantity/currency, text/photo ingestion and explicit search isolation.
- Original checkout baseline before fix: 501 passed, 1 failed (tests/test_deployment_artifacts.py::test_healthcheck_script_db_failure).
- Integrated full suite: 641 passed, 1 failed, 4 warnings. Same pre-existing healthcheck failure: check_database() returns True for corrupt DB. No newly failing tests.
- Changed-file Ruff and CRLF-aware diff whitespace checks passed.
- Isolated worktree additionally reproduced an environment-specific missing reminders table on unchanged HEAD; original checkout does not exhibit that failure.

## Eliminated

- Intent classification: normal ingestion calls extractor directly outside explicit search mode; routing changes unnecessary.
- Missing-phone drafts: existing confirmation path requires phone; retain safe resend UX rather than introduce incomplete drafts.

## Resolution

root_cause: Contiguous-only fallback disagreed with model normalization; unbounded regex accepted malformed substrings.
fix: Share whole-candidate scanner between fallback paths and normalize with existing ExtractedOrder validator; add 0084 normalization and exclude explicit quantity/currency digits before validating. Preserve original text and confirmation/search behavior.
verification: 140 added regression cases; integrated full suite 641 passed and same 1 baseline failure. Offline dispatcher /verify required immediately before commit.
files_changed:
  - src/models/extractor.py
  - src/services/extractor.py
  - tests/test_extractor.py
  - tests/test_ingest.py
limitations: Ambiguous formatted runs without clear field boundaries remain missing and prompt resend. Live Telegram/provider behavior not exercised. No production restart performed.
