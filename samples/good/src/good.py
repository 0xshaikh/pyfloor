"""A clean module using only pre-3.10 features (no match, no tomllib)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class Point:
    x: float
    y: float

    def dist(self) -> float:
        return (self.x * self.x + self.y * self.y) ** 0.5


def scale(points: List[Point], factor: float) -> List[Point]:
    return [Point(p.x * factor, p.y * factor) for p in points]


def maybe_value(flag: bool) -> Optional[str]:
    if flag:
        return "yes"
    return None


def union_demo(value: Union[int, str]) -> str:
    return str(value)
