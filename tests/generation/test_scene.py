import math

import pytest

from geometron_bot.generation.geometry import Polyline
from geometron_bot.generation.scene import Scene, Stroke, StrokeStyle


def test_stroke_accepts_default_and_boundary_styles() -> None:
    points = ((0.0, 0.0), (1.0, 1.0))
    polyline = Polyline(points)
    scene = Scene(strokes=(Stroke(polyline),))

    assert scene.strokes[0].polyline is polyline
    assert scene.strokes[0].style == StrokeStyle()
    assert StrokeStyle(width_scale=1e-10, palette_position=0.0).width_scale == 1e-10
    assert StrokeStyle(width_scale=2, palette_position=1.0).palette_position == 1.0


@pytest.mark.parametrize("width_scale", [0, -1, math.nan, math.inf, -math.inf, 10**400])
def test_style_rejects_invalid_width_scale_values(width_scale: float) -> None:
    with pytest.raises(ValueError, match="Width scale"):
        StrokeStyle(width_scale=width_scale)


@pytest.mark.parametrize("width_scale", [True, False, None, "2"])
def test_style_rejects_non_numeric_width_scale(width_scale: object) -> None:
    with pytest.raises(TypeError, match="Width scale"):
        StrokeStyle(width_scale=width_scale)


@pytest.mark.parametrize(
    "palette_position", [-0.1, 1.1, math.nan, math.inf, -math.inf, 10**400]
)
def test_style_rejects_invalid_palette_positions(palette_position: float) -> None:
    with pytest.raises(ValueError, match="Palette position"):
        StrokeStyle(palette_position=palette_position)


@pytest.mark.parametrize("palette_position", [True, False, "0.5"])
def test_style_rejects_non_numeric_palette_positions(
    palette_position: object,
) -> None:
    with pytest.raises(TypeError, match="Palette position"):
        StrokeStyle(palette_position=palette_position)
