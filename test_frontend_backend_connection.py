"""
test_frontend_backend_connection.py
Verifies complete connection between Frontend Static Files and Backend REST API endpoints.
"""

import sys
import threading
import time
import urllib.request
import json

from uvicorn import Server, Config
from app.main import app

def run_tests():
    config = Config(app=app, host="127.0.0.1", port=8002, log_level="warning")
    server = Server(config=config)
    t = threading.Thread(target=server.run)
    t.daemon = True
    t.start()
    time.sleep(1.5)

    base = "http://127.0.0.1:8002"
    passed = 0

    try:
        # Test 1: Frontend Root index.html
        with urllib.request.urlopen(f"{base}/index.html") as resp:
            data = resp.read().decode("utf-8")
            assert "Cashio Security" in data
            print("[PASS] 1. Frontend landing page (index.html) successfully served.")
            passed += 1

        # Test 2: Frontend CSS and JS
        with urllib.request.urlopen(f"{base}/css/style.css") as resp:
            data = resp.read().decode("utf-8")
            assert "Navy Blue" in data or "navy-primary" in data
            print("[PASS] 2. Frontend styling (style.css) successfully served.")
            passed += 1

        with urllib.request.urlopen(f"{base}/js/api.js") as resp:
            data = resp.read().decode("utf-8")
            assert "API_BASE" in data
            print("[PASS] 3. Frontend API client (api.js) successfully served.")
            passed += 1

        # Test 3: Backend Health Endpoint
        with urllib.request.urlopen(f"{base}/api/health") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "online"
            print(f"[PASS] 4. Backend Health check online: {data}")
            passed += 1

        # Test 4: Register Customer via API (Username must be lowercase letters only)
        suffix = "".join([chr(97 + (int(time.time() * 1000) >> i) % 26) for i in (0, 5, 10, 15)])
        username = f"user{suffix}"

        reg_payload = json.dumps({
            "name": username,
            "password": "Password@1234",
            "pin": "1234",
            "email": "test@cashio.in",
            "phone": "9876543210",
            "address": "Mumbai"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base}/auth/register",
            data=reg_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            reg_res = json.loads(resp.read().decode("utf-8"))
            acc_num = reg_res["account_number"]
            username = reg_res["name"]
            assert len(acc_num) == 8
            print(f"[PASS] 5. User registration connected: Created Account #{acc_num} ({username}).")
            passed += 1

        # Test 5: Login and Receive JWT
        login_payload = json.dumps({
            "name": username,
            "password": "Password@1234"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base}/auth/login",
            data=login_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            login_res = json.loads(resp.read().decode("utf-8"))
            token = login_res["access_token"]
            assert token
            print("[PASS] 6. Customer Login connected: JWT token issued successfully.")
            passed += 1

        # Test 6: Authenticated Account Details
        req = urllib.request.Request(
            f"{base}/account/details",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req) as resp:
            acc_details = json.loads(resp.read().decode("utf-8"))
            assert acc_details["account_number"] == acc_num
            safe_bal = acc_details['balance_rupees'].replace("\u20b9", "Rs. ")
            print(f"[PASS] 7. Authenticated Dashboard endpoint connected: Balance is {safe_bal}.")
            passed += 1

        print("\n" + "=" * 65)
        print(f" ALL {passed}/7 TESTS PASSED: FRONTEND AND BACKEND ARE FULLY CONNECTED!")
        print("=" * 65)

    except Exception as e:
        print(f"[FAIL] Error connecting frontend and backend: {e}")
        sys.exit(1)
    finally:
        server.should_exit = True

if __name__ == "__main__":
    run_tests()
