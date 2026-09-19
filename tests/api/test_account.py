"""Tests for AccountAPI module."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.account import AccountAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestAccountAPIInit:
    """Tests for AccountAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = AccountAPI(auth_api)
        assert api._auth_api is auth_api


@pytest.fixture
def account_api(mock_session):
    """Create an AccountAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return AccountAPI(auth_api)


class TestSetName:
    """Tests for set_name."""

    @pytest.mark.asyncio
    async def test_form_encoded_put(self, account_api, mock_session):
        """Test the verb, encoding, and field."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await account_api.set_name("Jane Doe")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["data"] == {"name": "Jane Doe"}
        assert "json" not in call_args.kwargs
        assert call_args.args[1].endswith("/account/name")

    @pytest.mark.asyncio
    async def test_returns_raw_envelope(self, account_api, mock_session):
        """Test the raw envelope is returned unchanged."""
        data = {"name": "Jane Doe"}
        envelope = api_success_response(data)
        mock_session.request.return_value = create_mock_response(200, envelope)

        result = await account_api.set_name("Jane Doe")

        assert result == envelope

    @pytest.mark.asyncio
    async def test_not_authenticated(self, account_api):
        """Test raises when not authenticated."""
        account_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await account_api.set_name("Jane Doe")


class TestSetEmail:
    """Tests for set_email."""

    @pytest.mark.asyncio
    async def test_form_encoded_put(self, account_api, mock_session):
        """Test the verb, encoding, and field."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await account_api.set_email("user@example.test")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["data"] == {"email": "user@example.test"}
        assert call_args.args[1].endswith("/account/email")

    @pytest.mark.asyncio
    async def test_email_value_never_logged(self, account_api, mock_session, caplog):
        """Test the email value never appears in any log record."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.DEBUG):
            await account_api.set_email("super-secret@example.test")

        assert all(
            "super-secret@example.test" not in record.getMessage() for record in caplog.records
        )


class TestVerifyEmail:
    """Tests for verify_email."""

    @pytest.mark.asyncio
    async def test_form_encoded_post(self, account_api, mock_session):
        """Test the verb, encoding, and field."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await account_api.verify_email("123456")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.kwargs["data"] == {"code": "123456"}
        assert call_args.args[1].endswith("/account/email/verify")

    @pytest.mark.asyncio
    async def test_code_value_never_logged(self, account_api, mock_session, caplog):
        """Test the verification code never appears in any log record."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.DEBUG):
            await account_api.verify_email("987654")

        assert all("987654" not in record.getMessage() for record in caplog.records)


class TestSetPhone:
    """Tests for set_phone."""

    @pytest.mark.asyncio
    async def test_form_encoded_put(self, account_api, mock_session):
        """Test the verb, encoding, and field."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await account_api.set_phone("+15555550100")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["data"] == {"phone": "+15555550100"}
        assert call_args.args[1].endswith("/account/phone")

    @pytest.mark.asyncio
    async def test_phone_value_never_logged(self, account_api, mock_session, caplog):
        """Test the phone value never appears in any log record."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.DEBUG):
            await account_api.set_phone("+15555550199")

        assert all("+15555550199" not in record.getMessage() for record in caplog.records)


class TestVerifyPhone:
    """Tests for verify_phone."""

    @pytest.mark.asyncio
    async def test_form_encoded_post(self, account_api, mock_session):
        """Test the verb, encoding, and field."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await account_api.verify_phone("654321")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.kwargs["data"] == {"code": "654321"}
        assert call_args.args[1].endswith("/account/phone/verify")

    @pytest.mark.asyncio
    async def test_code_value_never_logged(self, account_api, mock_session, caplog):
        """Test the verification code never appears in any log record."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.DEBUG):
            await account_api.verify_phone("111222")

        assert all("111222" not in record.getMessage() for record in caplog.records)


class TestSetConsents:
    """Tests for set_consents."""

    @pytest.mark.parametrize(
        "marketing_emails,wire_value",
        [(True, "true"), (False, "false")],
    )
    @pytest.mark.asyncio
    async def test_form_encoded_put(self, account_api, mock_session, marketing_emails, wire_value):
        """Test the verb, encoding, and boolean-to-string conversion."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await account_api.set_consents(marketing_emails=marketing_emails)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["data"] == {"marketing_emails": wire_value}
        assert call_args.args[1].endswith("/account/consents")


class TestGetSmsCountries:
    """Tests for get_sms_countries."""

    @pytest.mark.asyncio
    async def test_get_request(self, account_api, mock_session):
        """Test the verb and URL."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await account_api.get_sms_countries()

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/countries/sms")

    @pytest.mark.asyncio
    async def test_returns_raw_envelope(self, account_api, mock_session):
        """Test the raw envelope is returned unchanged."""
        data = {"US": "+1", "GB": "+44"}
        envelope = api_success_response(data)
        mock_session.request.return_value = create_mock_response(200, envelope)

        result = await account_api.get_sms_countries()

        assert result == envelope

    @pytest.mark.asyncio
    async def test_not_authenticated(self, account_api):
        """Test raises when not authenticated."""
        account_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await account_api.get_sms_countries()
