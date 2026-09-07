"""Small, status-aware calculations for the historical dataset."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


VALID_INPUT_STATUSES = frozenset({"selected", "calculated", "documented_zero"})


@dataclass(frozen=True)
class MetricValue:
    """A numeric result paired with a data-quality status and explanation."""

    value: Decimal | None
    status: str
    reason: str


def _blocked_status(*inputs: MetricValue) -> str:
    return (
        "manual_review"
        if any(value.status == "manual_review" for value in inputs)
        else "missing"
    )


def safe_ratio(numerator: MetricValue, denominator: MetricValue) -> MetricValue:
    """Divide only selected or calculated inputs and handle zero explicitly."""

    if (
        numerator.status not in VALID_INPUT_STATUSES
        or denominator.status not in VALID_INPUT_STATUSES
        or numerator.value is None
        or denominator.value is None
    ):
        return MetricValue(
            None,
            _blocked_status(numerator, denominator),
            "A required input is missing or requires manual review.",
        )
    if denominator.value == 0:
        return MetricValue(None, "missing", "The denominator is zero.")
    return MetricValue(
        numerator.value / denominator.value,
        "calculated",
        "Calculated from validated inputs.",
    )


def subtract(minuend: MetricValue, subtrahend: MetricValue) -> MetricValue:
    """Subtract only validated inputs."""

    if (
        minuend.status not in VALID_INPUT_STATUSES
        or subtrahend.status not in VALID_INPUT_STATUSES
        or minuend.value is None
        or subtrahend.value is None
    ):
        return MetricValue(
            None,
            _blocked_status(minuend, subtrahend),
            "A required input is missing or requires manual review.",
        )
    return MetricValue(
        minuend.value - subtrahend.value,
        "calculated",
        "Calculated from validated inputs.",
    )


def add(*inputs: MetricValue) -> MetricValue:
    """Add one or more validated inputs without treating missing values as zero."""

    if not inputs:
        raise ValueError("At least one input is required.")
    if any(
        item.status not in VALID_INPUT_STATUSES or item.value is None for item in inputs
    ):
        return MetricValue(
            None,
            _blocked_status(*inputs),
            "A required input is missing or requires manual review.",
        )
    return MetricValue(
        sum((item.value for item in inputs if item.value is not None), Decimal("0")),
        "calculated",
        "Calculated from validated inputs.",
    )


def revenue_growth(current: MetricValue, prior: MetricValue) -> MetricValue:
    """Calculate year-over-year revenue growth from two validated periods."""

    change = subtract(current, prior)
    return safe_ratio(change, prior)


def cagr(first: MetricValue, last: MetricValue, *, intervals: int) -> MetricValue:
    """Calculate CAGR, explicitly distinguishing observations from intervals."""

    if intervals <= 0:
        raise ValueError("CAGR intervals must be positive.")
    if (
        first.status not in VALID_INPUT_STATUSES
        or last.status not in VALID_INPUT_STATUSES
        or first.value is None
        or last.value is None
    ):
        return MetricValue(
            None,
            _blocked_status(first, last),
            "A required endpoint is missing or requires manual review.",
        )
    if first.value <= 0 or last.value < 0:
        return MetricValue(
            None,
            "missing",
            "CAGR requires a positive first value and nonnegative last value.",
        )
    result = Decimal(str(float(last.value / first.value) ** (1 / intervals) - 1))
    return MetricValue(
        result,
        "calculated",
        f"Calculated from two endpoints over {intervals} growth intervals.",
    )
