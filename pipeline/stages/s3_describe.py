"""Stage 3 -- per-shot semantic and framing description. THE METERED STAGE.

Every call goes through CostLog (CLAUDE.md: "every metered call gets logged with
token count and cost"). The prompt lives in prompts/shot_description/v1.md, never
inline in this module (CLAUDE.md convention).

MEASURED (2026-09-10, evals/shotbench, 86 items):
    gemini-3.5-flash-lite   87.1% on shot size + framing, $0.017/50 imgs, 1.79s
    gemini-3.8-flash        6.7x cost, 8x latency, 503 on ~83% of calls

Set VISION_MODEL to override. ShotVL-7B may beat both once benchmarked on GPU,
which would make the whole pipeline free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.costlog import CostLog


@dataclass
class ShotDescription:
    shot_size: str
    framing: str
    description: str
    camera_motion: str | None = None
    confidence: float | None = None


def describe(frames: list[Path], cost: CostLog,
             model: str | None = None) -> ShotDescription:
    """Describe one shot from 2-3 sampled frames.

    Must allow enough output tokens for the model to think before answering. At
    16 tokens Gemini 3 returns an empty string with finishReason=MAX_TOKENS,
    which looks like a model failure but is a caller bug.
    """
    raise NotImplementedError("stage 3")
