"""Stage 7 -- gap detection and generation-prompt emission.

This is the project's actual novel contribution (SPEC section 4): neither
arXiv 2105.06988 nor 2511.02505 does generative fill; both assume the user's
repository satisfies every slot.

CLAUDE.md, absolutely: video generation NEVER runs inside this app. This stage
emits text. It does not call a generation API. That is a deliberate cost
decision, not an unfinished feature.
"""

from __future__ import annotations

from pipeline.template import Slot, Template


def emit_prompts(template: Template) -> Template:
    """Write a generation_prompt onto every unfilled slot."""
    raise NotImplementedError("stage 7")


def prompt_for_slot(slot: Slot, tempo_bpm: float) -> str:
    """Build one generation prompt from a slot's shot size, framing and
    description, including how long the returned clip needs to be so it covers
    the slot at the user's tempo."""
    raise NotImplementedError("stage 7")
