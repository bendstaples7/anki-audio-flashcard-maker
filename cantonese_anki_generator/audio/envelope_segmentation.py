"""
Envelope-based audio segmentation.

Segments audio by computing an RMS energy envelope, identifying
contiguous low-energy regions (valleys), and selecting the N-1 deepest
interior valleys as split points to produce exactly N segments.

The threshold is derived from the peak RMS (1 % of max), so it adapts
to overall recording volume without being fooled by mostly-silent
recordings where the median RMS is near zero.
"""

import logging
from typing import List, Tuple

import numpy as np

from ..models import AudioSegment

logger = logging.getLogger(__name__)


class EnvelopeSegmenter:
    """
    Segments audio into N parts by finding the deepest interior valleys
    in the RMS energy envelope.

    A "valley" is a contiguous run of frames whose energy is below a
    threshold derived from the peak RMS.  Valleys that touch the very
    start or end of the audio (leading/trailing silence) are excluded
    so they cannot steal split-point slots from real between-term gaps.
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        rms_window_ms: float = 20.0,
        rms_hop_ms: float = 10.0,
        threshold_ratio: float = 0.01,
        min_valley_ms: float = 50.0,
    ):
        self.sample_rate = sample_rate
        self.rms_window_ms = rms_window_ms
        self.rms_hop_ms = rms_hop_ms
        self.threshold_ratio = threshold_ratio
        self.min_valley_ms = min_valley_ms

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

        # 2. Find interior valleys (contiguous low-energy regions,
        #    excluding leading/trailing silence)
        valleys = self._find_valleys(rms_env)

        logger.info(
            "Envelope segmentation: %d interior valleys found, need %d "
            "split points for %d segments",
            len(valleys), expected_count - 1, expected_count,
        )

        # 3. Pick the N-1 deepest valleys
        needed = expected_count - 1
        if len(valleys) >= needed:
            ranked = sorted(valleys, key=lambda v: v[2])
            chosen = sorted(ranked[:needed], key=lambda v: v[0])
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
        boundaries = [0.0, *split_times, total_duration]
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
        # Short buffer: if audio is shorter than one window, return a
        # single-frame RMS so downstream logic always has ≥1 frame.
        if len(frames) == 0 and n > 0:
            frames.append(float(np.sqrt(np.mean(audio_data ** 2))))
        return np.array(frames, dtype=np.float64), hop

    def _find_valleys(
        self,
        rms: np.ndarray,
    ) -> List[Tuple[int, int, float]]:
        """
        Identify contiguous low-energy regions in the RMS envelope.

        Returns a list of (start_frame, end_frame, min_energy) tuples.

        - Threshold is 1 % of the peak RMS, so it adapts to overall
          loudness without being fooled by mostly-silent recordings.
        - Valleys narrower than *min_valley_ms* are discarded (noise).
        - Valleys that touch frame 0 or the last frame are discarded
          (leading / trailing silence — not between-term gaps).
        """
        if len(rms) == 0:
            return []
        peak_rms = float(np.max(rms))
        if peak_rms == 0:
            return []
        threshold = peak_rms * self.threshold_ratio

        min_width = max(1, int(self.min_valley_ms / self.rms_hop_ms))
        total_frames = len(rms)

        raw_valleys: List[Tuple[int, int, float]] = []
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
                    raw_valleys.append((start, i, min_val))
                    in_valley = False
        if in_valley:
            raw_valleys.append((start, total_frames, min_val))

        # Keep only interior valleys with sufficient width
        valleys = [
            (s, e, m)
            for s, e, m in raw_valleys
            if (e - s) >= min_width and s > 0 and e < total_frames
        ]

        return valleys

    @staticmethod
    def _fill_missing_splits(
        current: List[int], needed: int, total_frames: int
    ) -> List[int]:
        """Bisect the longest span until we have enough splits.

        Falls back to evenly spaced splits when total_frames is too
        small for bisection to produce unique midpoints.  The returned
        list is always strictly increasing and clamped to
        [0, total_frames - 1].
        """
        if needed <= 0:
            return list(current)

        def _even_spaced(n: int, span: int) -> List[int]:
            """Produce *n* strictly increasing indices in [0, span)."""
            if span <= 0:
                return [0] * n
            raw = [
                max(0, min(span - 1,
                           int(round((i + 1) * span / (n + 1)))))
                for i in range(n)
            ]
            # Enforce strict monotonicity: bump duplicates forward.
            deduped: List[int] = []
            prev = -1
            for v in raw:
                v = max(v, prev + 1)
                if v >= span:
                    v = span - 1          # clamp — can't go further
                deduped.append(v)
                prev = v
            return deduped

        # When there aren't enough distinct frame positions for unique
        # bisection, fall back to evenly spaced indices.
        if total_frames < 2 or needed >= total_frames:
            return _even_spaced(needed, total_frames)

        splits = list(current)
        seen: set = set(splits)
        while len(splits) < needed:
            bounds = [0, *sorted(splits), total_frames]
            longest_idx = max(
                range(len(bounds) - 1), key=lambda i: bounds[i + 1] - bounds[i]
            )
            mid = (bounds[longest_idx] + bounds[longest_idx + 1]) // 2
            if mid in seen:
                # Bisection can't produce new points — fall back
                return _even_spaced(needed, total_frames)
            seen.add(mid)
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
