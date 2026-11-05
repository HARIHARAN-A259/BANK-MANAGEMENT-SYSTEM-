"""
tests/test_transactions.py — Tests for deposit, withdraw, transfer
Tests: limits, PIN lockout, atomic transfer rollback, daily limit
"""

import pytest
from tests.conftest import make_account, get_token
from app.models import Account, Transaction


class TestDeposit:
    def test_deposit_success(self, client, db_session):
        acc = make_account(db_session, balance=0)
        token = get_token(acc.account_number)
        resp = client.post(
            "/transactions/deposit",
            json={"amount": 1000.00},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Verify balance updated
        db_session.expire_all()
        acc2 = db_session.query(Account).filter(Account.account_number == acc.account_number).first()
        assert acc2.balance == 100_000   # ₹1000 = 100000 paise

    def test_deposit_logged_as_success(self, client, db_session):
        acc = make_account(db_session, balance=0)
        token = get_token(acc.account_number)
        client.post(
            "/transactions/deposit",
            json={"amount": 500.00},
            headers={"Authorization": f"Bearer {token}"},
        )
        txns = db_session.query(Transaction).filter(
            Transaction.account_number == acc.account_number,
            Transaction.type == "DEPOSIT",
        ).all()
        assert len(txns) == 1
        assert txns[0].status == "SUCCESS"
        assert txns[0].amount == 50_000  # ₹500 = 50000 paise

    def test_deposit_zero_rejected(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        resp = client.post(
            "/transactions/deposit",
            json={"amount": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_deposit_no_auth(self, client):
        resp = client.post("/transactions/deposit", json={"amount": 100})
        assert resp.status_code == 401


class TestWithdraw:
    def test_withdraw_success(self, client, db_session):
        acc = make_account(db_session, balance=100_000)
        token = get_token(acc.account_number)
        resp = client.post(
            "/transactions/withdraw",
            json={"amount": 500.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        db_session.expire_all()
        acc2 = db_session.query(Account).get(acc.account_number)
        assert acc2.balance == 50_000   # 100000 - 50000

    def test_withdraw_insufficient_balance(self, client, db_session):
        acc = make_account(db_session, balance=1_000)   # ₹10
        token = get_token(acc.account_number)
        resp = client.post(
            "/transactions/withdraw",
            json={"amount": 500.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "insufficient" in resp.json()["detail"].lower()

    def test_withdraw_exceeds_per_txn_limit(self, client, db_session):
        acc = make_account(db_session, balance=100_000_000)
        # Default withdraw_limit = ₹50,000 = 5,000,000 paise
        token = get_token(acc.account_number)
        resp = client.post(
            "/transactions/withdraw",
            json={"amount": 60000.00, "pin": "1234"},  # ₹60,000 > limit
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "limit" in resp.json()["detail"].lower()

    def test_withdraw_exceeds_daily_limit(self, client, db_session):
        """Daily limit is ₹20,000 = 2,000,000 paise."""
        acc = make_account(db_session, balance=100_000_000)
        token = get_token(acc.account_number)
        # First withdrawal: ₹15,000 (within per-txn and daily limit)
        client.post(
            "/transactions/withdraw",
            json={"amount": 15000.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Second: ₹10,000 — total would be ₹25,000 > daily ₹20,000
        resp = client.post(
            "/transactions/withdraw",
            json={"amount": 10000.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "daily" in resp.json()["detail"].lower()

    def test_withdraw_wrong_pin_lockout(self, client, db_session):
        """3 wrong PINs → pin_locked = True."""
        acc = make_account(db_session, balance=100_000)
        token = get_token(acc.account_number)
        for _ in range(3):
            client.post(
                "/transactions/withdraw",
                json={"amount": 100.00, "pin": "9999"},
                headers={"Authorization": f"Bearer {token}"},
            )
        # 4th attempt — now pin should be locked
        resp = client.post(
            "/transactions/withdraw",
            json={"amount": 100.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "locked" in resp.json()["detail"].lower()

    def test_failed_withdraw_logged(self, client, db_session):
        """A failed withdrawal (insufficient balance) must be logged."""
        acc = make_account(db_session, balance=100)   # ₹1
        token = get_token(acc.account_number)
        client.post(
            "/transactions/withdraw",
            json={"amount": 1000.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        txns = db_session.query(Transaction).filter(
            Transaction.account_number == acc.account_number,
            Transaction.type == "WITHDRAW",
            Transaction.status == "FAILED",
        ).all()
        assert len(txns) == 1


class TestTransfer:
    def test_transfer_success_atomic(self, client, db_session):
        """Transfer must debit sender and credit receiver in one transaction."""
        sender = make_account(db_session, name="sender", balance=100_000, account_number="10000001")
        receiver = make_account(db_session, name="receiver", balance=0, account_number="10000002")
        token = get_token(sender.account_number)

        resp = client.post(
            "/transactions/transfer",
            json={"to_account": receiver.account_number, "amount": 500.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        s = db_session.query(Account).get(sender.account_number)
        r = db_session.query(Account).get(receiver.account_number)
        assert s.balance == 50_000     # 100000 - 50000
        assert r.balance == 50_000     # 0 + 50000

    def test_transfer_creates_two_records_same_txn_id(self, client, db_session):
        """TRANSFER_OUT and TRANSFER_IN must share the same TXN ID."""
        sender = make_account(db_session, name="sndr", balance=100_000, account_number="10000001")
        receiver = make_account(db_session, name="rcvr", balance=0, account_number="10000002")
        token = get_token(sender.account_number)

        client.post(
            "/transactions/transfer",
            json={"to_account": receiver.account_number, "amount": 100.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )

        txns = db_session.query(Transaction).filter(
            Transaction.txn_id == "TXN-00001"
        ).all()
        assert len(txns) == 2
        types = {t.type for t in txns}
        assert types == {"TRANSFER_OUT", "TRANSFER_IN"}

    def test_self_transfer_rejected(self, client, db_session):
        acc = make_account(db_session, balance=100_000)
        token = get_token(acc.account_number)
        resp = client.post(
            "/transactions/transfer",
            json={"to_account": acc.account_number, "amount": 100.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "self" in resp.json()["detail"].lower() or "own" in resp.json()["detail"].lower()

    def test_transfer_to_inactive_receiver_rejected(self, client, db_session):
        sender = make_account(db_session, name="actsndr", balance=100_000, account_number="10000001")
        receiver = make_account(db_session, name="inactrcvr", balance=0, account_number="10000002")
        receiver.active = False
        db_session.commit()

        token = get_token(sender.account_number)
        resp = client.post(
            "/transactions/transfer",
            json={"to_account": receiver.account_number, "amount": 100.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_transfer_exceeds_limit(self, client, db_session):
        """Transfer > transfer_limit (₹1,00,000) must be rejected."""
        sender = make_account(db_session, name="bigsend", balance=1_000_000_000, account_number="10000001")
        receiver = make_account(db_session, name="bigrcv", balance=0, account_number="10000002")
        token = get_token(sender.account_number)
        resp = client.post(
            "/transactions/transfer",
            json={"to_account": receiver.account_number, "amount": 150000.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "limit" in resp.json()["detail"].lower()

    def test_transfer_rollback_on_insufficient_balance(self, client, db_session):
        """When sender has insufficient balance, receiver balance must be unchanged."""
        sender = make_account(db_session, name="poorsndr", balance=1_000, account_number="10000001")
        receiver = make_account(db_session, name="rcvr2", balance=0, account_number="10000002")
        token = get_token(sender.account_number)

        resp = client.post(
            "/transactions/transfer",
            json={"to_account": receiver.account_number, "amount": 500.00, "pin": "1234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

        db_session.expire_all()
        r = db_session.query(Account).get(receiver.account_number)
        assert r.balance == 0, "Receiver balance must not change when transfer fails"


class TestTransactionHistory:
    def test_full_history(self, client, db_session):
        acc = make_account(db_session)
        token = get_token(acc.account_number)
        client.post("/transactions/deposit", json={"amount": 100}, headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/transactions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_mini_statement_max_5(self, client, db_session):
        acc = make_account(db_session, balance=10_000_000)
        token = get_token(acc.account_number)
        for i in range(8):
            client.post("/transactions/deposit", json={"amount": 10}, headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/transactions/mini", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()) <= 5

    def test_counts_endpoint(self, client, db_session):
        acc = make_account(db_session, balance=10_000_000)
        token = get_token(acc.account_number)
        client.post("/transactions/deposit", json={"amount": 100}, headers={"Authorization": f"Bearer {token}"})
        client.post("/transactions/deposit", json={"amount": 200}, headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/transactions/counts", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["deposits"] == 2

