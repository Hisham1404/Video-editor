"""Stage 8 -- render with ffmpeg.

The ONLY place seconds exist in the output path, and they come from
Template.resolve(bpm) against the USER's track -- never read from the template
itself. That indirection is the whole reason the timeline is tempo-portable.

v1 is hard cuts only: no transitions, speed ramps, colour grading or camera
motion synthesis (CLAUDE.md). Output will look simpler than the reference;
SPEC says that is expected and acceptable.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.stages.s2_rhythm import RhythmMap
from pipeline.template import Template


def render(template: Template, rhythm: RhythmMap, audio: Path,
           out: Path) -> Path:
    """Lay the template onto the user's track and cut."""
    raise NotImplementedError("stage 8")
