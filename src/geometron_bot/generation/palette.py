"""Color palettes for rendered mathematical geometry."""

import math
from dataclasses import dataclass
from typing import Protocol

type Color = tuple[int, int, int]


class Palette(Protocol):
    """Map a normalized drawing position to an RGB color."""

    def color_at(self, position: float) -> Color:
        """Return the color at a position between zero and one."""
        ...


@dataclass(frozen=True, slots=True)
class GradientPalette:
    """A linear RGB gradient defined by two or more color stops."""

    colors: tuple[Color, ...]

    def __post_init__(self) -> None:
        if len(self.colors) < 2:
            raise ValueError("A gradient palette requires at least two colors")
        if any(not _is_valid_color(color) for color in self.colors):
            raise ValueError("Palette colors must contain RGB values from 0 to 255")

    def color_at(self, position: float) -> Color:
        """Interpolate a color, clamping positions outside the normalized range."""
        if not math.isfinite(position):
            raise ValueError("Palette position must be finite")

        clamped_position = min(max(position, 0.0), 1.0)
        scaled_position = clamped_position * (len(self.colors) - 1)
        left_index = min(int(scaled_position), len(self.colors) - 2)
        fraction = scaled_position - left_index
        left_color = self.colors[left_index]
        right_color = self.colors[left_index + 1]

        return tuple(
            round(left_channel + (right_channel - left_channel) * fraction)
            for left_channel, right_channel in zip(left_color, right_color, strict=True)
        )


def _is_valid_color(color: Color) -> bool:
    return len(color) == 3 and all(
        isinstance(channel, int) and 0 <= channel <= 255 for channel in color
    )


DEFAULT_PALETTE = GradientPalette(
    colors=(
        (126, 87, 255),
        (0, 220, 200),
        (255, 211, 105),
        (255, 105, 180),
        (126, 87, 255),
    )
)
