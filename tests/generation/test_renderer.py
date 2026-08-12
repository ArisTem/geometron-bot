from io import BytesIO

import pytest
from PIL import Image, ImageChops

from geometron_bot.generation.geometry import Polyline, Scene
from geometron_bot.generation.palette import GradientPalette
from geometron_bot.generation.renderer import PillowRenderer, RenderConfig


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
    scene = Scene(polylines=(Polyline(points=((-2.0, -1.0), (0.0, 1.0), (2.0, -1.0))),))

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
        renderer.render(Scene(polylines=()), palette)
