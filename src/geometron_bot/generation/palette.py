"""Color palettes for rendered mathematical geometry."""

import math
import random
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


@dataclass(frozen=True, slots=True)
class SolidPalette:
    """A palette that returns one color for every drawing position."""

    color: Color

    def __post_init__(self) -> None:
        if not _is_valid_color(self.color):
            raise ValueError("Palette color must contain RGB values from 0 to 255")

    def color_at(self, position: float) -> Color:
        """Return the palette color for any finite drawing position."""
        if not math.isfinite(position):
            raise ValueError("Palette position must be finite")
        return self.color


def _is_valid_color(color: Color) -> bool:
    return len(color) == 3 and all(
        isinstance(channel, int) and 0 <= channel <= 255 for channel in color
    )


def _cyclic_palette(colors: tuple[Color, ...]) -> GradientPalette:
    """Create a gradient whose last stop returns to its first color."""
    if not colors:
        raise ValueError("A cyclic palette requires at least one color")
    return GradientPalette(colors=(*colors, colors[0]))


DEFAULT_PALETTE = _cyclic_palette(
    (
        (126, 87, 255),
        (0, 220, 200),
        (255, 211, 105),
        (255, 105, 180),
    )
)

GRADIENT_PALETTES = (
    DEFAULT_PALETTE,
    _cyclic_palette(
        (
            (34, 197, 94),
            (45, 212, 191),
            (56, 189, 248),
            (139, 92, 246),
        )
    ),
    _cyclic_palette(
        (
            (255, 77, 109),
            (255, 140, 66),
            (255, 209, 102),
            (168, 85, 247),
        )
    ),
    _cyclic_palette(
        (
            (0, 245, 212),
            (0, 187, 249),
            (67, 97, 238),
            (247, 37, 133),
        )
    ),
    _cyclic_palette(
        (
            (132, 204, 22),
            (250, 204, 21),
            (249, 115, 22),
            (20, 184, 166),
        )
    ),
    _cyclic_palette(
        (
            (239, 68, 68),
            (249, 115, 22),
            (250, 204, 21),
            (236, 72, 153),
        )
    ),
    _cyclic_palette(
        (
            (125, 211, 252),
            (186, 230, 253),
            (224, 231, 255),
            (196, 181, 253),
        )
    ),
    _cyclic_palette(
        (
            (16, 185, 129),
            (163, 230, 53),
            (251, 191, 36),
            (251, 113, 133),
        )
    ),
    _cyclic_palette(
        (
            (244, 63, 94),
            (168, 85, 247),
            (59, 130, 246),
            (34, 211, 238),
        )
    ),
    _cyclic_palette(
        (
            (192, 132, 252),
            (244, 114, 182),
            (251, 146, 60),
            (250, 204, 21),
        )
    ),
)


SOLID_PALETTES = (
    SolidPalette(color=(167, 139, 250)),
    SolidPalette(color=(56, 189, 248)),
    SolidPalette(color=(45, 212, 191)),
    SolidPalette(color=(74, 222, 128)),
    SolidPalette(color=(250, 204, 21)),
    SolidPalette(color=(251, 146, 60)),
    SolidPalette(color=(251, 113, 133)),
    SolidPalette(color=(244, 114, 182)),
)


def select_random_palette(rng: random.Random) -> Palette:
    """Select a palette type and palette deterministically with equal type odds."""
    catalog = rng.choice((GRADIENT_PALETTES, SOLID_PALETTES))
    return rng.choice(catalog)
