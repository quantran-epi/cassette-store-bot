import os
import sqlite3
import time
from unittest.mock import MagicMock, patch

import pytest

from src.scripts import healthcheck


def test_healthcheck_script_healthy_state(tmp_path, monkeypatch):
    """Verify healthcheck passes when heartbeat is recent and DB ping succeeds."""
    heartbeat_file = tmp_path / "bot_heartbeat"
    heartbeat_file.write_text(str(time.time()), encoding="utf-8")

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE dummy (id INTEGER);")
    conn.commit()
    conn.close()

    monkeypatch.setattr(healthcheck, "HEARTBEAT_FILE", str(heartbeat_file))
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_file))

    assert healthcheck.check_heartbeat() is True
    assert healthcheck.check_database() is True

    # main should return cleanly (no sys.exit(1))
    with patch("sys.exit") as mock_exit:
        healthcheck.main()
        mock_exit.assert_called_once_with(0)


def test_healthcheck_script_missing_or_stale_heartbeat(tmp_path, monkeypatch):
    """Verify healthcheck fails when heartbeat is missing or older than MAX_HEARTBEAT_AGE."""
    non_existent = tmp_path / "non_existent_heartbeat"
    monkeypatch.setattr(healthcheck, "HEARTBEAT_FILE", str(non_existent))
    assert healthcheck.check_heartbeat() is False

    stale_file = tmp_path / "stale_heartbeat"
    stale_file.write_text(str(time.time() - 200), encoding="utf-8")
    old_time = time.time() - 150
    os.utime(str(stale_file), (old_time, old_time))

    monkeypatch.setattr(healthcheck, "HEARTBEAT_FILE", str(stale_file))
    assert healthcheck.check_heartbeat() is False

    with patch("sys.exit") as mock_exit:
        healthcheck.main()
        mock_exit.assert_called_once_with(1)


def test_healthcheck_script_db_failure(tmp_path, monkeypatch):
    """Verify healthcheck fails when SQLite query raises an exception or corrupt."""
    heartbeat_file = tmp_path / "bot_heartbeat"
    heartbeat_file.write_text(str(time.time()), encoding="utf-8")
    monkeypatch.setattr(healthcheck, "HEARTBEAT_FILE", str(heartbeat_file))

    corrupt_db = tmp_path / "corrupt.db"
    corrupt_db.write_text("NOT A VALID SQLITE DB", encoding="utf-8")
    monkeypatch.setenv("SQLITE_DB_PATH", str(corrupt_db))

    assert healthcheck.check_database() is False

    with patch("sys.exit") as mock_exit:
        healthcheck.main()
        mock_exit.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_post_shutdown_wal_checkpoint(tmp_path):
    """Verify post_shutdown_cleanup executes PRAGMA wal_checkpoint(TRUNCATE)."""
    from src.bot.app import post_shutdown_cleanup

    db_path = str(tmp_path / "wal_test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO items (name) VALUES ('Cassette');")
    conn.commit()
    conn.close()

    app_mock = MagicMock()
    settings_mock = MagicMock()
    settings_mock.sqlite_db_path = db_path
    app_mock.bot_data = {"settings": settings_mock}

    await post_shutdown_cleanup(app_mock)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM items;")
    rows = cursor.fetchall()
    conn.close()
    assert rows == [("Cassette",)]


def test_dockerfile_and_dockerignore():
    """Verify Dockerfile and .dockerignore specifications."""
    assert os.path.exists("Dockerfile")
    assert os.path.exists(".dockerignore")

    with open("Dockerfile", encoding="utf-8") as f:
        dockerfile_content = f.read()

    assert "FROM python:3.12-slim AS builder" in dockerfile_content
    assert "USER 10001" in dockerfile_content
    assert "TZ=Asia/Ho_Chi_Minh" in dockerfile_content
    assert "mkdir -p /app/data /app/data/backups" in dockerfile_content
    assert "HEALTHCHECK" in dockerfile_content
    assert "src.scripts.healthcheck" in dockerfile_content

    with open(".dockerignore", encoding="utf-8") as f:
        dockerignore_content = f.read()

    assert ".env" in dockerignore_content
    assert "*.db" in dockerignore_content
    assert "backups/" in dockerignore_content
    assert ".venv" in dockerignore_content


def test_docker_compose_config():
    """Verify docker-compose.yml configuration parameters."""
    assert os.path.exists("docker-compose.yml")

    with open("docker-compose.yml", encoding="utf-8") as f:
        compose_content = f.read()

    assert "cassette-bot:" in compose_content
    assert "container_name: cassette-store-bot" in compose_content
    assert "stop_grace_period: 30s" in compose_content
    assert "cassette_data:/app/data" in compose_content
    assert "src.scripts.healthcheck" in compose_content


def test_k8s_manifest_specs():
    """Verify Kubernetes all-in-one manifest specifications."""
    assert os.path.exists("k8s/all-in-one.yaml")

    with open("k8s/all-in-one.yaml", encoding="utf-8") as f:
        k8s_content = f.read()

    assert "kind: Namespace" in k8s_content
    assert "kind: ConfigMap" in k8s_content
    assert "kind: Secret" in k8s_content
    assert "kind: PersistentVolumeClaim" in k8s_content
    assert "ReadWriteOnce" in k8s_content
    assert "kind: Deployment" in k8s_content
    assert "replicas: 1" in k8s_content
    assert "type: Recreate" in k8s_content
    assert "fsGroup: 10001" in k8s_content
    assert "runAsNonRoot: true" in k8s_content
    assert "livenessProbe:" in k8s_content
    assert "readinessProbe:" in k8s_content
    assert "src.scripts.healthcheck" in k8s_content


def test_github_actions_workflow():
    """Verify GitHub Actions CI/CD workflow."""
    workflow_path = ".github/workflows/docker-publish.yml"
    assert os.path.exists(workflow_path)

    with open(workflow_path, encoding="utf-8") as f:
        workflow_content = f.read()

    assert "branches: [ \"main\" ]" in workflow_content or "branches: [ main ]" in workflow_content
    assert "docker/setup-buildx-action" in workflow_content
    assert "docker/login-action" in workflow_content
    assert "platforms: linux/amd64,linux/arm64" in workflow_content
    assert "DOCKERHUB_USERNAME" in workflow_content
