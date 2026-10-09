"""Tests for secure logging utilities."""

import copy
import logging
from types import MappingProxyType
from unittest.mock import patch

import pytest

from eero.logging import (
    _MAX_REDACTION_DEPTH,
    _UNTRAVERSABLE_PLACEHOLDER,
    DEFAULT_SENSITIVE_PATTERNS,
    SecureLoggerAdapter,
    _get_sensitive_regex,
    _is_sensitive_key,
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
        assert _is_sensitive_key("status") is False
        assert _is_sensitive_key("id") is False
        assert _is_sensitive_key("count") is False
        assert _is_sensitive_key("network_id") is False

    def test_detects_identifier_variations(self):
        """Should detect identifier field names that could leak a submitted identifier."""
        assert _is_sensitive_key("login") is True
        assert _is_sensitive_key("email") is True
        assert _is_sensitive_key("phone") is True
        assert _is_sensitive_key("sms") is True
        assert _is_sensitive_key("serial") is True
        assert _is_sensitive_key("mac") is True
        assert _is_sensitive_key("mac_address") is True
        assert _is_sensitive_key("ssid") is True


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
    """Tests for redact_sensitive applied to dictionaries."""

    def test_redacts_sensitive_keys(self):
        """Should redact values with sensitive keys."""
        data = {"user_token": "abc123", "name": "John"}
        result = redact_sensitive(data)

        assert "abc123" not in str(result["user_token"])
        assert "[REDACTED" in result["user_token"]
        assert result["name"] == "John"

    def test_preserves_non_sensitive_keys(self):
        """Should preserve non-sensitive values."""
        data = {"status": "ok", "count": 5, "items": ["a", "b"]}
        result = redact_sensitive(data)

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
        result = redact_sensitive(data)

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
        result = redact_sensitive(data)

        assert result["users"][0]["name"] == "John"
        assert "[REDACTED" in result["users"][0]["token"]
        assert result["users"][1]["name"] == "Jane"
        assert "[REDACTED" in result["users"][1]["token"]

    def test_handles_empty_dict(self):
        """Should handle empty dictionaries."""
        assert redact_sensitive({}) == {}


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


# ========================== Regex Cache Isolation Tests (item 6) ==========================


class TestSensitiveRegexCacheIsolation:
    """A logger built with a narrow/custom pattern set must not narrow later default loggers."""

    def test_get_sensitive_regex_does_not_leak_across_pattern_sets(self):
        """Each distinct pattern set gets its own independently-cached regex."""
        narrow = frozenset({"foo_only_field"})
        regex_narrow = _get_sensitive_regex(narrow)
        assert regex_narrow.search("token") is None
        assert regex_narrow.search("foo_only_field") is not None

        regex_default = _get_sensitive_regex(DEFAULT_SENSITIVE_PATTERNS)
        assert regex_default.search("token") is not None

        # The narrow lookup is unaffected by having built the default one
        # afterwards -- proves there is no shared mutable global being
        # overwritten between the two calls.
        assert _get_sensitive_regex(narrow) is regex_narrow
        assert regex_narrow.search("token") is None

    def test_custom_pattern_logger_does_not_narrow_later_default_loggers(self):
        """Building a logger with a narrow custom pattern set first must not affect later default loggers."""
        narrow_patterns = frozenset({"foo_only_field"})
        get_secure_logger("test.narrow.custom.logger", sensitive_patterns=narrow_patterns)

        # A default logger built afterwards must still redact every default
        # pattern -- the narrow logger's regex must never have overwritten a
        # shared global cache slot.
        assert _is_sensitive_key("token", DEFAULT_SENSITIVE_PATTERNS) is True
        assert _is_sensitive_key("password", DEFAULT_SENSITIVE_PATTERNS) is True
        assert _is_sensitive_key("token", narrow_patterns) is False


# ================ Zero-Visibility Redaction for Credentials Tests (item 7) ================


class TestRedactDictZeroVisibilityForCredentials:
    """Keys matching token/credential patterns must never show a value prefix via redact_sensitive."""

    @pytest.mark.parametrize(
        "key", ["token", "user_token", "session_id", "password", "api_key", "secret", "cookie"]
    )
    def test_credential_like_keys_show_length_only(self, key):
        """Should redact credential-shaped keys to length-only, with no leading characters."""
        value = "supersecretvalue1234"
        data = {key: value}
        result = redact_sensitive(data)

        assert result[key] == f"[REDACTED:{len(value)}chars]"
        assert "supe" not in result[key]

    def test_identifier_pattern_keys_still_use_visible_chars(self):
        """Identifier-shaped keys (not credential-shaped) keep the normal partial-prefix redaction."""
        data = {"email": "user@example.test-domain-value"}
        result = redact_sensitive(data)

        assert result["email"].startswith("user")

    def test_redact_value_called_directly_is_unaffected(self):
        """Calling _redact_value directly (outside redact_sensitive) keeps its own visible_chars default."""
        result = _redact_value("secret123456")
        assert result.startswith("secr")
        assert "[REDACTED:12chars]" in result


# ================ Recursive redaction coverage (list/tuple/extra/log/keys/cycles) ================

CANARY = "CANARY-tok-5b2e"


def _record_text(caplog) -> str:
    """Return the formatted message and every attribute of every captured record as text."""
    return "\n".join(f"{record.getMessage()}\n{vars(record)!r}" for record in caplog.records)


class TestRedactSensitiveContainers:
    """redact_sensitive walks mappings, lists and tuples to any (capped) depth."""

    def test_top_level_list_of_dicts_is_redacted(self):
        """A list of dicts at the top level is redacted element by element."""
        result = redact_sensitive([{"token": CANARY, "name": "n"}])

        assert isinstance(result, list)
        assert CANARY not in repr(result)
        assert result[0]["name"] == "n"

    def test_top_level_tuple_of_dicts_is_redacted_and_stays_a_tuple(self):
        """A tuple stays a tuple while its dict elements are redacted."""
        result = redact_sensitive(({"token": CANARY},))

        assert isinstance(result, tuple)
        assert CANARY not in repr(result)

    def test_list_in_list_in_dict_is_redacted(self):
        """Lists nested in lists nested in a dict are reached."""
        result = redact_sensitive({"outer": [[{"token": CANARY}]]})

        assert CANARY not in repr(result)
        assert isinstance(result["outer"], list)
        assert isinstance(result["outer"][0], list)

    def test_tuple_in_dict_is_redacted(self):
        """A tuple value of a dict is reached and keeps its type."""
        result = redact_sensitive({"outer": ({"token": CANARY},)})

        assert CANARY not in repr(result)
        assert isinstance(result["outer"], tuple)

    def test_non_dict_mapping_is_redacted_into_a_plain_dict(self):
        """Any Mapping is walked; the redacted copy is a plain dict."""
        result = redact_sensitive(MappingProxyType({"token": CANARY, "name": "n"}))

        assert type(result) is dict
        assert CANARY not in repr(result)
        assert result["name"] == "n"

    def test_scalars_and_strings_pass_through_unchanged(self):
        """Values that are not containers are returned as-is."""
        assert redact_sensitive("s=abc") == "s=abc"
        assert redact_sensitive(None) is None
        assert redact_sensitive(b"x") == b"x"

    def test_non_string_keys_do_not_raise_and_are_preserved(self):
        """Non-string keys are matched via str(key) and kept as the original objects."""
        result = redact_sensitive({1: "x", ("a", "token"): CANARY, None: {"token": CANARY}})

        assert result[1] == "x"
        assert CANARY not in repr(result)
        assert ("a", "token") in result
        assert None in result

    def test_cyclic_dict_is_replaced_by_placeholder(self):
        """A dict that contains itself yields the placeholder instead of recursing forever."""
        data = {"token": CANARY, "name": "n"}
        data["self"] = data

        result = redact_sensitive(data)

        assert result["self"] == _UNTRAVERSABLE_PLACEHOLDER
        assert result["name"] == "n"
        assert CANARY not in repr(result)

    def test_cyclic_list_is_replaced_by_placeholder(self):
        """A list that contains itself yields the placeholder."""
        data = [{"token": CANARY}]
        data.append(data)

        result = redact_sensitive(data)

        assert result[1] == _UNTRAVERSABLE_PLACEHOLDER
        assert CANARY not in repr(result)

    def test_mutual_cycle_across_types_is_replaced_by_placeholder(self):
        """A cycle that passes through a dict and a list terminates."""
        inner = [{"token": CANARY}]
        outer = {"items": inner}
        inner.append(outer)

        result = redact_sensitive(outer)

        assert result["items"][1] == _UNTRAVERSABLE_PLACEHOLDER
        assert CANARY not in repr(result)

    def test_shared_non_cyclic_reference_is_redacted_not_replaced(self):
        """The same object reachable twice (a DAG, no cycle) is redacted both times."""
        shared = {"token": CANARY, "name": "n"}

        result = redact_sensitive([shared, {"again": shared}])

        assert _UNTRAVERSABLE_PLACEHOLDER not in repr(result)
        assert result[0]["name"] == "n"
        assert result[1]["again"]["name"] == "n"
        assert CANARY not in repr(result)

    @staticmethod
    def _nest(levels: int, leaf):
        """Wrap ``leaf`` in ``levels`` single-element lists."""
        value = leaf
        for _ in range(levels):
            value = [value]
        return value

    def test_nesting_at_the_cap_is_still_walked(self):
        """A leaf container at the last permitted depth is redacted, not replaced."""
        data = self._nest(_MAX_REDACTION_DEPTH - 1, {"token": CANARY, "name": "n"})

        text = repr(redact_sensitive(data))

        assert _UNTRAVERSABLE_PLACEHOLDER not in text
        assert "'name': 'n'" in text
        assert CANARY not in text

    def test_nesting_beyond_the_cap_is_replaced_by_placeholder(self):
        """Anything below the cap is replaced wholesale, including non-sensitive siblings."""
        data = self._nest(_MAX_REDACTION_DEPTH, {"token": CANARY, "note": CANARY})

        text = repr(redact_sensitive(data))

        assert _UNTRAVERSABLE_PLACEHOLDER in text
        assert CANARY not in text

    def test_very_deep_nesting_does_not_raise(self):
        """Nesting far past the interpreter's recursion limit still terminates."""
        data = self._nest(5000, {"token": CANARY})

        assert CANARY not in repr(redact_sensitive(data))

    def test_argument_is_not_mutated_and_result_is_new(self):
        """Redaction builds new containers; the caller's objects keep their values and identity."""
        inner = {"token": CANARY, "tags": ["a"]}
        data = {"list": [inner], "tuple": (inner,), "n": 1}
        snapshot = copy.deepcopy(data)

        result = redact_sensitive(data)

        assert data == snapshot
        assert data["list"][0] is inner
        assert inner["token"] == CANARY
        assert result is not data
        assert result["list"] is not data["list"]
        assert result["list"][0] is not inner
        assert result["tuple"] is not data["tuple"]
        assert result["list"][0]["tags"] is not inner["tags"]

    def test_cyclic_argument_is_not_mutated(self):
        """A cyclic structure keeps its cycle after being redacted."""
        data = {"token": CANARY}
        data["self"] = data

        redact_sensitive(data)

        assert data["self"] is data
        assert data["token"] == CANARY


class TestSecureLoggerRedactionCoverage:
    """Every route into the adapter redacts, and a disabled level costs nothing."""

    @pytest.fixture
    def secure_logger(self):
        """Create a secure logger adapter over a dedicated logger."""
        return SecureLoggerAdapter(logging.getLogger("test.secure.coverage"))

    def test_top_level_list_argument(self, secure_logger, caplog):
        """A list of dicts passed as a format argument is redacted."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", [{"token": CANARY}])

        assert "Data: [{'token': '[REDACTED:" in caplog.text
        assert CANARY not in _record_text(caplog)

    def test_top_level_tuple_argument(self, secure_logger, caplog):
        """A tuple of dicts passed as a format argument is redacted."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", ({"token": CANARY},))

        assert CANARY not in _record_text(caplog)

    def test_list_in_list_in_dict_argument(self, secure_logger, caplog):
        """Lists nested in lists nested in a dict are redacted."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", {"outer": [[{"token": CANARY}]]})

        assert CANARY not in _record_text(caplog)

    def test_tuple_in_dict_argument(self, secure_logger, caplog):
        """A tuple inside a dict is redacted."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", {"outer": ({"token": CANARY},)})

        assert CANARY not in _record_text(caplog)

    def test_extra_is_redacted_on_the_record(self, secure_logger, caplog):
        """The extra= dict of a level method is redacted before it reaches the record."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.info(
                "Hello", extra={"token": CANARY, "nested": [{"password": CANARY}], "plain": "ok"}
            )

        (record,) = caplog.records
        assert record.token.startswith("[REDACTED")
        assert record.nested[0]["password"].startswith("[REDACTED")
        assert record.plain == "ok"
        assert CANARY not in _record_text(caplog)

    def test_extra_is_redacted_at_every_level_method(self, secure_logger, caplog):
        """debug/info/warning/error/critical/exception all redact extra=."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("m", extra={"token": CANARY})
            secure_logger.info("m", extra={"token": CANARY})
            secure_logger.warning("m", extra={"token": CANARY})
            secure_logger.error("m", extra={"token": CANARY})
            secure_logger.critical("m", extra={"token": CANARY})
            secure_logger.exception("m", extra={"token": CANARY})

        assert len(caplog.records) == 6
        assert CANARY not in _record_text(caplog)

    def test_adapter_level_extra_is_merged_and_redacted(self, caplog):
        """The adapter's own extra context is applied, redacted, and overridden by the call's."""
        adapter = SecureLoggerAdapter(
            logging.getLogger("test.secure.coverage"),
            extra={"api_key": CANARY, "origin": "adapter"},
        )

        with caplog.at_level(logging.DEBUG):
            adapter.info("m", extra={"origin": "call"})

        (record,) = caplog.records
        assert record.origin == "call"
        assert record.api_key.startswith("[REDACTED")
        assert CANARY not in _record_text(caplog)

    def test_log_method_redacts_arguments_and_extra(self, secure_logger, caplog):
        """adapter.log(level, ...) goes through the same redaction as the level methods."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.log(
                logging.WARNING,
                "Data: %s %s",
                [{"token": CANARY}],
                ({"password": CANARY},),
                extra={"secret": CANARY},
            )

        (record,) = caplog.records
        assert record.levelno == logging.WARNING
        assert CANARY not in _record_text(caplog)

    def test_dict_message_object_is_redacted(self, secure_logger, caplog):
        """A container passed as the message itself is redacted before it is stringified."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug({"token": CANARY})

        assert CANARY not in _record_text(caplog)

    def test_mapping_as_sole_argument_still_feeds_percent_style_formatting(
        self, secure_logger, caplog
    ):
        """A sole dict argument stays a mapping so %(name)s formatting keeps working."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("n=%(name)s t=%(token)s", {"name": "n", "token": CANARY})

        assert "n=n t=[REDACTED:" in caplog.text
        assert CANARY not in _record_text(caplog)

    def test_non_string_key_at_an_enabled_level(self, secure_logger, caplog):
        """{1: "x"} logs normally at an enabled level instead of raising AttributeError."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", {1: "x"})

        assert "Data: {1: 'x'}" in caplog.text

    def test_non_string_sensitive_key_is_redacted(self, secure_logger, caplog):
        """A non-string key whose text form is sensitive still has its value redacted."""
        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", {("user", "token"): CANARY})

        assert CANARY not in _record_text(caplog)

    @pytest.mark.parametrize("method", ["debug", "info", "warning", "error", "critical"])
    def test_non_string_key_at_a_disabled_level_neither_raises_nor_logs(
        self, secure_logger, caplog, method
    ):
        """A disabled level returns before any redaction runs, so nothing can raise."""
        with caplog.at_level(logging.CRITICAL + 1):
            getattr(secure_logger, method)("Data: %s", {1: "x"}, extra={2: "y"})
            secure_logger.log(logging.DEBUG, "Data: %s", {1: "x"})

        assert caplog.records == []

    def test_disabled_level_never_invokes_the_redactor(self, secure_logger, caplog):
        """The isEnabledFor check precedes redaction: a disabled level does no redaction work."""
        with caplog.at_level(logging.WARNING):
            with patch("eero.logging._redact") as redactor:
                secure_logger.debug("Data: %s", {"token": CANARY}, extra={"token": CANARY})
                secure_logger.log(logging.INFO, "Data: %s", [CANARY])

        redactor.assert_not_called()
        assert caplog.records == []

    def test_cyclic_dict_argument_does_not_raise(self, secure_logger, caplog):
        """A cyclic dict is logged with the placeholder instead of raising RecursionError."""
        data = {"token": CANARY}
        data["self"] = data

        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", data)

        assert _UNTRAVERSABLE_PLACEHOLDER in caplog.text
        assert CANARY not in _record_text(caplog)

    def test_cyclic_extra_does_not_raise(self, secure_logger, caplog):
        """A cycle inside extra= is also replaced by the placeholder."""
        cyclic: list = []
        cyclic.append(cyclic)

        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("m", extra={"data": cyclic})

        (record,) = caplog.records
        assert record.data == [_UNTRAVERSABLE_PLACEHOLDER]

    def test_deep_nesting_beyond_the_cap_does_not_raise(self, secure_logger, caplog):
        """Nesting far deeper than the cap is replaced by the placeholder, with no leak."""
        data: object = {"token": CANARY, "note": CANARY}
        for _ in range(_MAX_REDACTION_DEPTH * 4):
            data = {"n": [data]}

        with caplog.at_level(logging.DEBUG):
            secure_logger.debug("Data: %s", data)

        assert _UNTRAVERSABLE_PLACEHOLDER in caplog.text
        assert CANARY not in _record_text(caplog)

    def test_arguments_are_not_mutated(self, secure_logger, caplog):
        """Logging leaves the caller's args and extra untouched."""
        arg = [{"token": CANARY}]
        extra = {"password": CANARY, "rows": ({"token": CANARY},)}
        arg_snapshot, extra_snapshot = copy.deepcopy(arg), copy.deepcopy(extra)

        with caplog.at_level(logging.DEBUG):
            secure_logger.warning("Data: %s", arg, extra=extra)
            secure_logger.log(logging.ERROR, "Data: %s", arg, extra=extra)

        assert arg == arg_snapshot
        assert extra == extra_snapshot
        assert CANARY not in _record_text(caplog)

    def test_exception_logs_traceback_with_redacted_arguments(self, secure_logger, caplog):
        """exception() still attaches exc_info while redacting its arguments."""
        with caplog.at_level(logging.DEBUG):
            try:
                raise ValueError("boom")
            except ValueError:
                secure_logger.exception("Failed: %s", [{"token": CANARY}])

        (record,) = caplog.records
        assert record.levelno == logging.ERROR
        assert record.exc_info is not None
        assert CANARY not in record.getMessage()
