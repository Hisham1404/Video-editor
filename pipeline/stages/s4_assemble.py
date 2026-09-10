"""Stage 4 -- template assembly: shots + rhythm -> ordered slots.

This is the boundary where absolute seconds are converted into rhythm and then
never used again. Everything downstream reads beats, subdivisions and phrase
positions. The seconds computed inside this function are scaffolding and must
not reach the Template -- template.assert_no_absolute_time enforces that.
"""

from __future__ import annotations

from pipeline.stages.s1_segment import Shot
from pipeline.stages.s2_rhythm import RhythmMap
from pipeline.stages.s3_describe import ShotDescription
from pipeline.template import Template


def assemble(shots: list[Shot], rhythm: RhythmMap,
             descriptions: list[ShotDescription], fps: float) -> Template:
    """Snap each shot boundary to the reference beat grid, store as rhythm."""
    raise NotImplementedError("stage 4")
