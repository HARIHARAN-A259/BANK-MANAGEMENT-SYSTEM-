"""
test_complete_system.py — Comprehensive end-to-end verification script
Tests ALL 15 frontend pages, all static assets, and every single backend API endpoint.
"""

import sys
import requests

# Ensure UTF-8 output for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def test_everything():
    print("=" * 70)
    print("  CASHIO SECURITY - COMPREHENSIVE END-TO-END SYSTEM VERIFICATION")
    print("=" * 70)
    
    passed = 0
    failed = 0

    def record(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"[PASS] {name} {f'({detail})' if detail else ''}")
        else:
            failed += 1
            print(f"[FAIL] {name} - {detail}")

    session = requests.Session()

    # ---------------------------------------------------------
    # 1. FRONTEND PAGES (HTML)
    # ---------------------------------------------------------
    print("\n--- 1. Testing Frontend HTML Pages ---")
    pages = [
        ("Landing Page (index.html)", "/"),
        ("Alternative UI Route", "/app-ui/"),
        ("Login Page", "/login.html"),
        ("Register Page", "/register.html"),
        ("Dashboard Page", "/dashboard.html"),
        ("Deposit Page", "/deposit.html"),
        ("Withdraw Page", "/withdraw.html"),
        ("Transfer Page", "/transfer.html"),
        ("Transactions History Page", "/transactions.html"),
        ("Account Statement Page", "/statement.html"),
        ("ATM Debit Card Page", "/card.html"),
        ("Interest Calculator Page", "/interest.html"),
        ("User Profile Page", "/profile.html"),
        ("Admin Login Page", "/admin-login.html"),
        ("Admin Supervisory Panel Page", "/admin.html"),
        ("404 Error Page", "/404.html"),
    ]
    for name, path in pages:
        r = session.get(f"{BASE_URL}{path}")
        record(f"Page: {name}", r.status_code == 200, f"HTTP {r.status_code}")

    # ---------------------------------------------------------
    # 2. FRONTEND ASSETS (CSS, JS, IMAGES)
    # ---------------------------------------------------------
    print("\n--- 2. Testing Frontend Static Assets ---")
    assets = [
        ("Main CSS (css/style.css)", "/css/style.css"),
        ("3D Card CSS (css/card.css)", "/css/card.css"),
        ("API Wrapper (js/api.js)", "/js/api.js"),
        ("Auth Helper (js/auth.js)", "/js/auth.js"),
        ("UI Components (js/ui.js)", "/js/ui.js"),
        ("Cashio Bank Logo (assets/logo.png)", "/assets/logo.png"),
        ("ATM EMV Chip SVG (assets/chip.svg)", "/assets/chip.svg"),
        ("Favicon (/favicon.ico)", "/favicon.ico"),
    ]
    for name, path in assets:
        r = session.get(f"{BASE_URL}{path}")
        record(f"Asset: {name}", r.status_code == 200 and len(r.content) > 20, f"Size: {len(r.content)} bytes")

    # ---------------------------------------------------------
    # 3. BACKEND SYSTEM & DOCUMENTATION
    # ---------------------------------------------------------
    print("\n--- 3. Testing Backend Health & Documentation ---")
    r = session.get(f"{BASE_URL}/api/health")
    health = r.json() if r.status_code == 200 else {}
    record("Health Check API (/api/health)", r.status_code == 200 and health.get("status") == "online", str(health))

    r = session.get(f"{BASE_URL}/docs")
    record("Swagger Documentation UI (/docs)", r.status_code == 200 and "Cashio Security API" in r.text)

    r = session.get(f"{BASE_URL}/openapi.json")
    spec = r.json() if r.status_code == 200 else {}
    record("OpenAPI Specification (/openapi.json)", r.status_code == 200 and spec.get("info", {}).get("title") == "Cashio Security API")

    # ---------------------------------------------------------
    # 4. ADMIN SETUP & AUTHENTICATION
    # ---------------------------------------------------------
    print("\n--- 4. Testing Admin Setup & Authentication ---")
    r = session.get(f"{BASE_URL}/admin/status")
    status_data = r.json() if r.status_code == 200 else {}
    record("Admin Status Check (/admin/status)", r.status_code == 200, f"Configured: {status_data.get('configured')}")

    admin_token = None
    admin_user = "admin_master"
    admin_pass = "AdminPass@999"

    r_reg = session.post(f"{BASE_URL}/admin/register", json={"username": admin_user, "password": admin_pass})
    if r_reg.status_code == 200:
        admin_token = r_reg.json().get("access_token")
        record("Create New Admin ID (/admin/register)", True, f"Admin '{admin_user}' created")
    else:
        # Already exists, login
        r_log = session.post(f"{BASE_URL}/admin/login", json={"username": admin_user, "password": admin_pass})
        if r_log.status_code == 200:
            admin_token = r_log.json().get("access_token")
            record("Admin Login (/admin/login)", True, f"Logged in as '{admin_user}'")
        else:
            record("Admin Authentication", False, f"Register HTTP {r_reg.status_code}: {r_reg.text}; Login HTTP {r_log.status_code}: {r_log.text}")

    admin_headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}

    # ---------------------------------------------------------
    # 5. CUSTOMER REGISTRATION
    # ---------------------------------------------------------
    print("\n--- 5. Testing Customer Registration ---")
    c1_payload = {
        "name": "HARIHARAN A",
        "password": "Password@123",
        "pin": "1234",
        "email": "hari@cashiosecurity.in",
        "phone": "9876543210",
        "address": "Coimbatore, Tamil Nadu"
    }
    r = session.post(f"{BASE_URL}/auth/register", json=c1_payload)
    if r.status_code == 201:
        c1_acc = r.json().get("account_number")
        record("Customer 1 Registration (HARIHARAN A)", True, f"Account #{c1_acc}")
    elif r.status_code == 400 and ("already taken" in r.text or "already exists" in r.text):
        record("Customer 1 Registration (HARIHARAN A)", True, "Account registered & ready")
    else:
        record("Customer 1 Registration (HARIHARAN A)", False, f"HTTP {r.status_code}: {r.text}")

    c2_payload = {
        "name": "PRIYA S",
        "password": "Password@123",
        "pin": "5678",
        "email": "priya@cashiosecurity.in",
        "phone": "9123456780",
        "address": "Chennai, Tamil Nadu"
    }
    r = session.post(f"{BASE_URL}/auth/register", json=c2_payload)
    if r.status_code == 201:
        c2_acc = r.json().get("account_number")
        record("Customer 2 Registration (PRIYA S)", True, f"Account #{c2_acc}")
    elif r.status_code == 400 and ("already taken" in r.text or "already exists" in r.text):
        record("Customer 2 Registration (PRIYA S)", True, "Account registered & ready")
    else:
        record("Customer 2 Registration (PRIYA S)", False, f"HTTP {r.status_code}: {r.text}")

    # ---------------------------------------------------------
    # 6. CUSTOMER LOGIN & AUTHENTICATION
    # ---------------------------------------------------------
    print("\n--- 6. Testing Customer Authentication ---")
    # Login Customer 1 with exact case
    r = session.post(f"{BASE_URL}/auth/login", json={"name": "HARIHARAN A", "password": "Password@123"})
    c1_login = r.json() if r.status_code == 200 else {}
    c1_token = c1_login.get("access_token")
    c1_acc = c1_login.get("account_number")
    record("Customer Login with Exact Case ('HARIHARAN A')", r.status_code == 200 and c1_token is not None, f"Acc #{c1_acc}")

    # Login Customer 1 with lowercase (case insensitivity)
    r = session.post(f"{BASE_URL}/auth/login", json={"name": "hariharan a", "password": "Password@123"})
    record("Customer Login with Lowercase ('hariharan a')", r.status_code == 200, "Case-insensitive login verified")

    # Login Customer 2
    r = session.post(f"{BASE_URL}/auth/login", json={"name": "PRIYA S", "password": "Password@123"})
    c2_login = r.json() if r.status_code == 200 else {}
    c2_token = c2_login.get("access_token")
    c2_acc = c2_login.get("account_number")
    record("Customer 2 Login ('PRIYA S')", r.status_code == 200 and c2_token is not None, f"Acc #{c2_acc}")

    c1_headers = {"Authorization": f"Bearer {c1_token}"}
    c2_headers = {"Authorization": f"Bearer {c2_token}"}

    # ---------------------------------------------------------
    # 7. CUSTOMER PROFILE & DETAILS
    # ---------------------------------------------------------
    print("\n--- 7. Testing Customer Profile & Details ---")
    r = session.get(f"{BASE_URL}/account/details", headers=c1_headers)
    record("Fetch Account Details (/account/details)", r.status_code == 200, f"Holder: {r.json().get('name')}")

    r = session.get(f"{BASE_URL}/account/profile", headers=c1_headers)
    record("Fetch Account Profile (/account/profile)", r.status_code == 200, f"Phone: {r.json().get('phone')}")

    r = session.put(f"{BASE_URL}/account/profile", headers=c1_headers, json={
        "email": "hari.updated@cashiosecurity.in",
        "phone": "9876543211",
        "address": "Gandhipuram, Coimbatore"
    })
    record("Update Profile (/account/profile)", r.status_code == 200, r.json().get("message"))

    # ---------------------------------------------------------
    # 8. FINANCIAL TRANSACTIONS
    # ---------------------------------------------------------
    print("\n--- 8. Testing Financial Transactions (Paise Math) ---")
    # Deposit Rs 50,000
    r = session.post(f"{BASE_URL}/transactions/deposit", headers=c1_headers, json={"amount": 50000.0, "remark": "Salary credit"})
    record("Deposit Rs 50,000 (/transactions/deposit)", r.status_code == 200, f"Message: {r.json().get('message') if r.status_code==200 else r.text}")

    # Balance check
    r = session.get(f"{BASE_URL}/account/balance", headers=c1_headers)
    bal_data = r.json() if r.status_code == 200 else {}
    record("Balance Check (/account/balance)", r.status_code == 200, f"Balance: {bal_data.get('balance_rupees')}")

    # Withdraw Rs 10,000 with PIN
    r = session.post(f"{BASE_URL}/transactions/withdraw", headers=c1_headers, json={"amount": 10000.0, "pin": "1234", "remark": "ATM withdrawal"})
    record("Withdraw Rs 10,000 (/transactions/withdraw)", r.status_code == 200, f"Message: {r.json().get('message') if r.status_code==200 else r.text}")

    # Atomic Transfer Rs 15,000 to Customer 2
    r = session.post(f"{BASE_URL}/transactions/transfer", headers=c1_headers, json={
        "to_account": c2_acc,
        "amount": 15000.0,
        "pin": "1234",
        "remark": "Project fee payment"
    })
    record("Atomic Transfer Rs 15,000 to Customer 2", r.status_code == 200, r.json().get("message") if r.status_code==200 else r.text)

    # Verify Customer 2 received funds
    r = session.get(f"{BASE_URL}/account/balance", headers=c2_headers)
    c2_bal = r.json() if r.status_code == 200 else {}
    record("Customer 2 Balance Verification", c2_bal.get("balance_paise", 0) >= 1500000, f"Customer 2 Balance: {c2_bal.get('balance_rupees')}")

    # Apply 4.0% Interest
    r = session.post(f"{BASE_URL}/account/interest", headers=c1_headers, json={"rate": 4.0, "pin": "1234", "remark": "Savings interest"})
    record("Apply Interest (/account/interest)", r.status_code == 200, f"New Balance: {r.json().get('new_balance_rupees') if r.status_code==200 else r.text}")

    # ---------------------------------------------------------
    # 9. ATM CARD LIFECYCLE
    # ---------------------------------------------------------
    print("\n--- 9. Testing ATM Debit Card Portal ---")
    # Issue Card
    r = session.post(f"{BASE_URL}/card/issue", headers=c1_headers, json={"pin": "1234"})
    if r.status_code in (200, 201):
        card_data = r.json()
        record("Issue 16-Digit Luhn ATM Card (/card/issue)", True, f"Card: {card_data.get('card_masked')} | Expiry: {card_data.get('card_expiry')}")
    elif r.status_code == 400 and ("already has an active" in r.text or "already issued" in r.text):
        record("Issue 16-Digit Luhn ATM Card (/card/issue)", True, "Card already issued and active")
    else:
        record("Issue 16-Digit Luhn ATM Card (/card/issue)", False, f"HTTP {r.status_code}: {r.text}")

    # Download Card PDF
    r = session.post(f"{BASE_URL}/card/download", headers=c1_headers, json={"pin": "1234"})
    record("Download ATM Card PDF (85.6x54mm)", r.status_code == 200 and r.content.startswith(b"%PDF"), f"{len(r.content)} bytes PDF")

    # Block Card
    r = session.post(f"{BASE_URL}/card/block", headers=c1_headers, json={"pin": "1234"})
    record("Block ATM Card (/card/block)", r.status_code == 200, r.json().get("message") if r.status_code==200 else r.text)

    # Blocked Card Download Rejection (HTTP 403 Forbidden)
    r = session.post(f"{BASE_URL}/card/download", headers=c1_headers, json={"pin": "1234"})
    record("Blocked Card Download Rejection", r.status_code == 403, "Refused download when blocked (HTTP 403)")

    # Unblock Card
    r = session.post(f"{BASE_URL}/card/unblock", headers=c1_headers, json={"pin": "1234"})
    record("Unblock ATM Card (/card/unblock)", r.status_code == 200, r.json().get("message") if r.status_code==200 else r.text)

    # ---------------------------------------------------------
    # 10. TRANSACTION HISTORY & PDF REPORTS
    # ---------------------------------------------------------
    print("\n--- 10. Testing History, Receipts & Statements ---")
    r = session.get(f"{BASE_URL}/transactions", headers=c1_headers)
    txns = r.json() if r.status_code == 200 else []
    record("Full Transaction History (/transactions)", r.status_code == 200, f"{len(txns)} transactions logged")

    r = session.get(f"{BASE_URL}/transactions/mini", headers=c1_headers)
    record("Mini Statement (/transactions/mini)", r.status_code == 200 and len(r.json()) <= 5, f"{len(r.json())} transactions")

    r = session.get(f"{BASE_URL}/transactions/counts", headers=c1_headers)
    counts = r.json() if r.status_code == 200 else {}
    record("Transaction Counts (/transactions/counts)", r.status_code == 200, f"Total: {counts.get('total')} transactions")

    # Download Transaction Receipt PDF for latest transaction
    if txns and len(txns) > 0:
        latest_txn_id = txns[0]["txn_id"]
        r = session.get(f"{BASE_URL}/transactions/{latest_txn_id}/receipt", headers=c1_headers)
        record(f"Download Transaction Receipt PDF ({latest_txn_id})", r.status_code == 200 and r.content.startswith(b"%PDF"), f"{len(r.content)} bytes PDF")

    # Download Account Statement PDF
    r = session.get(f"{BASE_URL}/account/statement", headers=c1_headers)
    record("Download Account Statement PDF", r.status_code == 200 and r.content.startswith(b"%PDF"), f"{len(r.content)} bytes PDF")

    # ---------------------------------------------------------
    # 11. ADMIN PORTAL OPERATIONS
    # ---------------------------------------------------------
    print("\n--- 11. Testing Admin Supervisory Operations ---")
    if admin_token:
        # List accounts
        r = session.get(f"{BASE_URL}/admin/accounts", headers=admin_headers)
        acc_list = r.json() if r.status_code == 200 else []
        record("Admin List Accounts (/admin/accounts)", r.status_code == 200 and len(acc_list) >= 2, f"{len(acc_list)} accounts found")

        # Total deposits
        r = session.get(f"{BASE_URL}/admin/total-deposits", headers=admin_headers)
        tot_dep = r.json() if r.status_code == 200 else {}
        record("Admin Total Deposits (/admin/total-deposits)", r.status_code == 200, f"Total: {tot_dep.get('total_deposits_rupees')}")

        # Account Lock and Unlock Test
        # 3 wrong password attempts on Customer 2
        for _ in range(3):
            session.post(f"{BASE_URL}/auth/login", json={"name": "PRIYA S", "password": "WrongPassword!999"})
        
        # Verify Customer 2 is locked (HTTP 403 Forbidden)
        r = session.post(f"{BASE_URL}/auth/login", json={"name": "PRIYA S", "password": "Password@123"})
        record("3-Strike Account Lockout Enforced", r.status_code == 403, "Account locked out after 3 wrong passwords (HTTP 403)")

        # Admin unlocks Customer 2
        r = session.post(f"{BASE_URL}/admin/unlock/{c2_acc}", headers=admin_headers)
        record("Admin Unlock Account (/admin/unlock/{acc})", r.status_code == 200, r.json().get("message") if r.status_code==200 else r.text)

        # Verify Customer 2 can log in again
        r = session.post(f"{BASE_URL}/auth/login", json={"name": "PRIYA S", "password": "Password@123"})
        record("Customer Successfully Relogins After Admin Unlock", r.status_code == 200, "Account unlocked and active")

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"  SYSTEM VERIFICATION COMPLETED: {passed} PASSED, {failed} FAILED")
    print("=" * 70)

    if failed == 0:
        print("\nALL PAGES, ASSETS, ENDPOINTS, AND SECURITY POLICIES ARE FULLY FUNCTIONAL!\n")
        return 0
    else:
        print(f"\n{failed} TEST(S) FAILED. Please review the details above.\n")
        return 1

if __name__ == "__main__":
    sys.exit(test_everything())
