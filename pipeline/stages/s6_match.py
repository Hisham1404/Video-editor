"""Stage 6 -- slot matching with confidence scoring.

SPEC: "Matching quality decides whether this feels magical or broken. It is the
least glamorous component and will consume the most time. Budget accordingly."

The confidence score is load-bearing: stage 7 turns low-confidence slots into
generation prompts, so a miscalibrated threshold either floods the user with
needless prompts or silently ships bad matches. Calibrate against evals/golden,
do not guess.

WHY THE FLOOR IS STILL 0.55 AND WHAT WOULD MOVE IT
--------------------------------------------------
0.55 is inherited guesswork. Nothing has been measured that justifies it, and
saying so in a comment is cheaper than pretending otherwise.

What IS measured is how much to trust an asset's shot size, which is one of the
two inputs to a match score. Stage 5 tags every asset twice -- a DINOv2
classifier and stage 3's vision model -- and records whether they agreed. On 859
human-labelled frames:

    agreed (70.4% of assets)   91.6% correct
    disagreed (29.6%)          45.7% correct

That 46-point spread is free: the classifier costs nothing to run and the second
opinion falls out of a stage 3 call the pipeline already pays for. It does not
make matching more accurate; it makes the score honest about which matches to
doubt.

The disagreement number is the one to design around. At 45.7% the pipeline is
worse than guessing between the two labels on offer, and the second model is no
better at 44.9% -- so on those assets nothing in the system knows the framing.
An asset like that should not win a slot on a hair's-breadth semantic margin
over one both taggers read the same way, and stage 7 should prefer emitting a
generation prompt over filling a slot from it.
"""

from __future__ import annotations

from pipeline.stages.s5_ingest import Asset, DISAGREE_CONFIDENCE
from pipeline.template import Slot, Template

#: Below this, stage 7 emits a generation prompt instead of filling the slot.
#: Still a guess -- see the module docstring. The one thing known about it is
#: the direction of each error: too high floods the user with prompts for shots
#: they already have, too low ships mismatched footage silently. The second is
#: worse, so err high until evals/golden says otherwise.
CONFIDENCE_FLOOR = 0.55

#: How much of a match score comes from semantic similarity versus the shot size
#: agreeing. Shot size is the structural constraint -- a close-up in a wide slot
#: is wrong however well the subject matches -- but it is only one field, so it
#: does not dominate.
SEMANTIC_WEIGHT = 0.7
SHOT_SIZE_WEIGHT = 0.3


def score(slot: Slot, asset: Asset, similarity: float) -> float:
    """Combine semantic similarity with shot-size fit, discounted by how much
    the asset's shot size can be trusted.

    The discount is the point. Two assets can both claim "close up" and be
    equally similar to the slot's description, and one of them can have had two
    models disagree about its framing. That one should lose. Without the
    discount the tie is broken arbitrarily, and arbitrary is what produces a
    reel where one shot is visibly the wrong size.
    """
    size_fit = 1.0 if (asset.shot_size and asset.shot_size == slot.shot_size) else 0.0

    # An untagged asset is not a confident one. None means "nobody looked",
    # which is a reason to doubt the size term, not to trust it.
    trust = asset.shot_size_confidence
    if trust is None:
        trust = DISAGREE_CONFIDENCE

    return (SEMANTIC_WEIGHT * similarity
            + SHOT_SIZE_WEIGHT * size_fit * trust)


def match(template: Template, assets: list[Asset],
          floor: float = CONFIDENCE_FLOOR) -> Template:
    """Fill each slot with the best asset above the confidence floor.

    Two decisions are still open and should be made deliberately rather than by
    whatever the first implementation happens to do:

    Can one asset fill several slots? A reference with 20 shots and a user with
    10 clips means either 10 gaps or reuse. Reuse reads naturally in reels -- the
    same subject recurs -- but past a point it looks cheap.

    Greedy or global assignment? Greedy takes each slot's best match in order, so
    slot 1 can take the clip slot 7 needed far more. A Hungarian assignment
    optimises the whole set and is not much harder.
    """
    raise NotImplementedError("stage 6")
