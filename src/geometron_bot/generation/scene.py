"""Ordered drawing instructions independent of image pixels."""

import math
from dataclasses import dataclass, field

from geometron_bot.generation.geometry import Polyline


@dataclass(frozen=True, slots=True)
class StrokeStyle:
    """Relative line width and color selection from the render palette.

    ``width_scale`` multiplies the renderer's base line width.
    ``palette_position=None`` keeps the gradient across a polyline's segments.
    A number from 0 to 1 chooses one color for the entire stroke.
    """

    width_scale: float = 1.0
    palette_position: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.width_scale, bool) or not isinstance(
            self.width_scale, (int, float)
        ):
            raise TypeError("Width scale must be a number")
        if not _is_finite(self.width_scale) or self.width_scale <= 0:
            raise ValueError("Width scale must be finite and positive")

        if self.palette_position is None:
            return
        if isinstance(self.palette_position, bool) or not isinstance(
            self.palette_position, (int, float)
        ):
            raise TypeError("Palette position must be a number or None")
        if not _is_finite(self.palette_position) or not 0 <= self.palette_position <= 1:
            raise ValueError("Palette position must be finite and between 0 and 1")


@dataclass(frozen=True, slots=True)
class Stroke:
    """Draw a polyline with one style."""

    polyline: Polyline
    style: StrokeStyle = field(default_factory=StrokeStyle)


@dataclass(frozen=True, slots=True)
class Scene:
    """Strokes in drawing order, expressed independently from image pixels."""

    strokes: tuple[Stroke, ...]


def _is_finite(value: float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:
        return False
