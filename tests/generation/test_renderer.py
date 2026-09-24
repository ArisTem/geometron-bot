from io import BytesIO

import pytest
from PIL import Image, ImageChops

from geometron_bot.generation.geometry import Polyline
from geometron_bot.generation.palette import GradientPalette
from geometron_bot.generation.renderer import PillowRenderer, RenderConfig
from geometron_bot.generation.scene import Scene, Stroke, StrokeStyle


def test_renderer_creates_square_png_with_visible_geometry() -> None:
    background = (1, 2, 3)
    renderer = PillowRenderer(
        RenderConfig(
            image_size=128,
            margin=16,
            background_color=background,
            line_width=2,
            supersampling=2,
        )
    )
    palette = GradientPalette(colors=((255, 0, 0), (0, 255, 255)))
    scene = Scene(
        strokes=(Stroke(Polyline(points=((-2.0, -1.0), (0.0, 1.0), (2.0, -1.0)))),)
    )

    output = renderer.render(scene, palette)

    assert isinstance(output, BytesIO)
    assert output.tell() == 0
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (128, 128)
        assert image.mode == "RGB"
        background_image = Image.new("RGB", image.size, background)
        assert ImageChops.difference(image, background_image).getbbox() is not None


def test_renderer_rejects_a_scene_without_points() -> None:
    renderer = PillowRenderer(RenderConfig(image_size=64, margin=8))
    palette = GradientPalette(colors=((0, 0, 0), (255, 255, 255)))

    with pytest.raises(ValueError, match="at least one point"):
        renderer.render(Scene(strokes=()), palette)


def test_polyline_width_scales_each_line() -> None:
    renderer = PillowRenderer(
        RenderConfig(image_size=101, margin=10, line_width=4, supersampling=1)
    )
    palette = GradientPalette(colors=((255, 0, 0), (255, 0, 0)))
    scene = Scene(
        strokes=(
            Stroke(Polyline(((-1.0, 1.0), (1.0, 1.0))), StrokeStyle(width_scale=0.25)),
            Stroke(Polyline(((-1.0, 0.0), (1.0, 0.0)))),
            Stroke(Polyline(((-1.0, -1.0), (1.0, -1.0))), StrokeStyle(width_scale=2.0)),
        )
    )

    with Image.open(renderer.render(scene, palette)) as image:
        colored_rows = [
            y for y in range(image.height) if image.getpixel((50, y)) == (255, 0, 0)
        ]

    assert [sum(abs(y - center) < 15 for y in colored_rows) for center in (10, 50, 90)] == [
        1,
        4,
        8,
    ]


def test_palette_position_colors_entire_polyline_and_preserves_gradient() -> None:
    renderer = PillowRenderer(
        RenderConfig(image_size=101, margin=10, line_width=1, supersampling=1)
    )
    palette = GradientPalette(colors=((255, 0, 0), (0, 0, 255)))
    scene = Scene(
        strokes=(
            Stroke(
                Polyline(((-1.0, 1.0), (0.0, 1.0), (1.0, 1.0))),
                StrokeStyle(palette_position=0.0),
            ),
            Stroke(
                Polyline(((-1.0, 0.0), (0.0, 0.0), (1.0, 0.0))),
                StrokeStyle(palette_position=1.0),
            ),
            Stroke(Polyline(((-1.0, -1.0), (0.0, -1.0), (1.0, -1.0)))),
        )
    )

    with Image.open(renderer.render(scene, palette)) as image:
        assert [image.getpixel((x, y)) for x, y in ((30, 10), (70, 10))] == [
            (255, 0, 0),
            (255, 0, 0),
        ]
        assert [image.getpixel((x, y)) for x, y in ((30, 50), (70, 50))] == [
            (0, 0, 255),
            (0, 0, 255),
        ]
        assert [image.getpixel((x, y)) for x, y in ((30, 90), (70, 90))] == [
            (255, 0, 0),
            (0, 0, 255),
        ]


def test_single_point_uses_fixed_palette_position() -> None:
    renderer = PillowRenderer(
        RenderConfig(image_size=51, margin=5, line_width=1, supersampling=1)
    )
    palette = GradientPalette(colors=((255, 0, 0), (0, 0, 255)))
    scene = Scene(
        strokes=(
            Stroke(Polyline(((0.0, 0.0),)), StrokeStyle(palette_position=1.0)),
        )
    )

    with Image.open(renderer.render(scene, palette)) as image:
        assert image.getpixel((25, 25)) == (0, 0, 255)


def test_single_point_width_is_rounded_and_clamped() -> None:
    palette = GradientPalette(colors=((255, 0, 0), (255, 0, 0)))

    def point_pixels(line_width: int, width_scale: float) -> bytes:
        renderer = PillowRenderer(
            RenderConfig(image_size=51, margin=5, line_width=line_width, supersampling=1)
        )
        scene = Scene(
            strokes=(Stroke(Polyline(((0.0, 0.0),)), StrokeStyle(width_scale)),)
        )
        with Image.open(renderer.render(scene, palette)) as image:
            return image.tobytes()

    assert point_pixels(4, 0.01) == point_pixels(1, 1.0)
    assert point_pixels(4, 1.4) == point_pixels(6, 1.0)
