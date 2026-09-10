"""Reference-driven reel editor pipeline.

Stage order (see CLAUDE.md):
  1 segment  -> 2 rhythm -> 3 describe -> 4 assemble
  5 ingest   -> 6 match  -> 7 gaps     -> 8 render

The Template (pipeline.template) is the contract between 1-4 and 5-8.
"""

from pipeline.template import (  # noqa: F401
    SCHEMA_VERSION, RhythmPosition, Slot, Template, TemplateError,
    positions_from_beats,
)
from pipeline.costlog import CostLog  # noqa: F401

__all__ = ["SCHEMA_VERSION", "RhythmPosition", "Slot", "Template",
           "TemplateError", "positions_from_beats", "CostLog"]
