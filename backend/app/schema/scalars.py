"""Conservative lexical candidates, without coercing or returning source values."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MAX_INTERPRETED_CHARACTERS = 256
INTEGER = re.compile(r"[+-]?[0-9]+\Z")
DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
BOOLEAN_WORDS = frozenset({"true", "false", "yes", "no"})
NONFINITE = frozenset(
    {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
)


@dataclass(frozen=True)
class ScalarMatch:
    integer: bool = False
    decimal: bool = False
    boolean: bool = False
    boolean_override: bool = False
    leading_zero: bool = False
    nonfinite: bool = False
    too_long: bool = False


def scalar_match(value: str) -> ScalarMatch:
    if len(value) > MAX_INTERPRETED_CHARACTERS:
        return ScalarMatch(too_long=True)
    lower = value.lower()
    integer = INTEGER.fullmatch(value) is not None
    decimal = False
    if DECIMAL.fullmatch(value) is not None:
        try:
            decimal = Decimal(value).is_finite()
        except InvalidOperation:
            pass
    digits = value.lstrip("+-")
    return ScalarMatch(
        integer=integer,
        decimal=decimal,
        boolean=lower in BOOLEAN_WORDS,
        boolean_override=lower in BOOLEAN_WORDS or value in {"0", "1"},
        leading_zero=integer and len(digits) > 1 and digits.startswith("0"),
        nonfinite=lower in NONFINITE,
    )
