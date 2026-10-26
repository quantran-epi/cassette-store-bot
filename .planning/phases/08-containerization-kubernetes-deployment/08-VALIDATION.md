---
phase: 8
slug: containerization-kubernetes-deployment
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-27
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (`.venv/bin/pytest`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_deployment_artifacts.py -x` |
| **Full suite command** | `.venv/bin/pytest` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_deployment_artifacts.py -x`
- **After every plan wave:** Run `.venv/bin/pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | DEP-01, DEP-02, DEP-03, DEP-04, DEP-05 | — | Setup deployment tests scaffold | test | `.venv/bin/pytest tests/test_deployment_artifacts.py -x` | ✅ | ✅ green |
| 08-01-02 | 01 | 1 | DEP-01, DEP-02 | T-08-01 | Dockerfile multi-stage, non-root user 10001, TZ VN, .dockerignore | spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_dockerfile_and_dockerignore -x` | ✅ | ✅ green |
| 08-02-01 | 02 | 1 | DEP-05 | T-08-03 | Healthcheck script stdlib + post_shutdown WAL checkpoint TRUNCATE | unit | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_healthcheck_script_and_graceful_shutdown -x` | ✅ | ✅ green |
| 08-02-02 | 02 | 2 | DEP-03 | T-08-02 | docker-compose.yml with named volume, healthcheck, stop_grace_period 30s | spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_docker_compose_config -x` | ✅ | ✅ green |
| 08-03-01 | 03 | 2 | DEP-04 | T-08-04 | k8s/all-in-one.yaml with Recreate, replicas 1, PVC 2Gi, exec probes | spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_k8s_manifest_specs -x` | ✅ | ✅ green |
| 08-03-02 | 03 | 2 | DEP-01 | T-08-02 | .github/workflows/docker-publish.yml multi-arch Buildx push Docker Hub | spec | `.venv/bin/pytest tests/test_deployment_artifacts.py -k test_github_actions_workflow -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_deployment_artifacts.py` — automated assertions for Dockerfile, docker-compose.yml, k8s/all-in-one.yaml, healthcheck script, and post_shutdown hook

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Multi-arch build & push to Docker Hub | DEP-01 | Requires live Docker daemon and Docker Hub credentials | Run docker buildx build locally or push branch to GitHub with secrets configured |
| Live K8s cluster deployment | DEP-04 | Requires live Kubernetes cluster | `kubectl apply -f k8s/all-in-one.yaml` and verify Pod status Running |

*All code artifacts and syntax specifications are fully validated automatically via pytest.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-10-27
