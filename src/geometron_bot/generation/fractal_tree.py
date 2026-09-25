"""Renderer-independent geometry and styles for binary fractal trees."""

import math
import random
from dataclasses import dataclass
from enum import Enum

from geometron_bot.generation.geometry import Point, Polyline
from geometron_bot.generation.scene import Scene, Stroke, StrokeStyle


class TreeVariant(str, Enum):
    SYMMETRIC = "symmetric"
    ORGANIC = "organic"


@dataclass(frozen=True, slots=True)
class FractalTreeParameters:
    """Shape settings shared by every branch in one tree."""

    depth: int
    length_ratio: float
    branch_angle: float
    trunk_tilt: float
    angle_jitter: float
    length_jitter: float
    variant: TreeVariant

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
        if not isinstance(self.variant, TreeVariant):
            raise TypeError("Tree variant must be a TreeVariant")
        if self.variant is TreeVariant.SYMMETRIC and (
            self.angle_jitter != 0 or self.length_jitter != 0
        ):
            raise ValueError("Symmetric tree jitter must be zero")


def select_random_parameters(rng: random.Random) -> FractalTreeParameters:
    """Select the first-version depth, shape, and variant ranges."""
    variant = rng.choice(tuple(TreeVariant))
    return FractalTreeParameters(
        depth=rng.randint(9, 11),
        length_ratio=rng.uniform(0.67, 0.75),
        branch_angle=math.radians(rng.uniform(21, 34)),
        trunk_tilt=math.radians(rng.uniform(-4, 4)),
        angle_jitter=(
            math.radians(rng.uniform(2, 7))
            if variant is TreeVariant.ORGANIC
            else 0.0
        ),
        length_jitter=(
            rng.uniform(0.0, 0.06) if variant is TreeVariant.ORGANIC else 0.0
        ),
        variant=variant,
    )


def generate_fractal_tree(
    parameters: FractalTreeParameters, rng: random.Random
) -> Scene:
    """Build strokes in preorder: branch, left subtree, right subtree."""
    strokes: list[Stroke] = []
    # Entries hold the start, base length, base angle, and level of a branch.
    # Pushing right first lets the left subtree consume its random draws first.
    pending: list[tuple[Point, float, float, int]] = [
        ((0.0, 0.0), 1.0, math.pi / 2 + parameters.trunk_tilt, 0)
    ]
    while pending:
        start, length, angle, level = pending.pop()
        if level and parameters.variant is TreeVariant.ORGANIC:
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
            child_length = length * parameters.length_ratio
            child_level = level + 1
            pending.append((end, child_length, angle - parameters.branch_angle, child_level))
            pending.append((end, child_length, angle + parameters.branch_angle, child_level))

    return Scene(strokes=tuple(strokes))
