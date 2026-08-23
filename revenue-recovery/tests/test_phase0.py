import os
import requests
import redis
import psycopg2

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
API_HOST = os.getenv("API_HOST", "localhost")
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "dashboard")

def test_fastapi_health():
    print("Testing FastAPI /health endpoint...")
    url = f"http://{API_HOST}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data == {"status": "ok"}, f"Expected {{'status': 'ok'}}, got {data}"
    print(f"✅ FastAPI /health is responding with HTTP 200: {data}")

def test_redis_connection():
    print(f"Testing Redis container connection ({REDIS_HOST}:6379)...")
    r = redis.Redis(host=REDIS_HOST, port=6379, db=0, socket_timeout=5)
    ping_result = r.ping()
    assert ping_result is True, "Redis ping failed"
    print("✅ Redis is reachable (PONG)")

def test_postgres_connection():
    print(f"Testing PostgreSQL container connection ({POSTGRES_HOST}:5432)...")
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=5432,
        user="postgres",
        password="postgrespassword",
        dbname="revenue_recovery",
        connect_timeout=5
    )
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    result = cur.fetchone()
    assert result == (1,), f"Expected (1,), got {result}"
    cur.close()
    conn.close()
    print("✅ PostgreSQL is reachable (SELECT 1 returned 1)")

def test_dashboard_health():
    print(f"Testing Streamlit dashboard ({DASHBOARD_HOST}:8501)...")
    url = f"http://{DASHBOARD_HOST}:8501"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("✅ Streamlit dashboard is responding on port 8501 with HTTP 200")

if __name__ == "__main__":
    print("\n==========================================")
    print("   RUNNING PHASE 0 VERIFICATION SUITE")
    print("==========================================")
    test_fastapi_health()
    test_redis_connection()
    test_postgres_connection()
    test_dashboard_health()
    print("\n🎉 ALL PHASE 0 VERIFICATION & CONNECTIVITY CHECKS PASSED!\n")
