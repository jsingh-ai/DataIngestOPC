from __future__ import annotations

from typing import Any


def normalize_value(value: Any) -> tuple[float | None, str | None, bool | None]:
    if isinstance(value, bool):
        return None, None, value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), None, None
    if value is None:
        return None, None, None
    return None, str(value)[:255], None
