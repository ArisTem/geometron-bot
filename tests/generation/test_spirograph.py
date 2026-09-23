import math

import pytest

from geometron_bot.generation.random_source import RandomSource
from geometron_bot.generation.spirograph import (
    SpirographParameters,
    generate_spirograph,
    select_random_parameters,
)


@pytest.mark.parametrize(
    ("pattern_type", "radius", "rolling_radius", "distance", "first", "second"),
    [
        ("inside", 5, 2, 1.0, (4, 0), (-math.sqrt(0.5), 3 - math.sqrt(0.5))),
        ("outside", 5, 2, 1.0, (6, 0), (-math.sqrt(0.5), 7 + math.sqrt(0.5))),
        ("inside", 6, 4, 2.0, (4, 0), (math.sqrt(2), 2 - math.sqrt(2))),
    ],
)
def test_coordinates_and_closed_period(
    pattern_type, radius, rolling_radius, distance, first, second
) -> None:
    parameters = SpirographParameters(
        pattern_type, radius, rolling_radius, distance, sample_count=9
    )

    points = generate_spirograph(parameters).polylines[0].points

    assert len(points) == 9
    assert points[0] == pytest.approx(first)
    assert points[1] == pytest.approx(second)
    assert points[-1] == points[0]


@pytest.mark.parametrize(
    "changes",
    [
        {"pattern_type": "unknown"},
        {"fixed_radius": 2},
        {"rolling_radius": 0},
        {"rolling_radius": True},
        {"point_distance": 0},
        {"point_distance": math.nan},
        {"sample_count": 2},
        {"sample_count": True},
    ],
)
def test_invalid_parameters_are_rejected(changes) -> None:
    values = {
        "pattern_type": "inside",
        "fixed_radius": 7,
        "rolling_radius": 2,
        "point_distance": 2.0,
        "sample_count": 9,
    }
    values.update(changes)

    with pytest.raises(ValueError, match="Spirograph"):
        SpirographParameters(**values)


def test_random_parameters_use_expected_ranges() -> None:
    types = set()
    for seed in range(20):
        parameters = select_random_parameters(
            RandomSource(seed).stream("spirograph.parameters")
        )
        assert 7 <= parameters.fixed_radius <= 13
        assert 2 <= parameters.rolling_radius <= 5
        assert math.gcd(parameters.fixed_radius, parameters.rolling_radius) == 1
        assert 0.65 <= parameters.point_distance / parameters.rolling_radius <= 1.35
        assert parameters.sample_count == 3_600
        types.add(parameters.pattern_type)

    assert types == {"inside", "outside"}
