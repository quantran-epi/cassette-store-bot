---
phase: 261028-l0t
plan: 01
status: complete
completed: 2026-10-28
requirements-completed: [QUICK-261028-L0T-CUSTOMER-CLASSIFICATION]
---

# Customer classification

## Delivered

- Only `DA_GIAO` contributes to purchase count and spending; all-time BOM warnings remain separate.
- Frequency: 0, 1, 2–4, and at least 5 completed orders, with distinct markers and bold Vietnamese labels.
- Spending: below 1 million, 1–below 3 million, 3–below 10 million, and at least 10 million VND; separate highlighted label with actual total.
- Covered order preview, detail, date/status lists, natural-language search lists, mutation chooser, and customer profile.
- List hydration uses one shared batch aggregate scoped to displayed customer IDs, avoiding N+1 and whole-database aggregate joins.
- Missing customer association remains unknown, not fabricated zero history. All-status history and pagination preserved.
- No schema, dependency, or callback-data changes.

## Checks

- Focused regression suite: 92 passed.
- Full suite in primary checkout initially: 418 passed, 3 JobQueue warnings. Latest rerun: 417 passed, 1 failed (`tests/test_backup_restore.py::test_stage_rejects_missing_required_table`: staging `restore.sqlite3` still exists after rejection). Backup/restore files were not changed; this failure remains unresolved. Feature-focused suite and lint/diff checks still pass after final batch-hydration simplification.
- Ruff and `git diff --check`: passed.
- Executor worktree initially reported 417 passed/1 failure (`no such table: reminders`); reproduced at pristine HEAD there. Primary checkout full suite passes without changing unrelated reminder code.
- Real PTB `Application.process_update` with synthetic updates, temporary SQLite, whitelist gate, production handlers, and offline `BaseRequest` captured outgoing Bot API bodies.
- Independently drove status list, order detail, customer profile, next history page, and BOM-only profile in primary checkout. Observed 5 completed orders/10 million VND despite another pending order, history page 2/2, and BOM-only customer at zero completed purchases with warning intact.
- Runtime captures: `261028-l0t-dispatcher.json` (primary checkout) and `261028-l0t-runtime.txt` (executor).
- Boundary tests cover counts 0/1/2/4/5 and spending 999999/1000000/2999999/3000000/9999999/10000000.
- No live Telegram traffic, polling, external LLM calls, or production database writes.

## Workflow

Changes transferred from executor worktree to primary checkout. Unrelated debug artifact preserved. Local ignored verification recipe stored at `.claude/skills/verify/SKILL.md`.

User subsequently requested pushing main. Feature code, tests, and quick-task artifacts included in delivery commit; unrelated debug artifact excluded. ROADMAP unchanged; STATE updated by coordinator.
