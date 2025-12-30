"""
Client repository for managing buyer accounts.

Provides functions to query, validate, and manage client accounts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from domain.client import Client
from repositories.client import supabase


def _parse_utc_datetime(value: any) -> datetime:
    """Parse a Supabase timestamp into a timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    else:
        raise TypeError(f"Unsupported timestamp type: {type(value)!r}")

    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def get_client_by_id(client_id: UUID) -> Optional[Client]:
    """
    Get a client by their ID.

    Args:
        client_id: UUID of the client

    Returns:
        Client domain model or None if not found

    Example:
        client = get_client_by_id(UUID('12345678-1234-1234-1234-123456789012'))
        if client and client.is_active():
            # Client can make purchases
    """
    response = (
        supabase.table("clients")
        .select("*")
        .eq("client_id", str(client_id))
        .limit(1)
        .execute()
    )

    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to fetch client: {error}")

    rows = getattr(response, "data", None) or []

    if not rows:
        return None

    row = rows[0]

    return Client(
        client_id=UUID(str(row["client_id"])),
        email=str(row["email"]),
        status=str(row["status"]),
        company_name=row.get("company_name"),
        contact_name=row.get("contact_name"),
        phone=row.get("phone"),
        auth_provider=row.get("auth_provider"),
        auth_provider_user_id=row.get("auth_provider_user_id"),
        email_verified=bool(row.get("email_verified", False)),
        created_at=_parse_utc_datetime(row["created_at_utc"]) if row.get("created_at_utc") else None,
        updated_at=_parse_utc_datetime(row["updated_at_utc"]) if row.get("updated_at_utc") else None,
        last_login_at=_parse_utc_datetime(row["last_login_at_utc"]) if row.get("last_login_at_utc") else None,
    )


def get_client_by_email(email: str) -> Optional[Client]:
    """
    Get a client by their email address.

    Args:
        email: Client's email address

    Returns:
        Client domain model or None if not found

    Example:
        client = get_client_by_email("buyer@example.com")
    """
    response = (
        supabase.table("clients")
        .select("*")
        .eq("email", email)
        .limit(1)
        .execute()
    )

    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to fetch client: {error}")

    rows = getattr(response, "data", None) or []

    if not rows:
        return None

    row = rows[0]

    return Client(
        client_id=UUID(str(row["client_id"])),
        email=str(row["email"]),
        status=str(row["status"]),
        company_name=row.get("company_name"),
        contact_name=row.get("contact_name"),
        phone=row.get("phone"),
        auth_provider=row.get("auth_provider"),
        auth_provider_user_id=row.get("auth_provider_user_id"),
        email_verified=bool(row.get("email_verified", False)),
        created_at=_parse_utc_datetime(row["created_at_utc"]) if row.get("created_at_utc") else None,
        updated_at=_parse_utc_datetime(row["updated_at_utc"]) if row.get("updated_at_utc") else None,
        last_login_at=_parse_utc_datetime(row["last_login_at_utc"]) if row.get("last_login_at_utc") else None,
    )


def verify_client_active(client_id: UUID) -> bool:
    """
    Verify that a client exists and is active.

    Args:
        client_id: UUID of the client

    Returns:
        True if client exists and is active, False otherwise

    Example:
        if verify_client_active(client_id):
            # Proceed with purchase
        else:
            # Reject purchase
    """
    client = get_client_by_id(client_id)
    return client is not None and client.is_active()


def update_last_login(client_id: UUID) -> None:
    """
    Update the last login timestamp for a client.

    Args:
        client_id: UUID of the client

    Example:
        update_last_login(client_id)
    """
    response = (
        supabase.table("clients")
        .update({"last_login_at_utc": datetime.now(timezone.utc).isoformat()})
        .eq("client_id", str(client_id))
        .execute()
    )

    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to update last login: {error}")


def create_test_client(
    email: str,
    company_name: Optional[str] = None,
    status: str = "active",
    email_verified: bool = True
) -> Client:
    """
    Create a test client account (for development/testing).

    Args:
        email: Client email
        company_name: Optional company name
        status: Account status (default: active)
        email_verified: Email verification status (default: True)

    Returns:
        Created Client domain model

    Example:
        test_client = create_test_client("test@example.com", "Test Corp")
    """
    import uuid

    client_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    payload = {
        "client_id": str(client_id),
        "email": email,
        "status": status,
        "company_name": company_name,
        "auth_provider": "local",
        "email_verified": email_verified,
        "created_at_utc": now.isoformat(),
        "updated_at_utc": now.isoformat(),
    }

    response = supabase.table("clients").insert(payload).execute()

    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to create test client: {error}")

    return Client(
        client_id=client_id,
        email=email,
        status=status,
        company_name=company_name,
        auth_provider="local",
        email_verified=email_verified,
        created_at=now,
        updated_at=now,
    )


__all__ = [
    "get_client_by_id",
    "get_client_by_email",
    "verify_client_active",
    "update_last_login",
    "create_test_client",
]
