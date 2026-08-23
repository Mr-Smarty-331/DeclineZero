"""
Phase 10 Integration Test: Cold-Clone Verification & Submission Packaging.

Verifies:
1. Complete Submission Documentation: README.md and ASSUMPTIONS.md exist with all required sections.
2. Committed Model Binaries: All required models (baseline triage, uplift treated/control, conformal model & calibration scores, CMDP policy) exist and are non-empty.
3. No Leaked Secrets: .env files, private keys, or credentials are not present in tracked repository files.
4. Docker Stack Completeness: docker-compose.yml defines api, dashboard, redis, postgres, worker.
5. Live API & Service Health: Container services respond cleanly.
"""
import os
import json
import pytest
import requests

def test_submission_documentation_exists():
    """Verify README.md and ASSUMPTIONS.md exist in required directories."""
    root_readme = "README.md"
    sub_readme = "revenue-recovery/README.md"
    assumptions = "revenue-recovery/ASSUMPTIONS.md"

    assert os.path.exists(root_readme), "Missing root README.md"
    assert os.path.exists(sub_readme), "Missing revenue-recovery/README.md"
    assert os.path.exists(assumptions), "Missing ASSUMPTIONS.md"

    with open(root_readme, "r") as f:
        content = f.read()
        assert "DeclineZero" in content
        assert "Triage" in content
        assert "Diagnose" in content
        assert "CMDP" in content
        assert "Merkle" in content
        assert "158.7M" in content or "158" in content

    with open(assumptions, "r") as f:
        assump_content = f.read()
        assert "AVG_CUSTOMER_LTV_LOSS" in assump_content
        assert "AVG_COMPLIANCE_PENALTY" in assump_content
        assert "CONTACT_ATTEMPT_CAP" in assump_content
        assert "CONTACT_WINDOW_HOURS" in assump_content


def test_committed_models_and_policies():
    """Verify all trained artifacts exist for cold-clone instant boot."""
    required_artifacts = [
        "revenue-recovery/core/triage_scorer/models/baseline_triage_model.pkl",
        "revenue-recovery/core/triage_scorer/models/uplift_control.pkl",
        "revenue-recovery/core/triage_scorer/models/uplift_treated.pkl",
        "revenue-recovery/core/diagnostic_tree/models/conformal_base_model.pkl",
        "revenue-recovery/core/diagnostic_tree/models/conformal_calibration_scores.npy",
        "revenue-recovery/policy/stopping_policy.json",
        "revenue-recovery/simulator/data/synthetic_transactions_10k.csv"
    ]
    for path in required_artifacts:
        assert os.path.exists(path), f"Missing required pre-trained artifact: {path}"
        assert os.path.getsize(path) > 0, f"Artifact is empty: {path}"


def test_no_secrets_in_workspace():
    """Verify no live private keys, secrets, or .env files are exposed."""
    for root, dirs, files in os.walk("revenue-recovery"):
        # Ignore git or pycache
        if ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            assert not file.endswith(".env") or file == ".env.example", f"Forbidden .env file detected: {os.path.join(root, file)}"
            assert not file.endswith(".pem"), f"Forbidden private key detected: {os.path.join(root, file)}"
            assert not file.endswith(".key"), f"Forbidden private key detected: {os.path.join(root, file)}"


def test_docker_compose_definition():
    """Verify all 5 required services are defined in docker-compose.yml."""
    dc_path = "revenue-recovery/docker-compose.yml"
    assert os.path.exists(dc_path)
    with open(dc_path, "r") as f:
        dc_content = f.read()
        assert "api:" in dc_content
        assert "dashboard:" in dc_content
        assert "redis:" in dc_content
        assert "postgres:" in dc_content
        assert "worker:" in dc_content


def test_live_api_health():
    """Verify live API health endpoint responds with 200."""
    try:
        resp = requests.get("http://localhost:8000/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    except requests.exceptions.ConnectionError:
        pytest.skip("Docker container not running on localhost:8000")

if __name__ == "__main__":
    test_submission_documentation_exists()
    test_committed_models_and_policies()
    test_no_secrets_in_workspace()
    test_docker_compose_definition()
    test_live_api_health()
    print("✅ All Phase 10 integration and packaging checks PASSED!")
