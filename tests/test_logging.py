"""Tests for secure logging utilities."""

import logging

import pytest

from eero.logging import (
    SecureLoggerAdapter,
    _is_sensitive_key,
    _redact_dict,
    _redact_value,
    add_sensitive_pattern,
    get_secure_logger,
    redact_sensitive,
)


class TestIsSensitiveKey:
    """Tests for _is_sensitive_key function."""

    def test_detects_token_variations(self):
        """Should detect various token field names."""
        assert _is_sensitive_key("token") is True
        assert _is_sensitive_key("user_token") is True
        assert _is_sensitive_key("access_token") is True
        assert _is_sensitive_key("refresh_token") is True
        assert _is_sensitive_key("TOKEN") is True
        assert _is_sensitive_key("User_Token") is True

    def test_detects_password_variations(self):
        """Should detect password field names."""
        assert _is_sensitive_key("password") is True
        assert _is_sensitive_key("passwd") is True
        assert _is_sensitive_key("user_password") is True
        assert _is_sensitive_key("PASSWORD") is True

    def test_detects_secret_variations(self):
        """Should detect secret field names."""
        assert _is_sensitive_key("secret") is True
        assert _is_sensitive_key("client_secret") is True
        assert _is_sensitive_key("api_secret") is True

    def test_detects_key_variations(self):
        """Should detect key field names."""
        assert _is_sensitive_key("key") is True
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("apikey") is True
        assert _is_sensitive_key("private_key") is True

    def test_detects_session_variations(self):
        """Should detect session field names."""
        assert _is_sensitive_key("session") is True
        assert _is_sensitive_key("session_id") is True
        assert _is_sensitive_key("cookie") is True

    def test_detects_auth_variations(self):
        """Should detect auth field names."""
        assert _is_sensitive_key("auth") is True
        assert _is_sensitive_key("authorization") is True
        assert _is_sensitive_key("bearer") is True

    def test_non_sensitive_keys(self):
        """Should not flag non-sensitive keys."""
        assert _is_sensitive_key("name") is False
        assert _is_sensitive_key("email") is False
        assert _is_sensitive_key("status") is False
        assert _is_sensitive_key("id") is False
        assert _is_sensitive_key("count") is False
        assert _is_sensitive_key("network_id") is False


class TestRedactValue:
    """Tests for _redact_value function."""

    def test_redacts_none(self):
        """Should handle None values."""
        assert _redact_value(None) == "[NONE]"

    def test_redacts_empty_string(self):
        """Should handle empty strings."""
        assert _redact_value("") == "[EMPTY]"

    def test_redacts_short_string(self):
        """Should redact short strings without showing characters."""
        assert _redact_value("abc") == "[REDACTED:3chars]"
        assert _redact_value("abcd") == "[REDACTED:4chars]"

    def test_redacts_long_string(self):
        """Should show first chars of longer strings."""
        result = _redact_value("secret123456")
        assert result.startswith("secr")
        assert "[REDACTED:12chars]" in result

    def test_redacts_boolean(self):
        """Should redact boolean values."""
        assert _redact_value(True) == "[REDACTED:bool]"
        assert _redact_value(False) == "[REDACTED:bool]"

    def test_redacts_numbers(self):
        """Should redact numeric values."""
        assert _redact_value(12345) == "[REDACTED:number]"
        assert _redact_value(3.14) == "[REDACTED:number]"

    def test_custom_visible_chars(self):
        """Should respect custom visible_chars parameter."""
        result = _redact_value("secret123456", visible_chars=6)
        assert result.startswith("secret")


