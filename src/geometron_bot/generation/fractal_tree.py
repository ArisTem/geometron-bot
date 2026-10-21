"""Renderer-independent geometry and styles for varied fractal trees."""

import math
import random
from dataclasses import dataclass
from enum import Enum

from geometron_bot.generation.geometry import Point, Polyline
from geometron_bot.generation.scene import Scene, Stroke, StrokeStyle


class TreeVariant(str, Enum):
    SYMMETRIC = "symmetric"
    ORGANIC = "organic"


class TreeFamily(str, Enum):
    SLENDER = "slender"
    SPREADING = "spreading"
    BUSH = "bush"
    WINDSWEPT = "windswept"
    SPARSE = "sparse"


@dataclass(frozen=True, slots=True)
class FractalTreeParameters:
    """Shape settings shared by every branch in one tree.

    Lengths are relative to a unit trunk: ``trunk_length`` changes only the
    trunk, leaving the crown's branch lengths unchanged. At each fork,
    ``branch_asymmetry`` shortens and spreads one randomly selected side.
    ``prune_probability`` omits individual children beyond the first two forks;
    ``wind_bias`` turns every non-trunk branch in the same direction.
    """

    depth: int
    length_ratio: float
    branch_angle: float
    trunk_tilt: float
    angle_jitter: float
    length_jitter: float
    variant: TreeVariant
    family: TreeFamily
    trunk_length: float
    branch_asymmetry: float
    prune_probability: float
    wind_bias: float

    def __post_init__(self) -> None:
        if isinstance(self.depth, bool) or not isinstance(self.depth, int):
            raise TypeError("Tree depth must be an integer")
        if self.depth < 1:
            raise ValueError("Tree depth must be at least 1")

        for name, value in (
            ("length_ratio", self.length_ratio),
            ("branch_angle", self.branch_angle),
            ("trunk_tilt", self.trunk_tilt),
            ("angle_jitter", self.angle_jitter),
            ("length_jitter", self.length_jitter),
            ("trunk_length", self.trunk_length),
            ("branch_asymmetry", self.branch_asymmetry),
            ("prune_probability", self.prune_probability),
            ("wind_bias", self.wind_bias),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"Tree {name} must be a number")
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"Tree {name} must be finite")

        if not 0 < self.length_ratio < 1:
            raise ValueError("Tree length_ratio must be between 0 and 1")
        if not 0 < self.branch_angle < math.pi / 2:
            raise ValueError("Tree branch_angle must be between 0 and pi/2")
        if not 0 <= self.angle_jitter < math.pi / 2:
            raise ValueError("Tree angle_jitter must be between 0 and pi/2")
        if not 0 <= self.length_jitter < 1:
            raise ValueError("Tree length_jitter must be between 0 and 1")
        if self.trunk_length <= 0:
            raise ValueError("Tree trunk_length must be positive")
        if not 0 <= self.branch_asymmetry < 1:
            raise ValueError("Tree branch_asymmetry must be between 0 and 1")
        if not 0 <= self.prune_probability <= 1:
            raise ValueError("Tree prune_probability must be between 0 and 1 inclusive")
        if not -math.pi / 2 < self.wind_bias < math.pi / 2:
            raise ValueError("Tree wind_bias must be between -pi/2 and pi/2")
        if not isinstance(self.family, TreeFamily):
            raise TypeError("Tree family must be a TreeFamily")
        if not isinstance(self.variant, TreeVariant):
            raise TypeError("Tree variant must be a TreeVariant")
        if self.variant is TreeVariant.SYMMETRIC and (
            self.angle_jitter != 0
            or self.length_jitter != 0
            or self.branch_asymmetry != 0
            or self.prune_probability != 0
            or self.wind_bias != 0
        ):
            raise ValueError(
                "Symmetric tree jitter, asymmetry, pruning and wind must be zero"
            )


@dataclass(frozen=True, slots=True)
class _TreeProfile:
    """Coordinated ranges for one silhouette; angular ranges are in degrees."""

    depth: tuple[int, int]
    length_ratio: tuple[float, float]
    branch_angle: tuple[float, float]
    trunk_length: tuple[float, float]
    branch_asymmetry: tuple[float, float]
    prune_probability: tuple[float, float]


