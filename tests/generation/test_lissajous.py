import math
import random

import pytest

from geometron_bot.generation.lissajous import (
    LissajousParameters,
    generate_lissajous,
    select_random_parameters,
)
from geometron_bot.generation.random_source import RandomSource


def test_parameter_selection_is_deterministic_for_seed() -> None:
    first = select_random_parameters(
        RandomSource(12345).stream("lissajous.parameters")
    )
    second = select_random_parameters(
        RandomSource(12345).stream("lissajous.parameters")
    )

    assert first == second


def test_parameter_selection_does_not_depend_on_global_random_state() -> None:
    random.seed(1)
    first = select_random_parameters(RandomSource(12345).stream("lissajous.parameters"))
    random.seed(999)
    second = select_random_parameters(
        RandomSource(12345).stream("lissajous.parameters")
    )

    assert first == second


def test_random_frequencies_avoid_simple_degenerate_combinations() -> None:
    for seed in range(100):
        parameters = select_random_parameters(
            RandomSource(seed).stream("lissajous.parameters")
        )

        assert 1 <= parameters.frequency_x <= 7
        assert 1 <= parameters.frequency_y <= 7
        assert parameters.frequency_x != parameters.frequency_y
        assert math.gcd(parameters.frequency_x, parameters.frequency_y) == 1


def test_generate_lissajous_produces_expected_world_coordinates() -> None:
    parameters = LissajousParameters(
        frequency_x=1,
        frequency_y=2,
        phase_shift=math.pi / 2,
        sample_count=9,
    )

    scene = generate_lissajous(parameters)

    assert len(scene.polylines) == 1
    assert len(scene.polylines[0].points) == parameters.sample_count
    assert scene.polylines[0].points[0] == pytest.approx((1.0, 0.0))
    assert scene.polylines[0].points[1] == pytest.approx((math.sqrt(0.5), 1.0))
    assert scene.polylines[0].points[-1] == scene.polylines[0].points[0]
