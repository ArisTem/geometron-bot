import random
from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from geometron_bot.generation import fractal_tree, lissajous, spirograph
from geometron_bot.generation import service as service_module
from geometron_bot.generation.palette import (
    GradientPalette,
    select_random_gradient_palette,
    select_random_palette,
)
from geometron_bot.generation.random_source import RandomSource
from geometron_bot.generation.renderer import PillowRenderer
from geometron_bot.generation.service import (
    FractalTreeGenerationService,
    LissajousGenerationService,
    SpirographGenerationService,
)

_SERVICE_TYPES = (
    LissajousGenerationService,
    SpirographGenerationService,
    FractalTreeGenerationService,
)
_SERVICES_WITH_GEOMETRY = (
    pytest.param(LissajousGenerationService, lissajous, "lissajous", id="lissajous"),
    pytest.param(SpirographGenerationService, spirograph, "spirograph", id="spirograph"),
    pytest.param(
        FractalTreeGenerationService, fractal_tree, "fractal_tree", id="fractal_tree"
    ),
)


@pytest.mark.parametrize(("service_type", "geometry", "namespace"), _SERVICES_WITH_GEOMETRY)
def test_service_generates_reproducible_png(service_type, geometry, namespace) -> None:
    service = service_type()
    random_state = random.getstate()
    try:
        random.seed(1)
        first = service.generate(seed=12345)
        random.seed(999)
        second = service.generate(seed=12345)
    finally:
        random.setstate(random_state)

    assert first.seed == 12345
    assert first.parameters == geometry.select_random_parameters(
        RandomSource(12345).stream(f"{namespace}.parameters")
    )
    assert first.parameters == second.parameters
    assert first.image.getvalue() == second.image.getvalue()
    assert isinstance(first.image, BytesIO)
    assert first.image.tell() == 0
    with Image.open(first.image) as image:
        assert image.format == "PNG"
        assert image.size == (1024, 1024)


@pytest.mark.parametrize("service_type", _SERVICE_TYPES)
def test_service_creates_seed_when_one_is_not_supplied(
    service_type, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = Mock(spec=PillowRenderer)
    renderer.render.return_value = BytesIO(b"rendered image")

    def create_seed(bit_count: int) -> int:
        assert bit_count == 64
        return 987_654_321

    monkeypatch.setattr(service_module.secrets, "randbits", create_seed)

    assert service_type(renderer=renderer).generate().seed == 987_654_321


@pytest.mark.parametrize(
    ("service_type", "namespace"),
    [(LissajousGenerationService, "lissajous"), (SpirographGenerationService, "spirograph")],
)
def test_service_selects_palette_from_an_independent_seeded_stream(
    service_type, namespace
) -> None:
    renderer = Mock(spec=PillowRenderer)
    renderer.render.return_value = BytesIO(b"rendered image")

    service_type(renderer=renderer).generate(seed=12345)

    assert renderer.render.call_args.args[1] == select_random_palette(
        RandomSource(12345).stream(f"{namespace}.palette")
    )


@pytest.mark.parametrize("service_type", _SERVICE_TYPES)
def test_service_uses_an_explicit_palette(service_type) -> None:
    renderer = Mock(spec=PillowRenderer)
    renderer.render.return_value = BytesIO(b"rendered image")
    palette = GradientPalette(colors=((255, 0, 0), (0, 255, 0)))

    service_type(renderer=renderer, palette=palette).generate(seed=12345)

    assert renderer.render.call_args.args[1] is palette


def test_tree_service_uses_gradient_palette_and_independent_branch_stream() -> None:
    renderer = Mock(spec=PillowRenderer)
    renderer.render.return_value = BytesIO(b"rendered image")
    result = FractalTreeGenerationService(renderer=renderer).generate(seed=12345)
    scene, palette = renderer.render.call_args.args

    assert palette is select_random_gradient_palette(
        RandomSource(12345).stream("fractal_tree.palette")
    )
    assert scene == fractal_tree.generate_fractal_tree(
        result.parameters, RandomSource(12345).stream("fractal_tree.branches")
    )


@pytest.mark.parametrize("service_type", _SERVICE_TYPES)
@pytest.mark.parametrize(
    ("seed", "error_type", "message"),
    [
        (True, TypeError, "Seed must be an integer"),
        (False, TypeError, "Seed must be an integer"),
        (1.5, TypeError, "Seed must be an integer"),
        ("12345", TypeError, "Seed must be an integer"),
        (-1, ValueError, "unsigned 64-bit integer"),
        (2**64, ValueError, "unsigned 64-bit integer"),
    ],
)
def test_service_rejects_invalid_seed(service_type, seed, error_type, message) -> None:
    with pytest.raises(error_type, match=message):
        service_type().generate(seed)
