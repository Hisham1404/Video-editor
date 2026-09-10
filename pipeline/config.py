"""Runtime settings. Secrets come from the environment or .env, never source."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path | None = None) -> None:
    """Read KEY=value lines into os.environ. Existing vars win."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


@dataclass
class Settings:
    # Vision model for stage 3. Chosen by evals/shotbench, not by preference.
    # Measured 2026-09-10 on an 86-item subset: gemini-3.5-flash-lite scored
    # 87.1% on shot size + framing at $0.017 per 50-image reference, with no
    # thinking-token overhead. gemini-3.8-flash was 6.7x costlier, 8x slower,
    # and returned 503 on ~83% of calls. Revisit once ShotVL-7B is benchmarked
    # on a GPU -- local would make the pipeline fully free.
    vision_model: str = os.environ.get("VISION_MODEL", "gemini-3.5-flash-lite")

    # Gemini needs headroom for thinking tokens or it returns an empty string
    # with finishReason=MAX_TOKENS. 16 is not enough. This bit us once already.
    vision_max_output_tokens: int = 512

    # Stage 2. librosa has no downbeat tracker and reports beats ~22ms late;
    # madmom requires Python <3.10 and is unusable. beat_this measured 8.5ms MAE
    # with downbeats, CPU-capable at 18.7x realtime.
    beat_model: str = os.environ.get("BEAT_MODEL", "beat_this")

    # Stage 5/6. CPU throughput measured on an i7-1360P: ViT-B/32 69.5ms/img,
    # SigLIP base/16 188ms, ViT-L/14 930ms. Swappable on purpose -- SPEC calls
    # matching the make-or-break component.
    embed_model: str = os.environ.get("EMBED_MODEL", "clip-vit-base-patch32")

    runs_dir: Path = ROOT / "runs"
    prompts_dir: Path = ROOT / "prompts"

    def prompt_path(self, name: str, version: str = "v1") -> Path:
        """CLAUDE.md: prompts live in versioned files, never inline in code."""
        return self.prompts_dir / name / f"{version}.md"


settings = Settings()
