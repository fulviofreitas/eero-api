"""Tests for Account model."""

from datetime import datetime

from eero.models.account import Account, User


class TestAccount:
    """Test cases for the Account model."""

    def test_account_without_id(self):
        """Test that Account can be created without an id field.

        The Eero API /account endpoint does not return an `id` field,
        so the model must accept responses without it.
        """
        account = Account(
            name="Test Account",
            premium_status="active",
        )
        assert account.id is None
        assert account.name == "Test Account"
        assert account.premium_status == "active"

    def test_account_with_id(self):
        """Test that Account works correctly when id IS provided."""
        account = Account(
            id="12345",
            name="Test Account",
            premium_status="active",
        )
        assert account.id == "12345"
        assert account.name == "Test Account"
        assert account.premium_status == "active"

    def test_account_from_api_response_without_id(self):
        """Test parsing an API response that doesn't include the id field."""
        api_response = {
            "name": "HA",
            "premium_status": "active",
            "business_details": None,
        }
        account = Account.model_validate(api_response)
        assert account.id is None
        assert account.name == "HA"
        assert account.premium_status == "active"

    def test_account_with_users(self):
        """Test Account with a list of users."""
        user_data = {
            "id": "user-123",
            "email": "test@example.com",
            "created_at": "2024-01-01T00:00:00Z",
            "role": "owner",
        }
        account = Account(
            name="Test Account",
            users=[User.model_validate(user_data)],
        )
        assert account.id is None
        assert len(account.users) == 1
        assert account.users[0].id == "user-123"

    def test_account_all_optional_fields(self):
        """Test Account with all optional fields populated."""
        account = Account(
            id="acc-123",
            name="Full Account",
            premium_status="active",
            premium_expiry=datetime(2025, 12, 31),
            created_at=datetime(2020, 1, 1),
        )
        assert account.id == "acc-123"
        assert account.name == "Full Account"
        assert account.premium_status == "active"
        assert account.premium_expiry == datetime(2025, 12, 31)
        assert account.created_at == datetime(2020, 1, 1)


class TestUser:
    """Test cases for the User model."""

    def test_user_required_fields(self):
        """Test User with only required fields."""
        user = User(
            id="user-123",
            email="test@example.com",
            created_at=datetime(2024, 1, 1),
            role="owner",
        )
        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.name is None
        assert user.phone is None

    def test_user_all_fields(self):
        """Test User with all fields populated."""
        user = User(
            id="user-123",
            name="Test User",
            email="test@example.com",
            phone="+1234567890",
            created_at=datetime(2024, 1, 1),
            role="member",
        )
        assert user.id == "user-123"
        assert user.name == "Test User"
        assert user.email == "test@example.com"
        assert user.phone == "+1234567890"
        assert user.role == "member"
