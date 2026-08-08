from __future__ import annotations

from collections.abc import Iterable
from typing import Callable, TypeVar

T = TypeVar("T")


def within_radius(
    items: Iterable[T],
    radius_km: float,
    distance_getter: Callable[[T], float | None],
) -> list[T]:
    """Return items with known distance inside the requested radius."""

    selected: list[T] = []
    for item in items:
        distance = distance_getter(item)
        if distance is not None and distance <= radius_km:
            selected.append(item)
    return selected
