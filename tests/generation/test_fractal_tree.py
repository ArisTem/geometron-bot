import math
from collections import Counter
from dataclasses import replace
from random import Random
from unittest.mock import Mock

import pytest

from geometron_bot.generation.fractal_tree import (
    FractalTreeParameters,
    TreeFamily,
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
        "family": TreeFamily.SPREADING,
        "trunk_length": 1.0,
        "branch_asymmetry": 0.0,
        "prune_probability": 0.0,
        "wind_bias": 0.0,
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
        if level == 2:
            return index + 1
        left = index + 1
        right = check_subtree(left, level + 1)
        assert strokes[left].polyline.points[0] == stroke.polyline.points[1]
        assert strokes[right].polyline.points[0] == stroke.polyline.points[1]
        return check_subtree(right, level + 1)

    assert check_subtree(0, 0) == len(strokes)
    trunk, branch, tip = (stroke.style for stroke in strokes[:3])
    assert trunk.width_scale > branch.width_scale > tip.width_scale > 0
    assert (
        0
        <= trunk.palette_position
        < branch.palette_position
        < tip.palette_position
        <= 1
    )


def test_organic_tree_is_reproducible_and_changes_with_seed() -> None:
    settings = parameters(
        depth=5,
        variant=TreeVariant.ORGANIC,
        angle_jitter=math.radians(5),
        length_jitter=0.04,
        branch_asymmetry=0.3,
        prune_probability=0.4,
        wind_bias=0.05,
    )
    first = tree(settings, seed=12)
    assert first == tree(settings, seed=12)
    assert first != tree(settings, seed=13)


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
        ({"trunk_length": 0}, ValueError),
        ({"branch_asymmetry": -0.1}, ValueError),
        ({"branch_asymmetry": 1}, ValueError),
        ({"prune_probability": -0.1}, ValueError),
        ({"prune_probability": 1.1}, ValueError),
        ({"wind_bias": math.pi / 2}, ValueError),
        ({"wind_bias": -math.pi / 2}, ValueError),
        ({"family": "bush"}, TypeError),
        ({"variant": "symmetric"}, TypeError),
    ],
)
def test_invalid_parameters_are_rejected(changes, error_type) -> None:
    changes = {"variant": TreeVariant.ORGANIC, **changes}
    with pytest.raises(error_type, match="Tree"):
        parameters(**changes)


@pytest.mark.parametrize(
    "effect",
    [
        "angle_jitter",
        "length_jitter",
        "branch_asymmetry",
        "prune_probability",
        "wind_bias",
    ],
)
def test_symmetric_variant_rejects_asymmetric_effects(effect) -> None:
    with pytest.raises(ValueError, match="Symmetric"):
        parameters(**{effect: 0.1})


def test_selection_covers_all_families_and_both_variants_with_bounded_growth() -> None:
    variants = set()
    families = set()
    for seed in range(100):
        settings = select_random_parameters(
            RandomSource(seed).stream("fractal_tree.parameters")
        )
        # Even a full, unpruned tree stays within the existing 2047-branch budget.
        assert settings.depth <= 11
        # Jitter must not defeat length decay within the crown.
        assert settings.length_ratio * (1 + settings.length_jitter) < 1
        if settings.family is TreeFamily.WINDSWEPT:
            assert settings.wind_bias * settings.trunk_tilt > 0
        variants.add(settings.variant)
        families.add(settings.family)
    assert variants == set(TreeVariant)
    assert families == set(TreeFamily)


def test_trunk_length_changes_without_rescaling_the_crown() -> None:
    scene = tree(parameters(depth=2, trunk_length=2.0))

    assert scene.strokes[0].polyline.points[1] == pytest.approx((0.0, 2.0))
    for stroke in scene.strokes[1:]:
        assert stroke.polyline.points[0] == scene.strokes[0].polyline.points[1]
        assert math.dist(*stroke.polyline.points) == pytest.approx(0.5)


def test_asymmetry_keeps_a_long_leader_and_a_shorter_wider_side_branch() -> None:
    scene = tree(parameters(depth=2, variant=TreeVariant.ORGANIC, branch_asymmetry=0.5))
    leader, side = sorted(
        scene.strokes[1:],
        key=lambda stroke: math.dist(*stroke.polyline.points),
        reverse=True,
    )

    assert math.dist(*leader.polyline.points) == pytest.approx(0.5)
    assert math.dist(*side.polyline.points) == pytest.approx(0.25)

    def deviation(stroke):
        start, end = stroke.polyline.points
        return abs(math.atan2(end[1] - start[1], end[0] - start[0]) - math.pi / 2)

    assert deviation(leader) == pytest.approx(math.pi / 8)
    assert deviation(side) == pytest.approx(3 * math.pi / 8)


def test_pruning_can_leave_a_single_child_without_breaking_connections() -> None:
    settings = parameters(
        depth=4,
        variant=TreeVariant.ORGANIC,
        branch_angle=math.pi / 6,
        prune_probability=0.5,
    )
    rng = Mock(spec=Random)
    rng.uniform.side_effect = lambda minimum, maximum: (minimum + maximum) / 2
    # Beyond the protected forks, omit one child and retain the other.
    rng.random.side_effect = [0.25, 0.75] * 4
    scene = generate_fractal_tree(settings, rng)

    children = Counter(stroke.polyline.points[0] for stroke in scene.strokes[1:])
    assert 1 in children.values()

    ends = {scene.strokes[0].polyline.points[1]}
    for stroke in scene.strokes[1:]:
        start, end = stroke.polyline.points
        assert start in ends
        ends.add(end)


def test_maximum_pruning_preserves_the_first_two_forks() -> None:
    scene = tree(
        parameters(depth=8, variant=TreeVariant.ORGANIC, prune_probability=1.0)
    )
    assert len(scene.strokes) == 7


def test_wind_accumulates_in_both_directions_without_moving_the_trunk() -> None:
    settings = parameters(
        depth=3, variant=TreeVariant.ORGANIC, branch_angle=math.pi / 6
    )
    calm = tree(settings)

    def direction(stroke):
        start, end = stroke.polyline.points
        return math.atan2(end[1] - start[1], end[0] - start[0])

    for bias in (0.2, -0.2):
        windy = tree(replace(settings, wind_bias=bias))
        assert windy.strokes[0] == calm.strokes[0]
        assert direction(windy.strokes[1]) - direction(
            calm.strokes[1]
        ) == pytest.approx(bias)
        assert direction(windy.strokes[2]) - direction(
            calm.strokes[2]
        ) == pytest.approx(2 * bias)