_PROFILES = {
    TreeFamily.SLENDER: _TreeProfile(
        depth=(10, 11),
        length_ratio=(0.74, 0.81),
        branch_angle=(12, 22),
        trunk_length=(1.1, 1.6),
        branch_asymmetry=(0.35, 0.55),
        prune_probability=(0.03, 0.10),
    ),
    TreeFamily.SPREADING: _TreeProfile(
        depth=(9, 11),
        length_ratio=(0.67, 0.77),
        branch_angle=(30, 48),
        trunk_length=(0.65, 1.1),
        branch_asymmetry=(0.05, 0.22),
        prune_probability=(0.0, 0.07),
    ),
    TreeFamily.BUSH: _TreeProfile(
        depth=(9, 11),
        length_ratio=(0.74, 0.83),
        branch_angle=(25, 45),
        trunk_length=(0.15, 0.4),
        branch_asymmetry=(0.08, 0.30),
        prune_probability=(0.02, 0.10),
    ),
    TreeFamily.WINDSWEPT: _TreeProfile(
        depth=(9, 11),
        length_ratio=(0.71, 0.80),
        branch_angle=(20, 35),
        trunk_length=(0.6, 1.0),
        branch_asymmetry=(0.15, 0.40),
        prune_probability=(0.04, 0.12),
    ),
    TreeFamily.SPARSE: _TreeProfile(
        depth=(8, 10),
        length_ratio=(0.65, 0.78),
        branch_angle=(22, 42),
        trunk_length=(0.9, 1.4),
        branch_asymmetry=(0.20, 0.50),
        prune_probability=(0.28, 0.50),
    ),
}


def select_random_parameters(rng: random.Random) -> FractalTreeParameters:
    """Choose a silhouette, then vary its shape with a reproducible seed."""
    family = rng.choice(tuple(TreeFamily))
    profile = _PROFILES[family]
    # Retain occasional perfectly regular trees among the spreading crowns.
    variant = (
        rng.choice(tuple(TreeVariant))
        if family is TreeFamily.SPREADING
        else TreeVariant.ORGANIC
    )
    organic = variant is TreeVariant.ORGANIC
    wind_direction = rng.choice((-1, 1)) if family is TreeFamily.WINDSWEPT else 0
    return FractalTreeParameters(
        depth=rng.randint(*profile.depth),
        length_ratio=rng.uniform(*profile.length_ratio),
        branch_angle=math.radians(rng.uniform(*profile.branch_angle)),
        trunk_tilt=math.radians(
            wind_direction * rng.uniform(10, 20)
            if wind_direction
            else rng.uniform(-5, 5)
        ),
        angle_jitter=math.radians(rng.uniform(2, 6)) if organic else 0.0,
        length_jitter=rng.uniform(0.02, 0.08) if organic else 0.0,
        variant=variant,
        family=family,
        trunk_length=rng.uniform(*profile.trunk_length),
        branch_asymmetry=rng.uniform(*profile.branch_asymmetry) if organic else 0.0,
        prune_probability=rng.uniform(*profile.prune_probability) if organic else 0.0,
        wind_bias=math.radians(wind_direction * rng.uniform(3, 6))
        if wind_direction
        else 0.0,
    )


def generate_fractal_tree(
    parameters: FractalTreeParameters, rng: random.Random
) -> Scene:
    """Build strokes in preorder: branch, left subtree, right subtree."""
    strokes: list[Stroke] = []
    # Entries hold the start, base length, base angle, and level of a branch.
    # Pushing right first lets the left subtree consume its random draws first.
    pending: list[tuple[Point, float, float, int]] = [
        ((0.0, 0.0), parameters.trunk_length, math.pi / 2 + parameters.trunk_tilt, 0)
    ]
    while pending:
        start, length, angle, level = pending.pop()
        if level and parameters.variant is TreeVariant.ORGANIC:
            angle += parameters.wind_bias
            angle += rng.uniform(-parameters.angle_jitter, parameters.angle_jitter)
            length *= rng.uniform(
                1 - parameters.length_jitter, 1 + parameters.length_jitter
            )
        end = (start[0] + length * math.cos(angle), start[1] + length * math.sin(angle))
        if not all(math.isfinite(value) for value in end):
            raise ValueError("Tree coordinates must be finite")

        progress = level / (parameters.depth - 1) if parameters.depth > 1 else 0.0
        style = StrokeStyle(
            width_scale=0.35 + 3.65 * (1 - progress) ** 1.5,
            palette_position=0.75 * progress,
        )
        strokes.append(Stroke(polyline=Polyline(points=(start, end)), style=style))

        if level + 1 < parameters.depth:
            # Changing trunk length must not rescale the entire tree.
            child_length = (length if level else 1.0) * parameters.length_ratio
            child_level = level + 1
            dominant_side = rng.choice((-1, 1)) if parameters.branch_asymmetry else 0
            for side in (-1, 1):
                # Protect the base of the crown so pruning cannot leave only a trunk.
                if (
                    level >= 2
                    and parameters.prune_probability
                    and rng.random() < parameters.prune_probability
                ):
                    continue
                dominant = side == dominant_side
                asymmetry = parameters.branch_asymmetry
                length_scale = 1.0 if dominant else 1 - asymmetry
                angle_scale = 1 - asymmetry if dominant else 1 + asymmetry
                pending.append(
                    (
                        end,
                        child_length * length_scale,
                        angle + side * parameters.branch_angle * angle_scale,
                        child_level,
                    )
                )

    return Scene(strokes=tuple(strokes))
