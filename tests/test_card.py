"""
tests/test_card.py — Tests for /card/* endpoints
Tests: Luhn validity, issue, block, unblock, download (blocked card refused)
"""

import pytest
from tests.conftest import make_account, get_token
from app.security import luhn_valid, hash_pin
from app.models import Account


class TestCardIssue:
    def test_issue_card_success(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        resp = client.post(
            "/card/issue",
            json={"pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "card_masked" in data
        assert "**** **** ****" in data["card_masked"]
        assert "cvv" in data
        assert len(data["cvv"]) == 3
        assert data["cvv"].isdigit()
        assert data["card_expiry"]

    def test_issued_card_number_is_luhn_valid(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post(
            "/card/issue",
            json={"pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert luhn_valid(acc2.card_number), f"Card number {acc2.card_number} failed Luhn"

    def test_issue_second_card_rejected(self, client, db_session):
        """Cannot issue a second card when one is already ACTIVE."""
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400
        assert "active" in resp.json()["detail"].lower()

    def test_wrong_pin_on_issue_increments_counter(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "9999"}, headers={"Authorization": f"Bearer {token}"})
        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert acc2.pin_attempts == 1

    def test_cvv_not_stored_plaintext(self, client, db_session):
        """CVV in DB must be a bcrypt hash, not the plain 3-digit code."""
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        resp = client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        plain_cvv = resp.json()["cvv"]

        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert acc2.card_cvv_hash != plain_cvv
        assert acc2.card_cvv_hash.startswith("$2b$") or acc2.card_cvv_hash.startswith("$2a$")


class TestCardBlock:
    def test_block_active_card(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/card/block", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert acc2.card_status == "BLOCKED"

    def test_block_no_card_rejected(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        resp = client.post("/card/block", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400

    def test_block_already_blocked_rejected(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/card/block", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/card/block", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestCardUnblock:
    def test_unblock_blocked_card(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/card/block", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/card/unblock", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert acc2.card_status == "ACTIVE"


class TestCardDownload:
    def test_download_active_card_success(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/card/download", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_download_blocked_card_refused(self, client, db_session):
        """Blocked card download must be refused with 403."""
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/card/block", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/card/download", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "blocked" in resp.json()["detail"].lower()

    def test_download_no_card_rejected(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        resp = client.post("/card/download", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400

    def test_download_wrong_pin_refused(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/card/issue", json={"pin": "1234"}, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/card/download", json={"pin": "0000"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (401, 403)

