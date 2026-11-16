"""Streaming full-column evidence; no source cells are included in the result."""

import hashlib
from dataclasses import dataclass, field

from app.ingestion.models import CsvColumn
from app.schema.dates import date_match
from app.schema.models import (
    DateOrder,
    SchemaColumn,
    SchemaType,
    SchemaWarning,
    TypeEvidence,
    TypeOverride,
    WarningCode,
)
from app.schema.scalars import scalar_match


@dataclass
class ColumnEvidence:
    nulls: int = 0
    present: int = 0
    integers: int = 0
    decimals: int = 0
    booleans: int = 0
    override_booleans: int = 0
    iso: int = 0
    mdy: int = 0
    dmy: int = 0
    any_dates: int = 0
    timestamps: int = 0
    naive_timestamps: int = 0
    leading_zeros: int = 0
    invalid_dates: int = 0
    nonfinite: int = 0
    long_values: int = 0
    # Only retain digests, and stop at 21 distinct values: no raw-cell sample cache.
    distinct: set[bytes] = field(default_factory=set)

    def observe(self, value: str | None) -> None:
        if value is None:
            self.nulls += 1
            return
        self.present += 1
        if len(self.distinct) <= 20:
            self.distinct.add(hashlib.sha256(value.encode("utf-8")).digest())
        scalar = scalar_match(value)
        dates = date_match(value)
        self.integers += scalar.integer
        self.decimals += scalar.decimal
        self.booleans += scalar.boolean
        self.override_booleans += scalar.boolean_override
        self.leading_zeros += scalar.leading_zero
        self.nonfinite += scalar.nonfinite
        self.long_values += scalar.too_long
        self.iso += dates.iso
        self.mdy += dates.mdy
        self.dmy += dates.dmy
        self.any_dates += dates.iso or dates.mdy or dates.dmy
        self.invalid_dates += dates.invalid
        self.timestamps += dates.timestamp
        self.naive_timestamps += dates.naive

    def infer(self) -> tuple[SchemaType, DateOrder | None, str, list[SchemaWarning]]:
        warnings: list[SchemaWarning] = []

        def warn(code: WarningCode, message: str) -> None:
            warnings.append(SchemaWarning(code=code, message=message))

        if not self.present:
            warn("all_null", "No non-null values are available to infer a type.")
            return "text", None, "No non-null evidence; retain text.", warnings
        if self.leading_zeros:
            warn(
                "leading_zeros",
                "Leading-zero integers may be identifiers; automatic typing retains text.",
            )
        if self.invalid_dates:
            warn("invalid_dates", "Some date-shaped values are invalid calendar dates.")
        if self.nonfinite:
            warn(
                "nonfinite_numbers",
                "Non-finite numeric tokens are not supported as numeric evidence.",
            )
        if self.long_values:
            warn("long_values", "Values longer than 256 characters are not interpreted as scalars.")
        if self.naive_timestamps:
            warn(
                "timezone_unspecified", "Some timestamps have no timezone; no timezone is assumed."
            )
        if self.booleans == self.present:
            return "boolean", None, "All non-null values are true/false or yes/no words.", warnings
        if self.decimals == self.present and not self.leading_zeros:
            kind: SchemaType = "integer" if self.integers == self.present else "decimal"
            return kind, None, "Every non-null value matches finite numeric syntax.", warnings
        if self.iso == self.present:
            return "date", None, "Every non-null value is a valid ISO YYYY-MM-DD date.", warnings
        if self.timestamps == self.present:
            return "datetime", None, "Every non-null value is a supported ISO timestamp.", warnings
        mdy_complete = self.iso + self.mdy == self.present
        dmy_complete = self.iso + self.dmy == self.present
        if mdy_complete and dmy_complete:
            warn(
                "ambiguous_dates",
                "Slash dates permit both month/day/year and day/month/year; "
                "choose an explicit order.",
            )
        elif mdy_complete or dmy_complete:
            order: DateOrder = "mdy" if mdy_complete else "dmy"
            return (
                "date",
                order,
                "All dates fit one column-wide slash-date order, optionally with ISO dates.",
                warnings,
            )
        elif self.any_dates == self.present:
            warn("inconsistent_dates", "No single slash-date order fits every value.")
        strongest = max(self.decimals, self.booleans, self.any_dates, self.timestamps)
        if 0 < strongest < self.present:
            warn(
                "mixed_types",
                "Only some non-null values match a supported scalar family; retain text.",
            )
        # Uncertainty takes priority over a low-cardinality suggestion.
        if not warnings and self.present >= 10 and len(self.distinct) <= min(20, self.present // 5):
            warn(
                "low_cardinality",
                "Repeated text has at most 20 distinct values and a distinct ratio "
                "at most 20%; categorical is a heuristic.",
            )
            return (
                "categorical",
                None,
                "Repeated text meets the documented categorical heuristic.",
                warnings,
            )
        if not warnings:
            warn(
                "no_type_evidence",
                "Values do not support a conservative scalar or categorical type.",
            )
        return "text", None, "Retain source text rather than guessing an interpretation.", warnings

    def accepts(self, override: TypeOverride) -> bool:
        if override.type in {"text", "categorical"}:
            return True
        # An explicit semantic annotation is allowed for an all-null column.
        if not self.present:
            return True
        if override.type == "integer":
            return self.integers == self.present
        if override.type == "decimal":
            return self.decimals == self.present
        if override.type == "boolean":
            return self.override_booleans == self.present
        if override.type == "datetime":
            return self.timestamps == self.present
        if override.date_order == "mdy":
            return self.iso + self.mdy == self.present
        if override.date_order == "dmy":
            return self.iso + self.dmy == self.present
        # ISO-only or one unambiguous column-wide order; ambiguous slash dates need an order.
        return self.iso == self.present or (
            (self.iso + self.mdy == self.present) != (self.iso + self.dmy == self.present)
        )

    def column(self, column: CsvColumn, override: TypeOverride | None) -> SchemaColumn:
        inferred, order, explanation, warnings = self.infer()
        if override is not None:
            if override.type != "date":
                order = None
            elif override.date_order is not None:
                order = override.date_order
            explanation += (
                " An explicit validated override selects the effective type; "
                "stored values are unchanged."
            )
        return SchemaColumn(
            **column.model_dump(),
            inferred_type=inferred,
            effective_type=override.type if override else inferred,
            type_source="override" if override else "inferred",
            date_order=order,
            non_null_count=self.present,
            null_count=self.nulls,
            explanation=explanation,
            evidence=TypeEvidence(
                integer_values=self.integers,
                decimal_values=self.decimals,
                boolean_values=self.booleans,
                iso_date_values=self.iso,
                mdy_date_values=self.mdy,
                dmy_date_values=self.dmy,
                datetime_values=self.timestamps,
            ),
            warnings=tuple(warnings),
            override=override,
        )
