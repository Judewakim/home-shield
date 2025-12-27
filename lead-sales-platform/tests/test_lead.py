"""
Tests for `domain/lead.py`.

Covers contract rules:
- Lead classification is immutable after ingestion (cannot be changed).
- created_at_utc is required and must be a UTC timestamp.
- raw_payload and source are preserved as provided.
- No hidden logic is executed at instantiation (no mutation of provided payload).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from domain.lead import Lead, LeadClassification


def test_lead_created_at_utc_required() -> None:
    """Verify created_at_utc is required at instantiation."""

    with pytest.raises(TypeError):
        Lead(  # type: ignore[call-arg]
            lead_id=UUID("00000000-0000-0000-0000-000000000001"),
            source="src",
            state="TX",
            raw_payload={},
            classification=LeadClassification.GOLD,
        )


def test_lead_created_at_utc_must_be_utc() -> None:
    """Verify created_at_utc must be timezone-aware UTC (offset 0)."""

    lead_id = UUID("00000000-0000-0000-0000-000000000001")
    raw = {"k": "v"}

    with pytest.raises(ValueError):
        Lead(
            lead_id=lead_id,
            source="src",
            state="TX",
            raw_payload=raw,
            classification=LeadClassification.GOLD,
            created_at_utc=datetime(2025, 1, 1, 0, 0, 0),
        )

    with pytest.raises(ValueError):
        Lead(
            lead_id=lead_id,
            source="src",
            state="TX",
            raw_payload=raw,
            classification=LeadClassification.GOLD,
            created_at_utc=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5))),
        )


def test_lead_preserves_source_and_raw_payload_identity() -> None:
    """Verify source and raw_payload are stored exactly as provided."""

    lead_id = UUID("00000000-0000-0000-0000-000000000001")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    raw = {"a": 1, "nested": {"b": 2}}

    lead = Lead(
        lead_id=lead_id,
        source="source-A",
        state="TX",
        raw_payload=raw,
        classification=LeadClassification.SILVER,
        created_at_utc=created,
    )

    assert lead.source == "source-A"
    assert lead.raw_payload is raw
    assert lead.raw_payload["a"] == 1
    assert lead.raw_payload["nested"] == {"b": 2}


def test_lead_instantiation_does_not_mutate_payload() -> None:
    """Verify no hidden logic mutates the provided raw_payload during instantiation."""

    lead_id = UUID("00000000-0000-0000-0000-000000000001")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    raw = {"x": 1}

    _ = Lead(
        lead_id=lead_id,
        source="source-A",
        state="TX",
        raw_payload=raw,
        classification=LeadClassification.GOLD,
        created_at_utc=created,
    )

    assert raw == {"x": 1}


def test_lead_classification_is_immutable() -> None:
    """Verify classification cannot be changed after ingestion (frozen entity)."""

    lead = Lead(
        lead_id=UUID("00000000-0000-0000-0000-000000000001"),
        source="src",
        state="TX",
        raw_payload={},
        classification=LeadClassification.GOLD,
        created_at_utc=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(FrozenInstanceError):
        lead.classification = LeadClassification.SILVER  # type: ignore[misc]


