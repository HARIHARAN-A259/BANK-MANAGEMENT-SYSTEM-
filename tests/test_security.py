"""
tests/test_security.py — Unit tests for security module
Tests: password rules, bcrypt, JWT, Luhn check, card masking
"""

import pytest
from app.security import (
    validate_password, hash_password, verify_password,
    hash_pin, verify_pin,
    generate_luhn_card_number, luhn_valid, mask_card, card_number_in_groups,
    create_access_token, decode_access_token,
    format_txn_id, generate_account_number,
    CASHIO_BIN,
)


# ===========================================================================
# Password rules
# ===========================================================================

class TestPasswordRules:
    def test_valid_password(self):
        validate_password("Test@1234")   # should not raise

    def test_too_short(self):
        with pytest.raises(ValueError, match="8 characters"):
            validate_password("Ab@1")

    def test_no_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            validate_password("test@1234")

    def test_no_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_password("TEST@1234")

    def test_no_digit(self):
        with pytest.raises(ValueError, match="digit"):
            validate_password("Test@abcd")

    def test_no_special(self):
        with pytest.raises(ValueError, match="special"):
            validate_password("TestTest1")

    def test_exactly_8_chars_valid(self):
        validate_password("Aa@12345")   # exactly 8 chars — should pass


# ===========================================================================
# bcrypt password hashing
# ===========================================================================

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = hash_password("Test@1234")
        assert h != "Test@1234"

    def test_verify_correct_password(self):
        h = hash_password("Test@1234")
        assert verify_password("Test@1234", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("Test@1234")
        assert verify_password("Wrong@1234", h) is False

    def test_different_hashes_same_password(self):
        # bcrypt generates different salts each time
        h1 = hash_password("Test@1234")
        h2 = hash_password("Test@1234")
        assert h1 != h2

    def test_hash_starts_with_bcrypt_prefix(self):
        h = hash_password("Test@1234")
        assert h.startswith("$2b$") or h.startswith("$2a$")


# ===========================================================================
# PIN hashing
# ===========================================================================

class TestPINHashing:
    def test_correct_pin(self):
        h = hash_pin("1234")
        assert verify_pin("1234", h) is True

    def test_wrong_pin(self):
        h = hash_pin("1234")
        assert verify_pin("5678", h) is False

    def test_pin_hash_salted(self):
        h1 = hash_pin("1234")
        h2 = hash_pin("1234")
        assert h1 != h2


# ===========================================================================
# JWT
# ===========================================================================

class TestJWT:
    def test_encode_decode_roundtrip(self):
        token = create_access_token({"sub": "10000001", "type": "user"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "10000001"
        assert payload["type"] == "user"

    def test_invalid_token_returns_none(self):
        assert decode_access_token("not.a.real.token") is None

    def test_tampered_token_returns_none(self):
        token = create_access_token({"sub": "10000001", "type": "user"})
        tampered = token[:-5] + "XXXXX"
        assert decode_access_token(tampered) is None

    def test_admin_token_type(self):
        token = create_access_token({"sub": "admin", "type": "admin"})
        payload = decode_access_token(token)
        assert payload["type"] == "admin"


# ===========================================================================
# Luhn check
# ===========================================================================

class TestLuhn:
    def test_generated_card_is_valid(self):
        card = generate_luhn_card_number()
        assert luhn_valid(card), f"Generated card {card} failed Luhn check"

    def test_generated_card_starts_with_bin(self):
        card = generate_luhn_card_number()
        assert card.startswith(CASHIO_BIN)

    def test_generated_card_is_16_digits(self):
        card = generate_luhn_card_number()
        assert len(card) == 16
        assert card.isdigit()

    def test_known_valid_luhn(self):
        # Visa test number — always valid
        assert luhn_valid("4532015112830366") is True

    def test_known_invalid_luhn(self):
        # Flip last digit
        assert luhn_valid("4532015112830367") is False

    def test_multiple_generated_cards_all_valid(self):
        for _ in range(20):
            assert luhn_valid(generate_luhn_card_number())

    def test_non_digit_string_invalid(self):
        assert luhn_valid("453201511283ABCD") is False

    def test_wrong_length_invalid(self):
        assert luhn_valid("123456789") is False


# ===========================================================================
# Card masking
# ===========================================================================

class TestCardMasking:
    def test_mask_shows_last_4(self):
        assert mask_card("4532001234567890") == "**** **** **** 7890"

    def test_mask_hides_first_12(self):
        m = mask_card("4532001234567890")
        assert "453200" not in m

    def test_card_in_groups(self):
        assert card_number_in_groups("4532001234567890") == "4532 0012 3456 7890"


# ===========================================================================
# ID formatting
# ===========================================================================

class TestIDFormatting:
    def test_txn_id_format(self):
        assert format_txn_id(1) == "TXN-00001"
        assert format_txn_id(99999) == "TXN-99999"
        assert format_txn_id(100000) == "TXN-100000"

    def test_account_number_8_digits(self):
        num = generate_account_number(10000001)
        assert len(num) == 8
        assert num == "10000001"

