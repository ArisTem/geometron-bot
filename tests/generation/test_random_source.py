import random

import pytest

from geometron_bot.generation.random_source import RandomSource


def test_same_seed_and_namespace_produce_same_sequence() -> None:
    first = RandomSource(12345).stream("parameters")
    second = RandomSource(12345).stream("parameters")

    assert [first.random() for _ in range(5)] == [second.random() for _ in range(5)]


def test_namespaces_produce_independent_sequences() -> None:
    source = RandomSource(12345)

    parameter_values = [source.stream("parameters").random()]
    palette_values = [source.stream("palette").random()]

    assert parameter_values != palette_values


def test_stream_does_not_depend_on_global_random_state() -> None:
    random.seed(1)
    first_value = RandomSource(12345).stream("geometry").random()
    random.seed(999)
    second_value = RandomSource(12345).stream("geometry").random()

    assert first_value == second_value


def test_empty_namespace_is_rejected() -> None:
    with pytest.raises(ValueError, match="namespace must not be empty"):
        RandomSource(12345).stream("")
