"""Renderer-independent geometry in mathematical world coordinates."""

from dataclasses import dataclass

type Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Polyline:
    """An ordered sequence of points in mathematical world coordinates."""

    points: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class Scene:
    """Geometry to be rendered, expressed independently from image pixels."""

    polylines: tuple[Polyline, ...]
