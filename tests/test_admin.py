"""
tests/test_admin.py — Tests for /admin/* endpoints
Tests: admin login, list accounts, unlock, total deposits
"""

import pytest
from tests.conftest import make_account, get_token, get_admin_token
from app.models import Account


class TestAdminLogin:
    def test_admin_login_success(self, client):
        resp = client.post("/admin/login", json={"password": "Admin@1234"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_admin_login_wrong_password(self, client):
        resp = client.post("/admin/login", json={"password": "wrong"})
        assert resp.status_code == 401

    def test_user_token_cannot_access_admin(self, client, db_session):
        """A user JWT must be rejected on admin endpoints."""
        acc = make_account(db_session)
        user_token = get_token(acc.account_number)
        resp = client.get(
            "/admin/accounts",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 401


class TestAdminAccounts:
    def test_list_accounts(self, client, db_session):
        make_account(db_session, name="user1", account_number="10000001")
        make_account(db_session, name="user2", account_number="10000002")
        token = get_admin_token()
        resp = client.get("/admin/accounts", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        accounts = resp.json()
        names = [a["name"] for a in accounts]
        assert "user1" in names
        assert "user2" in names

    def test_list_accounts_no_auth(self, client):
        resp = client.get("/admin/accounts")
        assert resp.status_code == 401


class TestAdminUnlock:
    def test_unlock_locked_account(self, client, db_session):
        acc = make_account(db_session, name="lockedone")
        acc.locked = True
        acc.failed_login_count = 3
        db_session.commit()

        token = get_admin_token()
        resp = client.post(
            f"/admin/unlock/{acc.account_number}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert acc2.locked is False
        assert acc2.failed_login_count == 0

    def test_unlock_pin_locked(self, client, db_session):
        acc = make_account(db_session, name="pinlocked")
        acc.pin_locked = True
        acc.pin_attempts = 3
        db_session.commit()

        token = get_admin_token()
        resp = client.post(
            f"/admin/unlock/{acc.account_number}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert acc2.pin_locked is False
        assert acc2.pin_attempts == 0

    def test_unlock_nonexistent_account(self, client, db_session):
        token = get_admin_token()
        resp = client.post(
            "/admin/unlock/99999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestAdminTotalDeposits:
    def test_total_deposits_zero(self, client, db_session):
        token = get_admin_token()
        resp = client.get("/admin/total-deposits", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_deposits_paise"] == 0
        assert data["count"] == 0

    def test_total_deposits_after_transactions(self, client, db_session):
        acc = make_account(db_session, balance=0)
        user_token = get_token(acc.account_number)
        # Deposit ₹1000 twice
        client.post("/transactions/deposit", json={"amount": 1000}, headers={"Authorization": f"Bearer {user_token}"})
        client.post("/transactions/deposit", json={"amount": 500}, headers={"Authorization": f"Bearer {user_token}"})

        admin_token = get_admin_token()
        resp = client.get("/admin/total-deposits", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_deposits_paise"] == 150_000   # ₹1500 = 150000 paise
        assert data["count"] == 2

