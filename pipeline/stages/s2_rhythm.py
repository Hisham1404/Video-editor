"""Stage 2 -- rhythm extraction. Local, free.

MEASURED (2026-09-10) on a 120 BPM click track with exact ground truth:

    method                    beats    MAE      bias       downbeats
    librosa.beat_track        38/40    22.4ms   +22.4ms    none
    librosa onset+backtrack   39       10.2ms   -10.1ms    none
    beat_this (CPU)           40/40     8.5ms    +8.5ms    yes

librosa also estimated 117.5 BPM against a true 120 (2.1% error, which compounds
if extrapolated) and has NO downbeat tracker -- making CLAUDE.md's required
phrase position unbuildable on it. madmom, named in SPEC, requires Python <3.10
and will not install on 3.12. beat_this is the choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RhythmMap:
    """Beat grid for one audio track."""

    beat_times: list[float]      # seconds; analysis-side only, never templated
    downbeat_times: list[float]
    bpm: float
    time_signature: tuple[int, int] = (4, 4)

    def beat_index_at(self, t: float) -> int:
        """Nearest beat index to a wall-clock time in THIS track."""
        if not self.beat_times:
            raise ValueError("empty beat grid")
        return min(range(len(self.beat_times)),
                   key=lambda i: abs(self.beat_times[i] - t))


def extract(audio: Path) -> RhythmMap:
    """Beat + downbeat tracking with beat_this (CPU-capable, 18.7x realtime)."""
    raise NotImplementedError("stage 2")
