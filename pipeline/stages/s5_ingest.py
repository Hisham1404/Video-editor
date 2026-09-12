"""Stage 5 -- user asset ingestion and embedding. Local, free.

Embedding is a ONE-TIME cost per asset and is cached, so a slower, better model
is affordable here in a way it is not per-job. CPU throughput measured on an
i7-1360P: ViT-B/32 69.5ms/img, SigLIP base/16 188ms, ViT-L/14 930ms.

Worth evaluating: Qwen3-VL-Embedding-2B/8B (Apache 2.0, 2026-04) are jointly
multimodal, so a slot's text description and a candidate clip embed into the
same space -- exactly the operation stage 6 needs. CLIP is a 2021 model.

SHOT SIZE IS TAGGED HERE, BY TWO MODELS, ON PURPOSE
---------------------------------------------------
A user's clip needs a shot size so stage 6 can match it to a slot. This is the
one place in the pipeline that needs shot size and nothing else -- no
description, no camera motion -- which is exactly what a classifier can give for
free. Measured on 859 human-labelled frames (evals/shotbench, film-grab set):

    aslakey/shot_scale (DINOv2, 1.2GB)   78.0%   19.8 img/sec, CPU-capable
    Qwen3-VL-4B (8.9GB)                  64.4%
    Qwen3-VL-2B (4.3GB)                  61.8%

The classifier is both the most accurate and effectively free, so it is the
primary tagger.

The second model is NOT here to raise accuracy. That was measured too, and it
does not: on the items where the two disagree, the second model is the less
accurate one, so the only implementable rule is "believe the classifier", which
lands back at its solo accuracy. No combination beats the classifier alone; the
ceiling that does assumes a referee that already knows the answer.

What the second opinion buys is a **confidence signal**, and a strong one. The
cross-check is gemini-3.5-flash-lite, because CLAUDE.md already makes it the
stage 3 vision model -- its shot-size answer is a by-product of a call the
pipeline pays for anyway, so this costs nothing extra. Measured on the same 859
frames:

    they agree (70.4% of items)  -> 91.6% correct
    they disagree (29.6%)        -> classifier 45.7%, gemini 44.9%

Two things to notice. The agreement bucket is the most accurate of any pairing
tested -- better than a 62.5GB model as the second opinion. And the disagreement
bucket is near coin-flip for BOTH models, which is the useful part: when these
two differ, nothing in the pipeline knows the answer, and stage 6 should treat
that asset as a question rather than a fact.

That 46-point spread is nearly double what a small local VLM gives (24 points,
Qwen3-VL-2B). It matters because `s6_match.CONFIDENCE_FLOOR` is a guessed
constant, and this gives stage 6 something measured to weight against. A wrong
match the system flags is recoverable; a wrong match it is confident about ships
a broken reel.

If stage 3 moves to a different model, RE-MEASURE: `python
evals/shotbench/analyze.py` prints this table, and the constants below are one
row of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: Measured agreement rates for dinov2-shotscale x gemini-3.5-flash-lite,
#: film-grab set, n=859. Used to turn "the two taggers agreed" into a number
#: stage 6 can multiply into a match score. These are observed accuracies, not
#: tuning knobs -- re-measure before changing them, and re-measure if stage 3
#: changes model, because the second tagger IS stage 3's model.
AGREE_CONFIDENCE = 0.92
DISAGREE_CONFIDENCE = 0.46

#: Sole tagger, or no cross-check available (a still with no second opinion, or
#: the VLM erroring). Its standalone accuracy.
SOLO_CONFIDENCE = 0.78


@dataclass
class Asset:
    path: Path
    kind: str                                # "clip" | "still"
    embedding: list[float] | None = None
    shot_size: str | None = None
    duration_seconds: float | None = None    # source property, not cut timing

    # How much to trust `shot_size`. Set from whether the two taggers agreed --
    # see the module docstring. None means untagged, not "certain".
    shot_size_confidence: float | None = None

    # What each tagger actually said, kept so a disagreement can be inspected
    # rather than just distrusted. Storing only the verdict throws away the
    # evidence for it, and these disagree on 42% of frames.
    shot_size_votes: dict[str, str] = field(default_factory=dict)

    @property
    def shot_size_is_uncertain(self) -> bool:
        """True where the taggers disagreed.

        Stage 6 should prefer a confident asset over an uncertain one at equal
        semantic similarity, and stage 7 should rather emit a generation prompt
        than fill a slot from a clip whose framing nobody could agree on.
        """
        return (self.shot_size_confidence is not None
                and self.shot_size_confidence <= DISAGREE_CONFIDENCE)


def confidence_from_votes(votes: dict[str, str]) -> float | None:
    """Turn tagger votes into a confidence.

    Deliberately not an average of model confidences. A model's own softmax is
    not calibrated and says nothing about the other model; agreement between two
    independently-trained architectures is an external check, which is why it
    separates 88.3% from 63.9% cases where a softmax would not.
    """
    distinct = set(votes.values())
    if not distinct:
        return None
    if len(votes) == 1:
        return SOLO_CONFIDENCE
    return AGREE_CONFIDENCE if len(distinct) == 1 else DISAGREE_CONFIDENCE


def ingest(paths: list[Path]) -> list[Asset]:
    """Embed and index the user's clips and stills.

    Tags shot size with the classifier, cross-checks with the vision model
    already loaded for stage 3, and records both votes plus the resulting
    confidence.
    """
    raise NotImplementedError("stage 5")
