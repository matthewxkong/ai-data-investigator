"""Calendar validation with no locale or current-date assumptions."""

import re
from dataclasses import dataclass
from datetime import date

ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
SLASH_DATE = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})\Z")


@dataclass(frozen=True)
class DateMatch:
    iso: bool = False
    mdy: bool = False
    dmy: bool = False
    invalid: bool = False


def valid_date(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def date_match(value: str) -> DateMatch:
    if ISO_DATE.fullmatch(value):
        try:
            date.fromisoformat(value)
        except ValueError:
            return DateMatch(invalid=True)
        return DateMatch(iso=True)
    match = SLASH_DATE.fullmatch(value)
    if match is None:
        return DateMatch()
    first, second, year = (int(part) for part in match.groups())
    mdy = valid_date(year, first, second)
    dmy = valid_date(year, second, first)
    return DateMatch(mdy=mdy, dmy=dmy, invalid=not mdy and not dmy)
