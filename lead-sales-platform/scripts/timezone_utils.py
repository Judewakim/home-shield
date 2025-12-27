"""
Timezone utilities for CSV ingestion.

Maps US state codes to their respective timezones for timestamp conversion.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# Mapping of US state codes to IANA timezone identifiers
STATE_TO_TIMEZONE = {
    # Eastern Time (UTC-5/-4)
    "CT": "America/New_York",
    "DE": "America/New_York",
    "FL": "America/New_York",  # Most of FL; panhandle is Central
    "GA": "America/New_York",
    "MA": "America/New_York",
    "MD": "America/New_York",
    "ME": "America/New_York",
    "MI": "America/Detroit",  # Most of MI; some areas Central
    "NC": "America/New_York",
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NY": "America/New_York",
    "OH": "America/New_York",
    "PA": "America/New_York",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "VA": "America/New_York",
    "VT": "America/New_York",
    "WV": "America/New_York",

    # Central Time (UTC-6/-5)
    "AL": "America/Chicago",
    "AR": "America/Chicago",
    "IA": "America/Chicago",
    "IL": "America/Chicago",
    "IN": "America/Indiana/Indianapolis",  # Most of IN; some areas Eastern
    "KS": "America/Chicago",  # Most of KS; some areas Mountain
    "KY": "America/Kentucky/Louisville",  # Most of KY; western part Central
    "LA": "America/Chicago",
    "MN": "America/Chicago",
    "MO": "America/Chicago",
    "MS": "America/Chicago",
    "ND": "America/Chicago",  # Most of ND; some areas Mountain
    "NE": "America/Chicago",  # Most of NE; western part Mountain
    "OK": "America/Chicago",
    "SD": "America/Chicago",  # Most of SD; western part Mountain
    "TN": "America/Chicago",  # Most of TN; eastern part Eastern
    "TX": "America/Chicago",  # Most of TX; far west Mountain
    "WI": "America/Chicago",

    # Mountain Time (UTC-7/-6)
    "AZ": "America/Phoenix",  # Arizona doesn't observe DST
    "CO": "America/Denver",
    "ID": "America/Boise",  # Most of ID; northern part Pacific
    "MT": "America/Denver",
    "NM": "America/Denver",
    "UT": "America/Denver",
    "WY": "America/Denver",

    # Pacific Time (UTC-8/-7)
    "CA": "America/Los_Angeles",
    "NV": "America/Los_Angeles",  # Most of NV; some areas Mountain
    "OR": "America/Los_Angeles",  # Most of OR; some areas Mountain
    "WA": "America/Los_Angeles",

    # Alaska Time (UTC-9/-8)
    "AK": "America/Anchorage",

    # Hawaii-Aleutian Time (UTC-10) - Hawaii doesn't observe DST
    "HI": "America/Adak",
}


def get_timezone_for_state(state_code: str) -> ZoneInfo:
    """
    Get the timezone for a US state code.

    Args:
        state_code: Two-letter US state code (e.g., "LA", "CA", "NY")

    Returns:
        ZoneInfo object for the state's timezone.
        Falls back to UTC if state code is unknown or invalid.

    Examples:
        >>> get_timezone_for_state("LA")
        ZoneInfo('America/Chicago')

        >>> get_timezone_for_state("CA")
        ZoneInfo('America/Los_Angeles')

        >>> get_timezone_for_state("XX")  # Unknown state
        ZoneInfo('UTC')
    """
    state_code_upper = state_code.strip().upper()

    timezone_name = STATE_TO_TIMEZONE.get(state_code_upper)

    if timezone_name is None:
        # Unknown state, fallback to UTC
        return ZoneInfo("UTC")

    return ZoneInfo(timezone_name)


def parse_timestamp_with_state_timezone(
    timestamp_str: str,
    state_code: str,
    format: str = "%m-%d-%Y %H:%M:%S"
) -> datetime:
    """
    Parse a naive timestamp string and convert to UTC using the state's timezone.

    Args:
        timestamp_str: Timestamp string to parse (e.g., "06-09-2025 15:55:13")
        state_code: Two-letter US state code (e.g., "LA")
        format: strptime format string (default: "MM-DD-YYYY HH:MM:SS")

    Returns:
        Timezone-aware datetime in UTC.

    Raises:
        ValueError: If timestamp string doesn't match the expected format.

    Examples:
        >>> parse_timestamp_with_state_timezone("06-09-2025 15:55:13", "LA")
        datetime(2025, 6, 9, 20, 55, 13, tzinfo=timezone.utc)  # Central → UTC (+5 hours)
    """
    # Parse as naive datetime
    naive_dt = datetime.strptime(timestamp_str, format)

    # Get timezone for the state
    state_tz = get_timezone_for_state(state_code)

    # Localize to state timezone
    localized_dt = naive_dt.replace(tzinfo=state_tz)

    # Convert to UTC
    return localized_dt.astimezone(timezone.utc)


__all__ = [
    "get_timezone_for_state",
    "parse_timestamp_with_state_timezone",
    "STATE_TO_TIMEZONE",
]
