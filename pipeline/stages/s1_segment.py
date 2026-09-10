"""Stage 1 -- shot segmentation of the reference. Local, free.

MEASURED CAVEAT (2026-09-10, evals): PySceneDetect's ContentDetector and
AdaptiveDetector found ZERO cuts on a clip joined by 0.5s crossfades, at every
threshold tried including a very sensitive 6. It does not error -- it silently
returns a short shot list, which corrupts every downstream stage.

v1 renders hard cuts only (CLAUDE.md), but the reference reel will still contain
dissolves. Detecting them and reproducing them are different problems; we must
detect even in v1, or the template is simply wrong. Hence the dissolve guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Shot:
    index: int
    start_frame: int
    end_frame: int
    confidence: float = 1.0
    suspected_transition: bool = False


def segment(video: Path, threshold: float = 27.0) -> list[Shot]:
    """Detect hard cuts with PySceneDetect ContentDetector."""
    raise NotImplementedError("stage 1")


def flag_suspected_transitions(video: Path, shots: list[Shot]) -> list[Shot]:
    """Mark shots that look like an undetected dissolve.

    A dissolve reads as one long shot with steady frame-to-frame drift. Flag
    rather than guess, and surface flagged shots to the user: an admitted
    uncertainty is worth more than a confidently wrong shot list.
    """
    raise NotImplementedError("stage 1 - dissolve guard")
