"""
Voice Activity Detection segmentation using Silero VAD.

Detects speech bursts with millisecond precision, counts them,
reconciles with expected term count, and returns boundaries.
"""

import logging
from typing import List, Tuple

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Module-level cache so the model is loaded once
_silero_model = None
_silero_get_timestamps = None


def _load_silero():
    """Load Silero VAD model and utils via torch.hub (cached)."""
    global _silero_model, _silero_get_timestamps
    if _silero_model is not None:
        return _silero_model, _silero_get_timestamps
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        trust_repo=True,
    )
    _silero_model = model
    _silero_get_timestamps = utils[0]
    return _silero_model, _silero_get_timestamps


def detect_speech_segments(
    audio_data: np.ndarray,
    sample_rate: int,
    threshold: float = 0.3,
    min_silence_duration_ms: int = 200,
    speech_pad_ms: int = 30,
) -> List[Tuple[float, float]]:
    """
    Detect speech segments using Silero VAD.

    Args:
        audio_data: 1-D float32 numpy array.
        sample_rate: Sample rate in Hz (will be resampled to 16kHz if needed).
        threshold: VAD confidence threshold.
        min_silence_duration_ms: Min silence gap to split segments.
        speech_pad_ms: Padding around each segment.

    Returns:
        List of (start_seconds, end_seconds) for each speech burst.
    """
    logger.info("🎙️  Running Silero VAD...")

    # Resample to 16kHz if needed
    target_sr = 16000
    if sample_rate != target_sr:
        import torchaudio
        wav = torch.from_numpy(audio_data).float().unsqueeze(0)
        wav = torchaudio.functional.resample(wav, sample_rate, target_sr)
        wav = wav.squeeze(0)
    else:
        wav = torch.from_numpy(audio_data).float()

    model, get_speech_timestamps = _load_silero()

    timestamps = get_speech_timestamps(
        wav, model,
        sampling_rate=target_sr,
        threshold=threshold,
        min_silence_duration_ms=min_silence_duration_ms,
        speech_pad_ms=speech_pad_ms,
    )

    segments = [(ts['start'] / target_sr, ts['end'] / target_sr) for ts in timestamps]

    logger.info(f"✓ Silero VAD found {len(segments)} speech segments")
    for i, (s, e) in enumerate(segments):
        logger.info(f"   {i+1}: {s:.2f}s – {e:.2f}s (dur: {e-s:.2f}s)")

    return segments


def segment_audio_with_vad(
    audio_data: np.ndarray,
    sample_rate: int,
    expected_count: int,
) -> List[Tuple[float, float]]:
    """
    Segment audio into expected_count terms using Silero VAD.

    Detects all speech bursts, then reconciles with expected count:
    - Too many: merge closest pairs (smallest silence gap)
    - Too few: split longest bursts at lowest energy point
    """
    segments = detect_speech_segments(audio_data, sample_rate)

    if not segments:
        logger.error("No speech detected in audio")
        return [(0.0, 0.0)] * expected_count

    logger.info(f"🔢 Reconciling {len(segments)} detected bursts with {expected_count} expected terms")

    # Too many — merge closest pairs
    if len(segments) > expected_count:
        logger.info(f"🔗 Merging {len(segments)} → {expected_count} (closing smallest gaps)...")
        while len(segments) > expected_count:
            min_gap = float('inf')
            min_idx = 0
            for i in range(len(segments) - 1):
                gap = segments[i+1][0] - segments[i][1]
                if gap < min_gap:
                    min_gap = gap
                    min_idx = i
            merged = (segments[min_idx][0], segments[min_idx + 1][1])
            logger.info(f"   Merging gap {min_gap:.2f}s: "
                        f"{segments[min_idx][0]:.2f}-{segments[min_idx][1]:.2f} + "
                        f"{segments[min_idx+1][0]:.2f}-{segments[min_idx+1][1]:.2f} → "
                        f"{merged[0]:.2f}-{merged[1]:.2f}")
            segments[min_idx] = merged
            segments.pop(min_idx + 1)

    # Too few — split longest at quietest point
    elif len(segments) < expected_count:
        logger.info(f"✂️  Splitting {len(segments)} → {expected_count} (splitting longest bursts)...")
        while len(segments) < expected_count:
            longest_idx = max(range(len(segments)),
                              key=lambda i: segments[i][1] - segments[i][0])
            s, e = segments[longest_idx]
            # Search middle third for quietest point
            third = (e - s) / 3
            ss = int((s + third) * sample_rate)
            se = int((e - third) * sample_rate)

            if se > ss + sample_rate // 10:
                win = int(0.05 * sample_rate)
                hop = int(0.02 * sample_rate)
                min_rms = float('inf')
                split_sample = (ss + se) // 2
                for idx in range(ss, se - win, hop):
                    rms = float(np.sqrt(np.mean(audio_data[idx:idx+win] ** 2)))
                    if rms < min_rms:
                        min_rms = rms
                        split_sample = idx + win // 2
                split_time = split_sample / sample_rate
            else:
                split_time = (s + e) / 2

            logger.info(f"   Splitting {s:.2f}-{e:.2f} at {split_time:.2f}s")
            segments[longest_idx] = (s, split_time)
            segments.insert(longest_idx + 1, (split_time, e))

    logger.info(f"✓ Final: {len(segments)} segments for {expected_count} terms")
    for i, (s, e) in enumerate(segments):
        logger.info(f"   Term {i+1}: {s:.2f}s – {e:.2f}s (dur: {e-s:.2f}s)")

    return segments
