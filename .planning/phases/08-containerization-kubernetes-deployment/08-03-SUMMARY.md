---
phase: 8
plan: 3
subsystem: deployment
tags: [kubernetes, manifests, github-actions, ci-cd, docker-hub, multi-arch]
dependency-graph:
  requires: ["08-01", "08-02"]
  provides: ["k8s-deployment", "docker-hub-cicd"]
  affects: ["container-deployment", "ci-automation"]
tech-stack:
  added: []
  patterns: ["all-in-one-k8s-manifest", "recreate-deployment-strategy", "docker-buildx-multi-arch"]
key-files:
  created:
    - k8s/all-in-one.yaml
    - .github/workflows/docker-publish.yml
  modified:
    - tests/test_deployment_artifacts.py
decisions:
  - "Enforce replicas: 1 and strategy.type: Recreate in k8s deployment to eliminate concurrent multi-pod write hazards to SQLite WAL"
  - "Multi-arch Docker Hub build (linux/amd64, linux/arm64) using QEMU and Docker Buildx with GitHub Actions layer caching"
metrics:
  duration: 4m
  completed: "2026-10-27"
---

# Phase 8 Plan 3: All-in-One Kubernetes Manifest & GitHub Actions CI/CD Pipeline Summary

Single-command Kubernetes all-in-one manifest with strict single-replica SQLite safety and automated multi-arch Docker Hub build-and-push pipeline via GitHub Actions.

## Key Changes

1. **Single-Command Kubernetes Manifest (`k8s/all-in-one.yaml`):**
   - Namespace `cassette-store`.
   - ConfigMap `bot-config` containing runtime parameters (`TZ`, `SQLITE_DB_PATH=/app/data/cassette_store.db`, `NINE_ROUTER_BASE_URL`, `NINE_ROUTER_MODEL_ID`).
   - Secret `bot-secret` template with `stringData` placeholders for `TELEGRAM_BOT_TOKEN`, `NINE_ROUTER_API_KEY`, and Telegram IDs.
   - PersistentVolumeClaim `bot-data-pvc` with `2Gi` capacity and `ReadWriteOnce` access mode.
   - Deployment `cassette-store-bot`: enforces `replicas: 1` and `strategy.type: Recreate` (protects SQLite WAL integrity against dual-pod writes), `securityContext: fsGroup: 10001, runAsNonRoot: true`, `terminationGracePeriodSeconds: 30`, and exec probes calling `python -m src.scripts.healthcheck`.

2. **GitHub Actions CI/CD (`.github/workflows/docker-publish.yml`):**
   - Triggers on push to `main`, release tags (`v*`), and `workflow_dispatch`.
   - Configures QEMU and Docker Buildx for multi-architecture builds (`linux/amd64,linux/arm64`).
   - Authenticates against Docker Hub using GitHub repository secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`).
   - Publishes images with GitHub Actions cache acceleration.

3. **Deployment Verification Test Suite (`tests/test_deployment_artifacts.py`):**
   - Added `test_k8s_manifest_specs` and `test_github_actions_workflow`.
   - Validates all deployment artifacts, probes, non-root security contexts, and CI/CD targets.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected exit branching logic in healthcheck main function**
- **Found during:** Task 3 test execution
- **Issue:** `sys.exit` mocks in tests did not terminate execution when mocked, causing `sys.exit(1)` and `sys.exit(0)` to both execute in test harness without explicit `if/elif/else`.
- **Fix:** Structured `main()` with explicit `if/elif/else` blocks ensuring exactly one branch executes.
- **Files modified:** `src/scripts/healthcheck.py`

## Threat Surface Verification

- `T-08-04` mitigated via `replicas: 1` + `strategy.type: Recreate` in Deployment + `accessModes: [ReadWriteOnce]` in PVC.
- `T-08-01` mitigated via `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, and `fsGroup: 10001`.

## Self-Check: PASSED
- `k8s/all-in-one.yaml`: FOUND
- `.github/workflows/docker-publish.yml`: FOUND
- `tests/test_deployment_artifacts.py`: FOUND
- Test suite: 321/321 PASSED
