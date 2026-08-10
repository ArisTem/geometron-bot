"""Mathematical generation of Lissajous curves."""

import math
import random
from dataclasses import dataclass

from geometron_bot.generation.geometry import Polyline, Scene

_DEFAULT_SAMPLE_COUNT = 1_200
_FREQUENCY_PAIRS = tuple(
    (frequency_x, frequency_y)
    for frequency_x in range(1, 8)
    for frequency_y in range(1, 8)
    if frequency_x != frequency_y and math.gcd(frequency_x, frequency_y) == 1
)


@dataclass(frozen=True, slots=True)
class LissajousParameters:
    """Parameters of a Lissajous curve in mathematical world coordinates."""

    frequency_x: int
    frequency_y: int
    phase_shift: float
    sample_count: int = _DEFAULT_SAMPLE_COUNT

    def __post_init__(self) -> None:
        if self.frequency_x <= 0 or self.frequency_y <= 0:
            raise ValueError("Lissajous frequencies must be positive")
        if not math.isfinite(self.phase_shift):
            raise ValueError("Lissajous phase shift must be finite")
        if self.sample_count < 3:
            raise ValueError("Lissajous sample count must be at least 3")


def select_random_parameters(rng: random.Random) -> LissajousParameters:
    """Select a varied but non-degenerate set of Lissajous parameters."""
    frequency_x, frequency_y = rng.choice(_FREQUENCY_PAIRS)
    return LissajousParameters(
        frequency_x=frequency_x,
        frequency_y=frequency_y,
        phase_shift=rng.uniform(0.0, math.tau),
    )


def generate_lissajous(parameters: LissajousParameters) -> Scene:
    """Generate a closed Lissajous polyline without pixel-level concerns."""
    sample_times = (
        math.tau * sample_index / (parameters.sample_count - 1)
        for sample_index in range(parameters.sample_count - 1)
    )
    points = tuple(
        (
            math.sin(parameters.frequency_x * time + parameters.phase_shift),
            math.sin(parameters.frequency_y * time),
        )
        for time in sample_times
    )

    return Scene(polylines=(Polyline(points=(*points, points[0])),))