class TestRedactDict:
    """Tests for _redact_dict function."""

    def test_redacts_sensitive_keys(self):
        """Should redact values with sensitive keys."""
        data = {"user_token": "abc123", "name": "John"}
        result = _redact_dict(data)

        assert "abc123" not in str(result["user_token"])
        assert "[REDACTED" in result["user_token"]
        assert result["name"] == "John"

    def test_preserves_non_sensitive_keys(self):
        """Should preserve non-sensitive values."""
        data = {"status": "ok", "count": 5, "items": ["a", "b"]}
        result = _redact_dict(data)

        assert result["status"] == "ok"
        assert result["count"] == 5
        assert result["items"] == ["a", "b"]

    def test_handles_nested_dicts(self):
        """Should recursively redact nested dictionaries."""
        data = {
            "user": {
                "name": "John",
                "password": "secret123",
            },
            "session_id": "xyz789",
        }
        result = _redact_dict(data)

        assert result["user"]["name"] == "John"
        assert "[REDACTED" in result["user"]["password"]
        assert "[REDACTED" in result["session_id"]

    def test_handles_list_of_dicts(self):
        """Should redact dictionaries within lists."""
        data = {
            "users": [
                {"name": "John", "token": "abc"},
                {"name": "Jane", "token": "xyz"},
            ]
        }
        result = _redact_dict(data)

        assert result["users"][0]["name"] == "John"
        assert "[REDACTED" in result["users"][0]["token"]
        assert result["users"][1]["name"] == "Jane"
        assert "[REDACTED" in result["users"][1]["token"]

    def test_handles_empty_dict(self):
        """Should handle empty dictionaries."""
        assert _redact_dict({}) == {}


class TestRedactSensitive:
    """Tests for redact_sensitive function."""

    def test_handles_dict(self):
        """Should redact dictionaries."""
        data = {"token": "secret"}
        result = redact_sensitive(data)
        assert "[REDACTED" in result["token"]

    def test_passes_through_non_dict(self):
        """Should pass through non-dict values."""
        assert redact_sensitive("hello") == "hello"
        assert redact_sensitive(123) == 123
        assert redact_sensitive(None) is None


class TestSecureLoggerAdapter:
    """Tests for SecureLoggerAdapter class."""

    @pytest.fixture
    def logger(self):
        """Create a test logger."""
        return logging.getLogger("test.secure")

    @pytest.fixture
    def secure_logger(self, logger):
        """Create a secure logger adapter."""
        return SecureLoggerAdapter(logger)

    def test_redacts_dict_args(self, secure_logger, caplog):
        """Should redact sensitive data in dict arguments."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", {"user_token": "secret123", "status": "ok"})

        assert "secret123" not in caplog.text
        assert "status" in caplog.text
        assert "ok" in caplog.text

    def test_preserves_non_sensitive_args(self, secure_logger, caplog):
        """Should preserve non-sensitive arguments."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("User: %s, Count: %d", "John", 5)

        assert "John" in caplog.text
        assert "5" in caplog.text

    def test_all_log_levels_work(self, secure_logger, caplog):
        """Should work at all log levels."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Debug: %s", {"token": "a"})
            secure_logger.info("Info: %s", {"token": "b"})
            secure_logger.warning("Warning: %s", {"token": "c"})
            secure_logger.error("Error: %s", {"token": "d"})

        # All should have redacted the token
        for record in caplog.records:
            assert "token" in record.message.lower()
            # Original values should not appear
            for char in ["a", "b", "c", "d"]:
                if f"'token': '{char}'" in record.message:
                    pytest.fail(f"Token value '{char}' was not redacted")


class TestGetSecureLogger:
    """Tests for get_secure_logger function."""

    def test_returns_secure_adapter(self):
        """Should return a SecureLoggerAdapter."""
        logger = get_secure_logger("test.module")
        assert isinstance(logger, SecureLoggerAdapter)

    def test_caches_loggers(self):
        """Should cache and return same logger for same name."""
        logger1 = get_secure_logger("test.cached")
        logger2 = get_secure_logger("test.cached")
        assert logger1 is logger2

    def test_different_names_different_loggers(self):
        """Should return different loggers for different names."""
        logger1 = get_secure_logger("test.one")
        logger2 = get_secure_logger("test.two")
        assert logger1 is not logger2

    def test_custom_patterns(self):
        """Should accept custom sensitive patterns."""
        patterns = frozenset({"custom_field"})
        logger = get_secure_logger("test.custom", sensitive_patterns=patterns)
        assert logger._sensitive_patterns == patterns


class TestAddSensitivePattern:
    """Tests for add_sensitive_pattern function."""

    def test_adds_pattern(self):
        """Should add pattern to default set."""
        patterns = add_sensitive_pattern("my_custom_secret")
        assert "my_custom_secret" in patterns
        assert "token" in patterns  # Original patterns preserved

    def test_case_insensitive(self):
        """Should lowercase the pattern."""
        patterns = add_sensitive_pattern("MY_PATTERN")
        assert "my_pattern" in patterns
