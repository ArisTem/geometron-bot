"""Application-facing orchestration of mathematical image generation."""

import secrets
from dataclasses import dataclass
from io import BytesIO

from geometron_bot.generation import fractal_tree, lissajous, spirograph
from geometron_bot.generation.palette import (
    Palette,
    select_random_gradient_palette,
    select_random_palette,
)
from geometron_bot.generation.random_source import RandomSource
from geometron_bot.generation.renderer import PillowRenderer

_SEED_BITS = 64


def _resolve_seed(seed: int | None) -> int:
    """Validate an explicit seed or create a new unsigned 64-bit seed."""
    if seed is not None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("Seed must be an integer")
        if not 0 <= seed < 2**_SEED_BITS:
            raise ValueError("Seed must be an unsigned 64-bit integer")
        return seed
    return secrets.randbits(_SEED_BITS)


@dataclass(frozen=True, slots=True)
class LissajousGenerationResult:
    """A rendered image together with the inputs needed to identify it."""

    image: BytesIO
    seed: int
    parameters: lissajous.LissajousParameters


class LissajousGenerationService:
    """Coordinate parameter selection, geometry generation, and rendering."""

    def __init__(
        self,
        renderer: PillowRenderer | None = None,
        palette: Palette | None = None,
    ) -> None:
        self._renderer = renderer if renderer is not None else PillowRenderer()
        self._palette_override = palette

    def generate(self, seed: int | None = None) -> LissajousGenerationResult:
        """Generate a Lissajous PNG, creating a seed when none is supplied."""
        generation_seed = _resolve_seed(seed)
        random_source = RandomSource(generation_seed)
        parameters = lissajous.select_random_parameters(
            random_source.stream("lissajous.parameters")
        )
        palette = self._palette_override
        if palette is None:
            palette = select_random_palette(random_source.stream("lissajous.palette"))
        scene = lissajous.generate_lissajous(parameters)
        image = self._renderer.render(scene, palette)

        return LissajousGenerationResult(
            image=image,
            seed=generation_seed,
            parameters=parameters,
        )


@dataclass(frozen=True, slots=True)
class SpirographGenerationResult:
    """A rendered spirograph and the inputs needed to reproduce it."""

    image: BytesIO
    seed: int
    parameters: spirograph.SpirographParameters


class SpirographGenerationService:
    """Coordinate spirograph parameters, geometry, palette, and rendering."""

    def __init__(
        self,
        renderer: PillowRenderer | None = None,
        palette: Palette | None = None,
    ) -> None:
        self._renderer = renderer if renderer is not None else PillowRenderer()
        self._palette_override = palette

    def generate(self, seed: int | None = None) -> SpirographGenerationResult:
        """Generate a PNG with a new or explicitly supplied unsigned seed."""
        generation_seed = _resolve_seed(seed)
        random_source = RandomSource(generation_seed)
        parameters = spirograph.select_random_parameters(
            random_source.stream("spirograph.parameters")
        )
        palette = self._palette_override
        if palette is None:
            palette = select_random_palette(random_source.stream("spirograph.palette"))
        scene = spirograph.generate_spirograph(parameters)
        image = self._renderer.render(scene, palette)

        return SpirographGenerationResult(
            image=image,
            seed=generation_seed,
            parameters=parameters,
        )


@dataclass(frozen=True, slots=True)
class FractalTreeGenerationResult:
    """A rendered tree and the inputs needed to reproduce it."""

    image: BytesIO
    seed: int
    parameters: fractal_tree.FractalTreeParameters


class FractalTreeGenerationService:
    """Select tree settings, build branches, and render a PNG."""

    def __init__(
        self,
        renderer: PillowRenderer | None = None,
        palette: Palette | None = None,
    ) -> None:
        self._renderer = renderer if renderer is not None else PillowRenderer()
        self._palette_override = palette

    def generate(self, seed: int | None = None) -> FractalTreeGenerationResult:
        """Generate a new tree or reproduce one by its unsigned seed."""
        generation_seed = _resolve_seed(seed)
        random_source = RandomSource(generation_seed)
        parameters = fractal_tree.select_random_parameters(
            random_source.stream("fractal_tree.parameters")
        )
        scene = fractal_tree.generate_fractal_tree(
            parameters, random_source.stream("fractal_tree.branches")
        )
        palette = self._palette_override
        if palette is None:
            palette = select_random_gradient_palette(
                random_source.stream("fractal_tree.palette")
            )
        image = self._renderer.render(scene, palette)
        return FractalTreeGenerationResult(
            image=image,
            seed=generation_seed,
            parameters=parameters,
        )
