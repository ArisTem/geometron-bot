"""Deterministic, independent random streams for image generation."""

import hashlib
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RandomSource:
    """Derive reproducible random streams from one generation seed."""

    seed: int

    def stream(self, namespace: str) -> random.Random:
        """Return a fresh deterministic stream for the given namespace."""
        if not namespace:
            raise ValueError("Random stream namespace must not be empty")

        digest = hashlib.blake2b(digest_size=16, person=b"geometron-rng")
        digest.update(str(self.seed).encode("ascii"))
        digest.update(b"\0")
        digest.update(namespace.encode("utf-8"))
        derived_seed = int.from_bytes(digest.digest())
        return random.Random(derived_seed)
