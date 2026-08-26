from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from geometron_bot.generation import service as service_module
from geometron_bot.generation.lissajous import select_random_parameters
from geometron_bot.generation.palette import GradientPalette, select_random_palette
from geometron_bot.generation.random_source import RandomSource
from geometron_bot.generation.renderer import PillowRenderer, RenderConfig
from geometron_bot.generation.service import LissajousGenerationService


def test_service_generates_lissajous_image_without_telegram() -> None:
    service = LissajousGenerationService(
        renderer=PillowRenderer(
            RenderConfig(
                image_size=128,
                margin=16,
                line_width=2,
                supersampling=2,
            )
        )
    )

    result = service.generate(seed=12345)

    assert result.seed == 12345
    assert result.parameters == select_random_parameters(
        RandomSource(12345).stream("lissajous.parameters")
    )
    assert isinstance(result.image, BytesIO)
    assert result.image.tell() == 0
    with Image.open(result.image) as image:
        assert image.format == "PNG"
        assert image.size == (128, 128)


def test_service_creates_seed_when_one_is_not_supplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_seed = 987_654_321

    def create_seed(bit_count: int) -> int:
        assert bit_count == 64
        return generated_seed

    monkeypatch.setattr(service_module.secrets, "randbits", create_seed)
    service = LissajousGenerationService(
        renderer=PillowRenderer(
            RenderConfig(image_size=64, margin=8, supersampling=1)
        )
    )

    result = service.generate()

    assert result.seed == generated_seed


def test_service_selects_palette_from_an_independent_seeded_stream() -> None:
    seed = 12345
    renderer = Mock(spec=PillowRenderer)
    renderer.render.return_value = BytesIO(b"rendered image")
    service = LissajousGenerationService(renderer=renderer)

    service.generate(seed)

    selected_palette = renderer.render.call_args.args[1]
    expected_palette = select_random_palette(
        RandomSource(seed).stream("lissajous.palette")
    )
    assert selected_palette == expected_palette


def test_service_uses_an_explicit_palette_instead_of_random_selection() -> None:
    renderer = Mock(spec=PillowRenderer)
    renderer.render.return_value = BytesIO(b"rendered image")
    palette = GradientPalette(colors=((255, 0, 0), (0, 255, 0)))
    service = LissajousGenerationService(renderer=renderer, palette=palette)

    service.generate(seed=12345)

    assert renderer.render.call_args.args[1] is palette


@pytest.mark.parametrize("seed", [True, False, 1.5, "12345"])
def test_service_rejects_non_integer_seed(seed: object) -> None:
    service = LissajousGenerationService()

    with pytest.raises(TypeError, match="Seed must be an integer"):
        service.generate(seed)


@pytest.mark.parametrize("seed", [-1, 2**64])
def test_service_rejects_seed_outside_unsigned_64_bit_range(seed: int) -> None:
    service = LissajousGenerationService()

    with pytest.raises(ValueError, match="unsigned 64-bit integer"):
        service.generate(seed)
