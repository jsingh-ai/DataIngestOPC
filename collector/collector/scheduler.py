from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from collector.models import TagConfig


def due_tags(tags: list[TagConfig], now: datetime | None = None) -> dict[int, list[TagConfig]]:
    current = now or datetime.now(UTC)
    grouped: dict[int, list[TagConfig]] = defaultdict(list)
    timestamp = int(current.timestamp())
    for tag in tags:
        if not tag.enabled or tag.scan_interval_seconds <= 0:
            continue
        if timestamp % tag.scan_interval_seconds == 0:
            grouped[tag.machine_id].append(tag)
    return dict(grouped)
