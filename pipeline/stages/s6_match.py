"""Stage 6 -- slot matching with confidence scoring.

SPEC: "Matching quality decides whether this feels magical or broken. It is the
least glamorous component and will consume the most time. Budget accordingly."

The confidence score is load-bearing: stage 7 turns low-confidence slots into
generation prompts, so a miscalibrated threshold either floods the user with
needless prompts or silently ships bad matches. Calibrate against evals/golden,
do not guess.
"""

from __future__ import annotations

from pipeline.stages.s5_ingest import Asset
from pipeline.template import Template

CONFIDENCE_FLOOR = 0.55


def match(template: Template, assets: list[Asset],
          floor: float = CONFIDENCE_FLOOR) -> Template:
    """Fill each slot with the best asset above the confidence floor."""
    raise NotImplementedError("stage 6")
