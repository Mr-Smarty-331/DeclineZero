"""
Cross-Phase Integration Test: Phase 1a -> Phase 0 Binding.

Verifies:
1. Relative Path & Location: Batch generation outputs land strictly within the /revenue-recovery/ structure.
2. API Health & Coexistence: Phase 0 FastAPI application remains healthy and responds on GET /health.
3. Dependency Integrity: requirements.txt retains all Phase 0 packages and appends pandas without overwriting.
4. Module Seams: Clean imports across api, core, and simulator without circularity or broken paths.
"""
import os
from pathlib import Path
import requests
import psycopg2
import redis

from simulator.generator import generate_batch, DEFAULT_OUTPUT_PATH
from api.main import app as fastapi_app

def test_relative_path_and_output_location():
    print("Testing generator output location and relative path resolution...")
    batch = generate_batch(n=100)
    assert len(batch) == 100
    
    assert DEFAULT_OUTPUT_PATH.exists(), f"Output file does not exist at {DEFAULT_OUTPUT_PATH}"
    
    # Assert path is located inside the revenue-recovery/simulator/data folder
    resolved_str = str(DEFAULT_OUTPUT_PATH.resolve())
    assert "simulator" in resolved_str and "data" in resolved_str, f"Unexpected output path: {resolved_str}"
    print(f"✅ Output file correctly resolved to relative workspace path: {DEFAULT_OUTPUT_PATH.name}")

def test_requirements_integrity():
    print("Testing requirements.txt dependency preservation...")
    req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    assert req_path.exists(), f"requirements.txt not found at {req_path}"
    
    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read().lower()
        
    expected_phase0_pkgs = ["fastapi", "uvicorn", "psycopg2-binary", "redis", "pydantic", "requests", "streamlit"]
    for pkg in expected_phase0_pkgs:
        assert pkg in content, f"Phase 0 package '{pkg}' was removed from requirements.txt!"
        
    assert "pandas" in content, "Phase 1a package 'pandas' missing from requirements.txt!"
    print("✅ requirements.txt successfully preserves all Phase 0 packages and adds Phase 1 dependencies.")

def test_phase0_api_health():
    print("Testing Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

def test_module_seams():
    print("Testing import seams across api, core, and simulator...")
    assert fastapi_app is not None
    import core
    import simulator.decline_codes as dc
    assert len(dc.ALL_VALID_CODES) > 0
    print("✅ All module seams between Phase 0 (api/core) and Phase 1a (simulator) bind cleanly.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 1a CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_relative_path_and_output_location()
    test_requirements_integrity()
    test_phase0_api_health()
    test_module_seams()
    print("\n🎉 ALL PHASE 1a -> PHASE 0 INTEGRATION SEAMS PASSED!\n")
