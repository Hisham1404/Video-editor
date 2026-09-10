"""Template: the contract between analysis and render.

This module exists to make CLAUDE.md's single hardest rule impossible to break
by accident:

    Never store cut timings in absolute seconds.

The reference's music cannot ship with the output, so every timeline has to be
re-mappable onto a different track at a different tempo. If a duration is stored
as "1.4 seconds" that re-mapping is lossy and wrong -- the cut no longer lands on
the beat. SPEC.md calls retrofitting this "rebuilding the timeline model".

So the rule is enforced three ways here, not documented and hoped for:

1. There is no seconds field anywhere in the dataclasses.
2. `validate()` rejects any incoming JSON whose keys look like absolute time.
3. Seconds only ever appear as the *output* of `resolve()`, which requires a
   target tempo -- you cannot get a number of seconds without saying which track
   you are laying the cut against.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"

# Keys that would smuggle absolute time into the template. Checked against
# incoming JSON so a well-meaning future change can't quietly reintroduce them.
_FORBIDDEN_KEY = re.compile(
    r"(^|_)(sec|secs|second|seconds|ms|millis|milliseconds|timecode|tc)($|_)"
    r"|^(start|end|duration|offset|t)_?(s|sec|secs|seconds|ms)$",
    re.IGNORECASE,
)

# Fields allowed to carry a reference-side wall-clock value. These describe the
# *source* reel for provenance and are never used to place a cut.
_PROVENANCE_ALLOWLIST = {"reference_duration_seconds", "source_fps"}

SHOT_SIZES = ("extreme wide", "wide", "medium wide", "medium",
              "medium close up", "close up", "extreme close up")
FRAMINGS = ("single", "two shot", "three shot", "group", "over the shoulder",
            "insert", "establishing", "unknown")


class TemplateError(ValueError):
    """Raised when a template violates the schema or the no-seconds rule."""


@dataclass(frozen=True)
class RhythmPosition:
    """A point in time expressed purely as musical structure.

    `beat` is the absolute beat index from the start of the track. The rest is
    derived structure that survives a tempo change:

      bar / beat_in_bar   -- where the cut sits inside the bar
      phrase / beat_in_phrase -- where it sits inside the musical phrase, which
                            is what makes a cut feel like it belongs to the
                            section rather than merely landing on a beat
      subdivision         -- fractional offset from the beat, 0.0 on the beat,
                            0.5 an eighth late, 0.25 a sixteenth late
    """

    beat: int
    subdivision: float = 0.0
    bar: int = 0
    beat_in_bar: int = 0
    phrase: int = 0
    beat_in_phrase: int = 0

    def __post_init__(self) -> None:
        if self.beat < 0:
            raise TemplateError(f"beat index must be >= 0, got {self.beat}")
        if not 0.0 <= self.subdivision < 1.0:
            raise TemplateError(
                f"subdivision must be in [0.0, 1.0), got {self.subdivision}")

    @property
    def absolute_beats(self) -> float:
        """Position in beats, including the sub-beat offset."""
        return self.beat + self.subdivision

    def resolve(self, bpm: float, origin_beat: int = 0) -> float:
        """Convert to seconds against a *specific* tempo.

        This is the only place seconds are produced, and it is impossible to
        call without naming the track you are resolving against."""
        if bpm <= 0:
            raise TemplateError(f"bpm must be positive, got {bpm}")
        return (self.absolute_beats - origin_beat) * (60.0 / bpm)


@dataclass
class Slot:
    """One shot-shaped hole in the timeline, described but not yet filled."""

    index: int
    start: RhythmPosition
    end: RhythmPosition

    # What the reference did here. Filled by the vision stage.
    shot_size: str = "unknown"
    framing: str = "unknown"
    description: str = ""

    # v2 fields. Present in the schema from v1 so adding them later is not a
    # breaking change; None means "not analysed", not "no motion".
    camera_motion: str | None = None

    # Filled by the matching stage.
    matched_asset: str | None = None
    match_confidence: float | None = None
    generation_prompt: str | None = None

    def __post_init__(self) -> None:
        if self.end.absolute_beats <= self.start.absolute_beats:
            raise TemplateError(
                f"slot {self.index}: end ({self.end.absolute_beats}) must be "
                f"after start ({self.start.absolute_beats})")
        if self.match_confidence is not None:
            if not 0.0 <= self.match_confidence <= 1.0:
                raise TemplateError(
                    f"slot {self.index}: confidence must be in [0,1], "
                    f"got {self.match_confidence}")

    @property
    def duration_beats(self) -> float:
        return self.end.absolute_beats - self.start.absolute_beats

    @property
    def is_gap(self) -> bool:
        """A slot no asset satisfied -- the generative-fill contribution."""
        return self.matched_asset is None

    def duration_seconds(self, bpm: float) -> float:
        """Length in seconds against a given tempo. Requires a tempo, by design."""
        if bpm <= 0:
            raise TemplateError(f"bpm must be positive, got {bpm}")
        return self.duration_beats * (60.0 / bpm)


@dataclass
class Template:
    """An ordered list of slots plus the musical frame they were measured in.

    `reference_bpm` is provenance, not timing. It records what the reference was
    cut against so the analysis is reproducible; the render uses the *user's*
    tempo. Nothing in the render path should read it."""

    slots: list[Slot] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    time_signature: tuple[int, int] = (4, 4)
    beats_per_phrase: int = 32
    reference_bpm: float | None = None
    reference_id: str | None = None
    notes: str = ""

    # ---- invariants -----------------------------------------------------

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise TemplateError(
                f"schema version {self.schema_version!r} != {SCHEMA_VERSION!r}. "
                f"Migrate the template before use.")
        if self.time_signature[0] <= 0 or self.time_signature[1] <= 0:
            raise TemplateError(f"bad time signature {self.time_signature}")
        for i, slot in enumerate(self.slots):
            if slot.index != i:
                raise TemplateError(
                    f"slot indices must be contiguous from 0; "
                    f"position {i} has index {slot.index}")
        for a, b in zip(self.slots, self.slots[1:]):
            if b.start.absolute_beats < a.end.absolute_beats:
                raise TemplateError(
                    f"slots {a.index} and {b.index} overlap: "
                    f"{a.end.absolute_beats} > {b.start.absolute_beats}")

    # ---- rendering ------------------------------------------------------

    def resolve(self, bpm: float, origin_beat: int = 0) -> list[tuple[float, float]]:
        """Lay this template onto a track at `bpm`, returning (start, end) seconds.

        This is the payoff for storing rhythm rather than seconds: the same
        template resolves onto any track, and cuts still land on the beat."""
        self.validate()
        return [(s.start.resolve(bpm, origin_beat), s.end.resolve(bpm, origin_beat))
                for s in self.slots]

    def total_beats(self) -> float:
        return self.slots[-1].end.absolute_beats if self.slots else 0.0

    def gaps(self) -> list[Slot]:
        return [s for s in self.slots if s.is_gap]

    # ---- serialisation --------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["time_signature"] = list(self.time_signature)
        return d

    def save(self, path: str | Path) -> None:
        self.validate()
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Template":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Template":
        assert_no_absolute_time(raw)
        slots = [
            Slot(
                index=s["index"],
                start=RhythmPosition(**s["start"]),
                end=RhythmPosition(**s["end"]),
                shot_size=s.get("shot_size", "unknown"),
                framing=s.get("framing", "unknown"),
                description=s.get("description", ""),
                camera_motion=s.get("camera_motion"),
                matched_asset=s.get("matched_asset"),
                match_confidence=s.get("match_confidence"),
                generation_prompt=s.get("generation_prompt"),
            )
            for s in raw.get("slots", [])
        ]
        ts = raw.get("time_signature", [4, 4])
        tpl = cls(
            slots=slots,
            schema_version=raw.get("schema_version", SCHEMA_VERSION),
            time_signature=(int(ts[0]), int(ts[1])),
            beats_per_phrase=raw.get("beats_per_phrase", 32),
            reference_bpm=raw.get("reference_bpm"),
            reference_id=raw.get("reference_id"),
            notes=raw.get("notes", ""),
        )
        tpl.validate()
        return tpl


def assert_no_absolute_time(obj: Any, _path: str = "") -> None:
    """Walk a decoded template and reject absolute-time keys.

    Catches the failure mode CLAUDE.md warns about: someone adds a convenient
    `start_seconds` alongside the rhythm fields, the render quietly starts
    reading it, and the template stops being tempo-portable. Loud failure now is
    cheaper than a timeline-model rewrite later."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            here = f"{_path}.{key}" if _path else key
            if key in _PROVENANCE_ALLOWLIST:
                continue
            if _FORBIDDEN_KEY.search(key):
                raise TemplateError(
                    f"absolute time is not allowed in templates: {here!r}. "
                    f"Store rhythm (beat, subdivision, phrase position) instead; "
                    f"see CLAUDE.md. If this really is source provenance, add it "
                    f"to _PROVENANCE_ALLOWLIST deliberately.")
            assert_no_absolute_time(val, here)
    elif isinstance(obj, (list, tuple)):
        for i, val in enumerate(obj):
            assert_no_absolute_time(val, f"{_path}[{i}]")


def positions_from_beats(
    beat_indices: Iterable[int],
    time_signature: tuple[int, int] = (4, 4),
    beats_per_phrase: int = 32,
) -> list[RhythmPosition]:
    """Turn bare beat indices into full rhythm positions.

    Derives bar and phrase structure so downstream code has phrase position
    without recomputing it, which is what makes a cut read as belonging to the
    section rather than merely landing on a beat."""
    per_bar = time_signature[0]
    out = []
    for b in beat_indices:
        out.append(RhythmPosition(
            beat=int(b),
            subdivision=0.0,
            bar=int(b) // per_bar,
            beat_in_bar=int(b) % per_bar,
            phrase=int(b) // beats_per_phrase,
            beat_in_phrase=int(b) % beats_per_phrase,
        ))
    return out
