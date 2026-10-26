"""Container healthcheck probe script using only Python standard library.

Checks:
1. Heartbeat file existence and freshness (< 90 seconds).
2. SQLite database connectivity ping (SELECT 1 with 2s timeout).
Exit 0 if healthy, exit 1 if unhealthy.
"""

import os
import sqlite3
import sys
import time

HEARTBEAT_FILE = "/tmp/bot_heartbeat"
MAX_HEARTBEAT_AGE = 90  # seconds (JobQueue writes every 30s)
DB_PING_TIMEOUT = 2.0   # seconds


def check_heartbeat() -> bool:
    """Verify heartbeat file exists and has been modified recently."""
    if not os.path.exists(HEARTBEAT_FILE):
        sys.stderr.write(f"Healthcheck FAIL: Heartbeat file {HEARTBEAT_FILE} does not exist\n")
        return False

    try:
        mtime = os.path.getmtime(HEARTBEAT_FILE)
        age = time.time() - mtime
        if age > MAX_HEARTBEAT_AGE:
            sys.stderr.write(f"Healthcheck FAIL: Heartbeat stale ({age:.1f}s > {MAX_HEARTBEAT_AGE}s)\n")
            return False
    except OSError as e:
        sys.stderr.write(f"Healthcheck FAIL: Error reading heartbeat file: {e}\n")
        return False

    return True


def check_database() -> bool:
    """Verify SQLite database responds to a simple query."""
    db_path = os.environ.get("SQLITE_DB_PATH", "/app/data/cassette_store.db")
    if not os.path.exists(db_path):
        # Initial boot before table creation - pass if heartbeat is healthy
        return True

    try:
        conn = sqlite3.connect(db_path, timeout=DB_PING_TIMEOUT)
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        res = cursor.fetchone()
        conn.close()
        if not res or res[0] != 1:
            sys.stderr.write("Healthcheck FAIL: Unexpected result from DB ping\n")
            return False
    except Exception as e:
        sys.stderr.write(f"Healthcheck FAIL: Database ping failed: {e}\n")
        return False

    return True


def main() -> None:
    if not check_heartbeat():
        sys.exit(1)
    elif not check_database():
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
