"""
Envelope-based audio segmentation.

Segments audio by computing an RMS energy envelope, identifying
contiguous low-energy regions (valleys), and selecting the N-1 deepest
valleys as split points to produce exactly N segments.
"""

import logging
from typing import List, Tuple

import numpy as np

from ..models import AudioSegment

logger = logging.getLogger(__name__)


class EnvelopeSegmenter:
    """
    Segments audio into N parts by finding the deepest valleys in the
    RMS energy envelope.

    A "valley" is a contiguous run of frames whose energy is below a
    threshold derived from the audio itself.  Each valley yields one
    candidate split point (its centre).  We rank valleys by their
    minimum energy and pick the N-1 deepest ones.
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        rms_window_ms: float = 20.0,
        rms_hop_ms: float = 10.0,
    ):
        self.sample_rate = sample_rate
        self.rms_window_ms = rms_window_ms
        self.rms_hop_ms = rms_hop_ms

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def segment_audio(
        self,
        audio_data: np.ndarray,
        expected_count: int,
    ) -> List[AudioSegment]:
        """
        Segment *audio_data* into exactly *expected_count* segments.

        Args:
            audio_data: 1-D numpy array of audio samples (float).
            expected_count: Number of segments to produce.

        Returns:
            List of AudioSegment, length == expected_count.
        """
        if expected_count <= 0:
            return []

        total_samples = len(audio_data)
        total_duration = total_samples / self.sample_rate

        if expected_count == 1:
            return [self._make_segment(audio_data, 0.0, total_duration, 0)]

        # 1. RMS energy envelope
        rms_env, hop_samples = self._rms_envelope(audio_data)

        # 2. Find valleys (contiguous low-energy regions)
        valleys = self._find_valleys(rms_env)

        logger.info(
            "Envelope segmentation: %d valleys found, need %d split points "
            "for %d segments",
            len(valleys), expected_count - 1, expected_count,
        )

        # 3. Pick the N-1 deepest valleys
        needed = expected_count - 1
        if len(valleys) >= needed:
            # Sort by minimum energy in the valley (ascending = deepest first)
            ranked = sorted(valleys, key=lambda v: v[2])
            chosen = sorted(ranked[:needed], key=lambda v: v[0])  # re-sort by time
        else:
            chosen = sorted(valleys, key=lambda v: v[0])

        # Each valley's split point is its centre frame
        split_frames = [int((v[0] + v[1]) / 2) for v in chosen]

        # If we still don't have enough, bisect the longest spans
        if len(split_frames) < needed:
            split_frames = self._fill_missing_splits(
                split_frames, needed, len(rms_env)
            )

        # Convert frame indices -> seconds
        split_times = [f * hop_samples / self.sample_rate for f in split_frames]

        logger.info("Split times (s): %s", [round(t, 3) for t in split_times])

        # 4. Build segments
        boundaries = [0.0] + split_times + [total_duration]
        segments: List[AudioSegment] = []
        for i in range(len(boundaries) - 1):
            segments.append(
                self._make_segment(audio_data, boundaries[i], boundaries[i + 1], i)
            )

        logger.info(
            "Envelope segmentation complete: %d segments, durations %s",
            len(segments),
            [round(s.end_time - s.start_time, 2) for s in segments],
        )
        return segments

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rms_envelope(self, audio_data: np.ndarray):
        """Return (rms_array, hop_samples)."""
        win = max(1, int(self.rms_window_ms / 1000.0 * self.sample_rate))
        hop = max(1, int(self.rms_hop_ms / 1000.0 * self.sample_rate))
        n = len(audio_data)
        frames: List[float] = []
        for start in range(0, n - win + 1, hop):
            w = audio_data[start : start + win]
            frames.append(float(np.sqrt(np.mean(w ** 2))))
        return np.array(frames, dtype=np.float64), hop

    @staticmethod
    def _find_valleys(
        rms: np.ndarray,
    ) -> List[Tuple[int, int, float]]:
        """
        Identify contiguous low-energy regions in the RMS envelope.

        Returns a list of (start_frame, end_frame, min_energy) tuples.
        The threshold is set at 15 % of the median RMS so that it adapts
        to the overall loudness of the recording.
        """
        median_rms = float(np.median(rms))
        threshold = median_rms * 0.15

        valleys: List[Tuple[int, int, float]] = []
        in_valley = False
        start = 0
        min_val = float("inf")

        for i, val in enumerate(rms):
            if val <= threshold:
                if not in_valley:
                    in_valley = True
                    start = i
                    min_val = val
                else:
                    min_val = min(min_val, val)
            else:
                if in_valley:
                    valleys.append((start, i, min_val))
                    in_valley = False
        # Close a trailing valley
        if in_valley:
            valleys.append((start, len(rms), min_val))

        return valleys

    @staticmethod
    def _fill_missing_splits(
        current: List[int], needed: int, total_frames: int
    ) -> List[int]:
        """Bisect the longest span until we have enough splits."""
        splits = list(current)
        while len(splits) < needed:
            bounds = [0] + splits + [total_frames]
            longest_idx = max(
                range(len(bounds) - 1), key=lambda i: bounds[i + 1] - bounds[i]
            )
            mid = (bounds[longest_idx] + bounds[longest_idx + 1]) // 2
            splits.append(mid)
            splits.sort()
        return splits

    def _make_segment(
        self, audio_data: np.ndarray, start_time: float, end_time: float, index: int
    ) -> AudioSegment:
        s = max(0, int(start_time * self.sample_rate))
        e = min(len(audio_data), int(end_time * self.sample_rate))
        return AudioSegment(
            start_time=start_time,
            end_time=end_time,
            audio_data=audio_data[s:e],
            confidence=0.9,
            segment_id=f"envelope_{index + 1:03d}",
        )
