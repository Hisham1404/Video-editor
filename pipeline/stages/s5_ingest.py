"""Stage 5 -- user asset ingestion and embedding. Local, free.

Embedding is a ONE-TIME cost per asset and is cached, so a slower, better model
is affordable here in a way it is not per-job. CPU throughput measured on an
i7-1360P: ViT-B/32 69.5ms/img, SigLIP base/16 188ms, ViT-L/14 930ms.

Worth evaluating: Qwen3-VL-Embedding-2B/8B (Apache 2.0, 2026-04) are jointly
multimodal, so a slot's text description and a candidate clip embed into the
same space -- exactly the operation stage 6 needs. CLIP is a 2021 model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Asset:
    path: Path
    kind: str                                # "clip" | "still"
    embedding: list[float] | None = None
    shot_size: str | None = None
    duration_seconds: float | None = None    # source property, not cut timing


def ingest(paths: list[Path]) -> list[Asset]:
    """Embed and index the user's clips and stills."""
    raise NotImplementedError("stage 5")
