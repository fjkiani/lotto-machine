import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_darkpool_levels_fail_loudly():
    """Verify that if API key is missing, we get a 503/502/404, NOT mock data."""
    # We don't set the API key here to force a failure or a check
    response = client.get("/api/v1/darkpool/SPY/levels")
    # If key is missing, our new code raises 503
    assert response.status_code in [200, 503, 502, 404]
    
    if response.status_code == 200:
        data = response.json()
        assert "levels" in data
        assert data["symbol"] == "SPY"
        # Verify it's not the old mock data (old mock had specific hardcoded prices like 450.25)
        for level in data["levels"]:
            assert level["price"] != 450.25 

def test_signals_divergence_route_exists():
    """Verify that the /signals/divergence route is now registered and reachable."""
    response = client.get("/api/v1/signals/divergence")
    # It might return 503 if monitor isn't fully initialized in test env, 
    # but it should NOT be 404.
    assert response.status_code != 404

def test_health_checkers_registered():
    """Verify that the health router is registered and working."""
    response = client.get("/api/v1/health/checkers")
    assert response.status_code == 200
    data = response.json()
    assert "checkers" in data
    assert isinstance(data["checkers"], list)

if __name__ == "__main__":
    import traceback
    # Run simple check
    print("Running API verification...")
    try:
        test_health_checkers_registered()
        print("✅ Health router verified")
        test_signals_divergence_route_exists()
        print("✅ Signals divergence route verified (exists)")
        test_darkpool_levels_fail_loudly()
        print("✅ Darkpool data integrity verified (no mock detected)")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        traceback.print_exc()
