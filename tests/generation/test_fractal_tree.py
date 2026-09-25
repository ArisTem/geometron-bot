import math

import pytest

from geometron_bot.generation.fractal_tree import (
    FractalTreeParameters,
    TreeVariant,
    generate_fractal_tree,
    select_random_parameters,
)
from geometron_bot.generation.random_source import RandomSource


def parameters(**changes) -> FractalTreeParameters:
    values = {
        "depth": 3,
        "length_ratio": 0.5,
        "branch_angle": math.pi / 4,
        "trunk_tilt": 0.0,
        "angle_jitter": 0.0,
        "length_jitter": 0.0,
        "variant": TreeVariant.SYMMETRIC,
    }
    values.update(changes)
    return FractalTreeParameters(**values)


def tree(settings: FractalTreeParameters, seed: int = 42):
    return generate_fractal_tree(
        settings, RandomSource(seed).stream("fractal_tree.branches")
    )


def test_vertical_trunk_at_depth_one() -> None:
    scene = tree(parameters(depth=1))

    assert len(scene.strokes) == 1
    assert scene.strokes[0].polyline.points[0] == (0.0, 0.0)
    assert scene.strokes[0].polyline.points[1] == pytest.approx((0.0, 1.0))
    assert scene.strokes[0].style.palette_position == 0.0
    assert scene.strokes[0].style.width_scale == 4.0


def test_preorder_geometry_and_parent_connections() -> None:
    scene = tree(parameters(depth=3))
    strokes = scene.strokes
    assert len(strokes) == 7
    trunk_end = strokes[0].polyline.points[1]
    assert strokes[1].polyline.points[0] == trunk_end
    assert strokes[1].polyline.points[1] == pytest.approx(
        (-math.sqrt(0.125), 1 + math.sqrt(0.125))
    )
    assert strokes[4].polyline.points[0] == trunk_end
    assert strokes[4].polyline.points[1] == pytest.approx(
        (math.sqrt(0.125), 1 + math.sqrt(0.125))
    )

    def check_subtree(index: int, level: int) -> int:
        stroke = strokes[index]
        assert len(stroke.polyline.points) == 2
        assert all(
            math.isfinite(coordinate)
            for point in stroke.polyline.points
            for coordinate in point
        )
        expected_progress = level / 2
        assert stroke.style.palette_position == pytest.approx(0.75 * expected_progress)
        assert stroke.style.width_scale == pytest.approx(
            0.35 + 3.65 * (1 - expected_progress) ** 1.5
        )
        if level == 2:
            return index + 1
        left = index + 1
        right = check_subtree(left, level + 1)
        assert strokes[left].polyline.points[0] == stroke.polyline.points[1]
        assert strokes[right].polyline.points[0] == stroke.polyline.points[1]
        return check_subtree(right, level + 1)

    assert check_subtree(0, 0) == len(strokes)


def test_organic_tree_is_reproducible_and_changes_with_seed() -> None:
    settings = parameters(
        depth=5,
        variant=TreeVariant.ORGANIC,
        angle_jitter=math.radians(5),
        length_jitter=0.04,
    )
    first = tree(settings, seed=12)
    assert first == tree(settings, seed=12)
    assert first != tree(settings, seed=13)
    assert len(first.strokes) == 2**settings.depth - 1


@pytest.mark.parametrize(
    ("changes", "error_type"),
    [
        ({"depth": 0}, ValueError),
        ({"depth": True}, TypeError),
        ({"depth": 2.5}, TypeError),
        ({"length_ratio": 0}, ValueError),
        ({"length_ratio": 1}, ValueError),
        ({"length_ratio": True}, TypeError),
        ({"branch_angle": math.pi / 2}, ValueError),
        ({"branch_angle": math.nan}, ValueError),
        ({"trunk_tilt": math.inf}, ValueError),
        ({"angle_jitter": -0.01}, ValueError),
        ({"angle_jitter": math.pi / 2}, ValueError),
        ({"length_jitter": 1}, ValueError),
        ({"length_jitter": False}, TypeError),
        ({"variant": "symmetric"}, TypeError),
        ({"angle_jitter": 0.1}, ValueError),
    ],
)
def test_invalid_parameters_are_rejected(changes, error_type) -> None:
    with pytest.raises(error_type, match="Tree|Symmetric"):
        parameters(**changes)


def test_selected_ranges_and_both_variants() -> None:
    variants = set()
    for seed in range(100):
        settings = select_random_parameters(
            RandomSource(seed).stream("fractal_tree.parameters")
        )
        assert 9 <= settings.depth <= 11
        assert 0.67 <= settings.length_ratio <= 0.75
        assert math.radians(21) <= settings.branch_angle <= math.radians(34)
        assert math.radians(-4) <= settings.trunk_tilt <= math.radians(4)
        if settings.variant is TreeVariant.SYMMETRIC:
            assert settings.angle_jitter == settings.length_jitter == 0
        else:
            assert math.radians(2) <= settings.angle_jitter <= math.radians(7)
            assert 0 <= settings.length_jitter <= 0.06
        variants.add(settings.variant)
    assert variants == set(TreeVariant)
