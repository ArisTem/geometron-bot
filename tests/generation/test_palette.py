import random

import pytest

from geometron_bot.generation.palette import (
    PALETTE_CATALOG,
    GradientPalette,
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


def test_palette_catalog_contains_distinct_cyclic_gradients() -> None:
    assert len(set(PALETTE_CATALOG)) == len(PALETTE_CATALOG)
    assert all(palette.colors[0] == palette.colors[-1] for palette in PALETTE_CATALOG)


def test_random_palette_selection_is_deterministic() -> None:
    first = select_random_palette(random.Random(12345))
    second = select_random_palette(random.Random(12345))

    assert first == second
    assert first in PALETTE_CATALOG


def test_random_palette_selection_varies_across_seeds() -> None:
    selected_palettes = {
        select_random_palette(random.Random(seed)) for seed in range(32)
    }

    assert len(selected_palettes) > 1
