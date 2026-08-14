"""Application-facing orchestration of Lissajous image generation."""

import secrets
from dataclasses import dataclass
from io import BytesIO

from geometron_bot.generation.lissajous import (
    LissajousParameters,
    generate_lissajous,
    select_random_parameters,
)
from geometron_bot.generation.palette import DEFAULT_PALETTE, Palette
from geometron_bot.generation.random_source import RandomSource
from geometron_bot.generation.renderer import PillowRenderer

_SEED_BITS = 64


@dataclass(frozen=True, slots=True)
class LissajousGenerationResult:
    """A rendered image together with the inputs needed to identify it."""

    image: BytesIO
    seed: int
    parameters: LissajousParameters


class LissajousGenerationService:
    """Coordinate parameter selection, geometry generation, and rendering."""

    def __init__(
        self,
        renderer: PillowRenderer | None = None,
        palette: Palette | None = None,
    ) -> None:
        self._renderer = renderer if renderer is not None else PillowRenderer()
        self._palette = palette if palette is not None else DEFAULT_PALETTE

    def generate(self, seed: int | None = None) -> LissajousGenerationResult:
        """Generate a Lissajous PNG, creating a seed when none is supplied."""
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise TypeError("Seed must be an integer")
            if not 0 <= seed < 2**_SEED_BITS:
                raise ValueError("Seed must be an unsigned 64-bit integer")

        generation_seed = seed if seed is not None else secrets.randbits(_SEED_BITS)
        random_source = RandomSource(generation_seed)
        parameters = select_random_parameters(
            random_source.stream("lissajous.parameters")
        )
        scene = generate_lissajous(parameters)
        image = self._renderer.render(scene, self._palette)

        return LissajousGenerationResult(
            image=image,
            seed=generation_seed,
            parameters=parameters,
        )
