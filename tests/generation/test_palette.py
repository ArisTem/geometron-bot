import pytest

from geometron_bot.generation.palette import GradientPalette


def test_gradient_palette_interpolates_between_color_stops() -> None:
    palette = GradientPalette(colors=((0, 20, 100), (100, 220, 200)))

    assert palette.color_at(0.0) == (0, 20, 100)
    assert palette.color_at(0.5) == (50, 120, 150)
    assert palette.color_at(1.0) == (100, 220, 200)


def test_gradient_palette_clamps_positions_to_its_ends() -> None:
    palette = GradientPalette(colors=((10, 20, 30), (40, 50, 60)))

    assert palette.color_at(-1.0) == (10, 20, 30)
    assert palette.color_at(2.0) == (40, 50, 60)


@pytest.mark.parametrize(
    "colors",
    [
        ((0, 0, 0),),
        ((0, 0, 0), (256, 0, 0)),
    ],
)
def test_gradient_palette_rejects_invalid_colors(colors) -> None:
    with pytest.raises(ValueError):
        GradientPalette(colors=colors)
