"""Deterministic joint circular-block permutations with a time embargo."""

from __future__ import annotations

import random


def _distance(left: int, right: int, length: int) -> int:
    return min((left - right) % length, (right - left) % length)


def joint_block_permutation_indices(
    length: int,
    *,
    block_size: int,
    embargo: int,
    rng: random.Random,
    maximum_attempts: int = 20_000,
) -> tuple[int, ...]:
    """Return one bijection applied to every basket column, or abstain."""
    if length < 1 or block_size < 1 or embargo < 0 or maximum_attempts < 1:
        raise ValueError("invalid permutation dimensions")
    if embargo >= length // 2 or length <= block_size:
        return ()

    for _ in range(maximum_attempts):
        offset = rng.randrange(length)
        circular = tuple((offset + index) % length for index in range(length))
        blocks = [
            list(circular[start : start + block_size]) for start in range(0, length, block_size)
        ]
        rng.shuffle(blocks)
        candidate = tuple(source for block in blocks for source in block)
        displaced = all(
            _distance(target, source, length) > embargo for target, source in enumerate(candidate)
        )
        if displaced:
            return candidate
    return ()
