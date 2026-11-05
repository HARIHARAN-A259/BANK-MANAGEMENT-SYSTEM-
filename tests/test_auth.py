"""
tests/test_auth.py — Tests for /auth/* endpoints
Tests: register, login, lockout after 3 failed attempts
"""

import pytest
from tests.conftest import make_account, get_token


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "name": "alice",
            "password": "Alice@1234",
            "pin": "4321",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "account_number" in data
        assert len(data["account_number"]) == 8
        assert data["name"] == "alice"

    def test_register_weak_password(self, client):
        resp = client.post("/auth/register", json={
            "name": "bob",
            "password": "weakpass",
            "pin": "1234",
        })
        assert resp.status_code == 422 or resp.status_code == 400

    def test_register_invalid_name_digits(self, client):
        resp = client.post("/auth/register", json={
            "name": "alice123",
            "password": "Alice@1234",
            "pin": "1234",
        })
        assert resp.status_code == 422

    def test_register_duplicate_name(self, client, db_session):
        make_account(db_session, name="dupuser")
        resp = client.post("/auth/register", json={
            "name": "dupuser",
            "password": "Dup@12345",
            "pin": "0000",
        })
        assert resp.status_code == 400
        assert "taken" in resp.json()["detail"].lower()

    def test_register_pin_not_4_digits(self, client):
        resp = client.post("/auth/register", json={
            "name": "charlie",
            "password": "Charlie@1",
            "pin": "12",
        })
        assert resp.status_code == 422

    def test_register_pin_non_numeric(self, client):
        resp = client.post("/auth/register", json={
            "name": "dave",
            "password": "Dave@1234",
            "pin": "abcd",
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client, db_session):
        make_account(db_session, name="loginuser", password="Login@1234")
        resp = client.post("/auth/login", json={
            "name": "loginuser",
            "password": "Login@1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, db_session):
        make_account(db_session, name="wrongpw")
        resp = client.post("/auth/login", json={
            "name": "wrongpw",
            "password": "Wrong@1234",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={
            "name": "ghost",
            "password": "Ghost@1234",
        })
        assert resp.status_code == 401

    def test_login_lockout_after_3_failures(self, client, db_session):
        """Account must be locked after exactly 3 wrong passwords."""
        make_account(db_session, name="lockme", password="Real@1234")

        for i in range(3):
            r = client.post("/auth/login", json={
                "name": "lockme",
                "password": "Wrong@9999",
            })
            if i < 2:
                assert r.status_code == 401
            else:
                # 3rd attempt locks the account
                assert r.status_code in (401, 403)

        # Now even correct password is refused
        r = client.post("/auth/login", json={
            "name": "lockme",
            "password": "Real@1234",
        })
        assert r.status_code == 403
        assert "locked" in r.json()["detail"].lower()

    def test_lockout_persists_across_requests(self, client, db_session):
        """Failed login counter persists in DB between requests."""
        make_account(db_session, name="persist")
        # 2 wrong attempts
        client.post("/auth/login", json={"name": "persist", "password": "X@12345"})
        client.post("/auth/login", json={"name": "persist", "password": "X@12345"})

        # Reload account from DB and verify counter
        db_session.expire_all()
        from app.models import Account
        acc = db_session.query(Account).filter(Account.name == "persist").first()
        assert acc.failed_login_count == 2

    def test_login_counter_resets_on_success(self, client, db_session):
        """Failed counter resets to 0 after a successful login."""
        make_account(db_session, name="resetme", password="Real@1234")
        # 1 wrong attempt
        client.post("/auth/login", json={"name": "resetme", "password": "Wrong@1"})
        # Correct login
        client.post("/auth/login", json={"name": "resetme", "password": "Real@1234"})
        # Verify reset
        db_session.expire_all()
        from app.models import Account
        acc = db_session.query(Account).filter(Account.name == "resetme").first()
        assert acc.failed_login_count == 0

    def test_inactive_account_cannot_login(self, client, db_session):
        acc = make_account(db_session, name="inactive")
        acc.active = False
        db_session.commit()
        resp = client.post("/auth/login", json={
            "name": "inactive",
            "password": "Test@1234",
        })
        assert resp.status_code == 403


class TestLogout:
    def test_logout(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        resp = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "logged out" in resp.json()["message"].lower()

    def test_logout_no_token(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code == 401

