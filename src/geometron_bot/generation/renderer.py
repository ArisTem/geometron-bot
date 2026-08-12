"""Pillow rendering of mathematical scenes."""

import math
from dataclasses import dataclass
from io import BytesIO
from itertools import pairwise

from PIL import Image, ImageDraw

from geometron_bot.generation.geometry import Point, Scene
from geometron_bot.generation.palette import Color, Palette


@dataclass(frozen=True, slots=True)
class RenderConfig:
    """Pixel-level settings for square image rendering."""

    image_size: int = 1_024
    margin: int = 64
    background_color: Color = (7, 10, 24)
    line_width: int = 3
    supersampling: int = 4

    def __post_init__(self) -> None:
        if self.image_size < 2:
            raise ValueError("Image size must be at least 2 pixels")
        if self.margin < 0 or self.margin * 2 >= self.image_size:
            raise ValueError("Margin must leave space for drawing")
        if not _is_valid_color(self.background_color):
            raise ValueError("Background color must contain RGB values from 0 to 255")
        if self.line_width <= 0:
            raise ValueError("Line width must be positive")
        if self.supersampling <= 0:
            raise ValueError("Supersampling factor must be positive")


class PillowRenderer:
    """Render world-coordinate polylines to an antialiased PNG stream."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self._config = config or RenderConfig()

    def render(self, scene: Scene, palette: Palette) -> BytesIO:
        """Render a scene and return a PNG stream positioned at its beginning."""
        world_points = tuple(
            point for polyline in scene.polylines for point in polyline.points
        )
        if not world_points:
            raise ValueError("Scene must contain at least one point")
        if any(not _is_finite_point(point) for point in world_points):
            raise ValueError("Scene points must contain finite coordinates")

        config = self._config
        scale_factor = config.supersampling
        working_size = config.image_size * scale_factor
        working_margin = config.margin * scale_factor
        transform = _create_transform(world_points, working_size, working_margin)

        image = Image.new(
            "RGB",
            (working_size, working_size),
            color=config.background_color,
        )
        drawing = ImageDraw.Draw(image)
        working_line_width = config.line_width * scale_factor

        for polyline in scene.polylines:
            image_points = tuple(transform(point) for point in polyline.points)
            if len(image_points) == 1:
                _draw_point(
                    drawing,
                    image_points[0],
                    palette.color_at(0.0),
                    working_line_width,
                )
                continue

            final_segment_index = len(image_points) - 2
            for segment_index, (start, end) in enumerate(pairwise(image_points)):
                position = (
                    segment_index / final_segment_index
                    if final_segment_index > 0
                    else 0.0
                )
                drawing.line(
                    (start, end),
                    fill=palette.color_at(position),
                    width=working_line_width,
                )

        if scale_factor > 1:
            image = image.resize(
                (config.image_size, config.image_size),
                resample=Image.Resampling.LANCZOS,
            )

        output = BytesIO()
        image.save(output, format="PNG")
        output.seek(0)
        return output


def _create_transform(points: tuple[Point, ...], image_size: int, margin: int):
    minimum_x = min(point[0] for point in points)
    maximum_x = max(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_y = max(point[1] for point in points)

    world_center_x = (minimum_x + maximum_x) / 2
    world_center_y = (minimum_y + maximum_y) / 2
    world_span = max(maximum_x - minimum_x, maximum_y - minimum_y)
    drawable_span = image_size - 1 - 2 * margin
    scale = drawable_span / world_span if world_span > 0 else 1.0
    image_center = (image_size - 1) / 2

    def transform(point: Point) -> tuple[float, float]:
        return (
            image_center + (point[0] - world_center_x) * scale,
            image_center - (point[1] - world_center_y) * scale,
        )

    return transform


def _draw_point(
    drawing: ImageDraw.ImageDraw,
    point: tuple[float, float],
    color: Color,
    diameter: int,
) -> None:
    radius = diameter / 2
    drawing.ellipse(
        (
            point[0] - radius,
            point[1] - radius,
            point[0] + radius,
            point[1] + radius,
        ),
        fill=color,
    )


def _is_finite_point(point: Point) -> bool:
    return math.isfinite(point[0]) and math.isfinite(point[1])


def _is_valid_color(color: Color) -> bool:
    return len(color) == 3 and all(
        isinstance(channel, int) and 0 <= channel <= 255 for channel in color
    )
