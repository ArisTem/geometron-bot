"""Mathematical generation of hypotrochoid and epitrochoid curves."""

import math
import random
from dataclasses import dataclass
from typing import Literal

from geometron_bot.generation.geometry import Polyline
from geometron_bot.generation.scene import Scene, Stroke

type SpirographType = Literal["inside", "outside"]

_DEFAULT_SAMPLE_COUNT = 3_600
_RADIUS_PAIRS = tuple(
    (fixed_radius, rolling_radius)
    for fixed_radius in range(7, 14)
    for rolling_radius in range(2, 6)
    if math.gcd(fixed_radius, rolling_radius) == 1
)


@dataclass(frozen=True, slots=True)
class SpirographParameters:
    """The circles, drawing point, and sampling of one closed trajectory."""

    pattern_type: SpirographType
    fixed_radius: int
    rolling_radius: int
    point_distance: float
    sample_count: int = _DEFAULT_SAMPLE_COUNT

    def __post_init__(self) -> None:
        if self.pattern_type not in ("inside", "outside"):
            raise ValueError("Spirograph type must be 'inside' or 'outside'")
        if (
            isinstance(self.fixed_radius, bool)
            or not isinstance(self.fixed_radius, int)
            or isinstance(self.rolling_radius, bool)
            or not isinstance(self.rolling_radius, int)
            or not self.fixed_radius > self.rolling_radius > 0
        ):
            raise ValueError("Spirograph radii must be integers with R > r > 0")
        if (
            isinstance(self.point_distance, bool)
            or not isinstance(self.point_distance, (int, float))
            or not math.isfinite(self.point_distance)
            or self.point_distance <= 0
        ):
            raise ValueError("Spirograph point distance must be positive and finite")
        if (
            isinstance(self.sample_count, bool)
            or not isinstance(self.sample_count, int)
            or self.sample_count < 3
        ):
            raise ValueError("Spirograph sample count must be an integer at least 3")


def select_random_parameters(rng: random.Random) -> SpirographParameters:
    """Select a varied, reproducible shape from the first-version ranges."""
    pattern_type = rng.choice(("inside", "outside"))
    fixed_radius, rolling_radius = rng.choice(_RADIUS_PAIRS)
    return SpirographParameters(
        pattern_type=pattern_type,
        fixed_radius=fixed_radius,
        rolling_radius=rolling_radius,
        point_distance=rolling_radius * rng.uniform(0.65, 1.35),
    )


def generate_spirograph(parameters: SpirographParameters) -> Scene:
    """Sample one full period and close the polyline with its first point."""
    radius = parameters.fixed_radius
    rolling_radius = parameters.rolling_radius
    distance = parameters.point_distance
    period = math.tau * rolling_radius / math.gcd(radius, rolling_radius)
    if parameters.pattern_type == "inside":
        center_radius = radius - rolling_radius
        cosine_sign = 1
    else:
        center_radius = radius + rolling_radius
        cosine_sign = -1
    rotation = center_radius / rolling_radius
    sample_times = (
        period * index / (parameters.sample_count - 1)
        for index in range(parameters.sample_count - 1)
    )
    points = tuple(
        (
            center_radius * math.cos(time)
            + cosine_sign * distance * math.cos(rotation * time),
            center_radius * math.sin(time) - distance * math.sin(rotation * time),
        )
        for time in sample_times
    )

    if any(not math.isfinite(coordinate) for point in points for coordinate in point):
        raise ValueError("Spirograph coordinates must be finite")
    return Scene(strokes=(Stroke(polyline=Polyline(points=(*points, points[0]))),))
