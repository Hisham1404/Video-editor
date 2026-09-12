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
does not:

    they agree (58% of items)  -> 88.3% correct
    they disagree (42%)        -> classifier 63.9%, VLM 25.6%

On disagreement the VLM is worse, so the only sensible rule is "believe the
classifier", which lands back at 78.0%. No implementable combination beats the
classifier alone; the 88.8% ceiling assumes a referee that knows the answer.

What the second opinion buys is a **confidence signal**, and a strong one: a
24-point spread between agreement and disagreement, for free. That matters
because `s6_match.CONFIDENCE_FLOOR` is currently a guessed constant, and this
gives stage 6 something measured to weight against. A wrong match the system
flags is recoverable; a wrong match it is confident about ships a broken reel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: Measured agreement rates, film-grab set, n=859. Used to turn "the two taggers
#: agreed" into a number stage 6 can multiply into a match score. These are
#: observed accuracies, not tuning knobs -- re-measure before changing them.
AGREE_CONFIDENCE = 0.88
DISAGREE_CONFIDENCE = 0.64

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
