---
status: complete
quick_id: 261115-ga1
code_commit: 7ead9e1
---

# Pending orders quick menu

- Replaced today's menu button with `⏳ Đơn chờ làm`; routed through existing CHO_LAM status-list renderer and callbacks, including older pending orders.
- Kept today's orders accessible through `📋 Xem theo ngày` and `Hôm nay`; updated tutorial and try-now shortcut.
- Preserved all five pre-existing dirty files (order-card icons, payment labels, compact dividers and related assertions), committed alongside menu change.

## Checks

- Focused order UI/tutorial suite: 75 passed.
- Full suite before final tutorial-only regression addition: 662 passed, 1 failed (`tests/test_deployment_artifacts.py::test_healthcheck_script_db_failure`). Reproduces standalone; healthcheck source and its tests identical to HEAD before task. Corrupt DB unexpectedly passes `check_database()`. Not changed in this task.
- Ruff on newly modified menu, handler, tutorial and associated tests: passed.
- Ruff including all pre-existing dirty tests: existing F841 unused `oid2` at tests/test_order_search.py:1270; reproduced from original HEAD using stdin lint. Left unchanged.
- Mandatory `/verify` offline dispatcher check ran successfully immediately before code commit; commit guarded by `&&`.
- `git apply --reverse --check /tmp/cassette-store-bot-before-pending-menu-20261115.patch`: passed before commit, proving prior hunks retained.
- Whitespace check passed with CRLF-aware `core.whitespace=cr-at-eol`.

## Delivery

Code committed on quick/pending-orders-menu-20261115. Orchestrator records workflow artifacts, fast-forwards local main, then pushes origin main without force.
