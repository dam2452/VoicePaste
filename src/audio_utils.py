import numpy as np
from scipy.signal import resample


def normalize_audio(audio: np.ndarray, sample_rate: int, target_rate: int = 16000) -> tuple[np.ndarray, int]:
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483648.0

    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    if sample_rate != target_rate:
        num_samples = int(len(audio) * target_rate / sample_rate)
        audio = resample(audio, num_samples)
        sample_rate = target_rate

    return audio.astype(np.float32), sample_rate
