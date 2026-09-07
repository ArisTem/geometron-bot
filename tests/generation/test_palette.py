import random

import pytest

from geometron_bot.generation.palette import (
    GRADIENT_PALETTES,
    SOLID_PALETTES,
    GradientPalette,
    SolidPalette,
    select_random_palette,
)


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


def test_solid_palette_returns_the_same_color_at_every_position() -> None:
    color = (10, 20, 30)
    palette = SolidPalette(color=color)

    assert {palette.color_at(position) for position in (-1.0, 0.0, 0.5, 1.0, 2.0)} == {
        color
    }


def test_solid_palette_rejects_an_invalid_color() -> None:
    with pytest.raises(ValueError):
        SolidPalette(color=(256, 0, 0))


def test_palette_catalogs_contain_distinct_palettes_and_cyclic_gradients() -> None:
    all_palettes = (*GRADIENT_PALETTES, *SOLID_PALETTES)

    assert len(set(all_palettes)) == len(all_palettes)
    assert all(palette.colors[0] == palette.colors[-1] for palette in GRADIENT_PALETTES)


def test_random_palette_selection_is_deterministic() -> None:
    first = select_random_palette(random.Random(12345))
    second = select_random_palette(random.Random(12345))

    assert first == second


def test_random_palette_selection_can_select_each_palette_type() -> None:
    selected_palettes = {
        select_random_palette(random.Random(seed)) for seed in range(32)
    }

    assert {type(palette) for palette in selected_palettes} == {
        GradientPalette,
        SolidPalette,
    }
