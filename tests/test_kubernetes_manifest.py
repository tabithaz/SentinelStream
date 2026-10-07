from pathlib import Path


MANIFEST = (Path(__file__).parents[1] / "deploy" / "kubernetes.yaml").read_text()


def test_manifest_provisions_service_deployment_disruption_budget_and_autoscaler():
    assert "kind: Service" in MANIFEST
    assert "kind: Deployment" in MANIFEST
    assert "kind: PodDisruptionBudget" in MANIFEST
    assert "kind: HorizontalPodAutoscaler" in MANIFEST
    assert "replicas: 2" in MANIFEST
    assert "minAvailable: 1" in MANIFEST


def test_deployment_uses_distinct_liveness_and_readiness_probes():
    assert "livenessProbe:\n            httpGet:\n              path: /health" in MANIFEST
    assert "readinessProbe:\n            httpGet:\n              path: /ready" in MANIFEST
    assert "startupProbe:\n            httpGet:\n              path: /health" in MANIFEST


def test_deployment_has_zero_downtime_rollout_and_resource_budgets():
    assert "maxUnavailable: 0" in MANIFEST
    assert "maxSurge: 1" in MANIFEST
    assert "requests:" in MANIFEST
    assert "cpu: 100m" in MANIFEST
    assert "memory: 128Mi" in MANIFEST
    assert "limits:" in MANIFEST
    assert "cpu: 500m" in MANIFEST
    assert "memory: 512Mi" in MANIFEST


def test_deployment_enforces_a_hardened_non_root_container():
    assert "runAsNonRoot: true" in MANIFEST
    assert "runAsUser: 10001" in MANIFEST
    assert "type: RuntimeDefault" in MANIFEST
    assert "allowPrivilegeEscalation: false" in MANIFEST
    assert "readOnlyRootFilesystem: true" in MANIFEST
    assert "drop:\n                - ALL" in MANIFEST


def test_autoscaler_uses_cpu_and_memory_with_safe_replica_bounds():
    assert "apiVersion: autoscaling/v2" in MANIFEST
    assert "minReplicas: 2" in MANIFEST
    assert "maxReplicas: 10" in MANIFEST
    assert "name: cpu" in MANIFEST
    assert "averageUtilization: 70" in MANIFEST
    assert "name: memory" in MANIFEST
    assert "averageUtilization: 75" in MANIFEST


def test_autoscaler_limits_scale_down_churn():
    assert "scaleDown:" in MANIFEST
    assert "stabilizationWindowSeconds: 300" in MANIFEST
    assert "value: 25" in MANIFEST
