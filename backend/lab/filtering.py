from dataclasses import dataclass


@dataclass
class EMA:
    alpha: float
    last_seq: int = -1
    value: float | None = None

    def apply(self, seq: int, raw: float) -> float:
        if seq != self.last_seq + 1:
            raise ValueError("EMA requires contiguous ordered samples")
        self.value = raw if self.value is None else self.alpha * raw + (1 - self.alpha) * self.value
        self.last_seq = seq
        return self.value
