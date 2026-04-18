from __future__ import annotations
import random


class Rng:
    def __init__(self, seed: int = 0) -> None:
        self.r = random.Random(seed)

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        return self.r.gauss(mu, sigma)

    def uniform(self, a: float, b: float) -> float:
        return self.r.uniform(a, b)

    def random(self) -> float:
        return self.r.random()
