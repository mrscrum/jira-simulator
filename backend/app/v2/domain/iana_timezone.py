"""Validated IANA timezone resolution for pure v2 domain services."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

PSEUDO_ZONE_NAMES = frozenset({"Factory", "localtime", "posixrules"})
AVAILABLE_IANA_TIMEZONE_NAMES = frozenset(available_timezones()) - PSEUDO_ZONE_NAMES


def resolve_iana_timezone(timezone_name: object) -> ZoneInfo:
    invalid_name = (
        type(timezone_name) is not str
        or not timezone_name
        or timezone_name.strip() != timezone_name
        or timezone_name not in AVAILABLE_IANA_TIMEZONE_NAMES
    )
    if invalid_name:
        raise ValueError("timezone_name must name an available IANA timezone")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("timezone_name must name an available IANA timezone") from error
