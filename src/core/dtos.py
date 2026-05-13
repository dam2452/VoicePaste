from dataclasses import dataclass

import numpy as np


@dataclass
class AudioData:
    data: np.ndarray
    sample_rate: int
    source_name: str


@dataclass
class CacheEntry:
    text: str
    timestamp: float
    source_type: str
    title: str
