"""Tests for the template contract.

The point of these is narrow: prove that CLAUDE.md's hardest rule -- never store
cut timings in absolute seconds -- is enforced by code rather than by memory,
and that a template genuinely re-maps onto a different tempo. If the tempo
portability test ever fails, the timeline model is broken and SPEC says that
means a rewrite.

Run with:  python -m pytest tests/ -q
"""

from __future__ import annotations

import json

import pytest

from pipeline.template import (
    SCHEMA_VERSION,
    RhythmPosition,
    Slot,
    Template,
    TemplateError,
    assert_no_absolute_time,
    positions_from_beats,
)


def make_template(cuts=(0, 4, 12, 16)) -> Template:
    """A template with cuts on the given beat indices."""
    pos = positions_from_beats(cuts)
    slots = [Slot(index=i, start=pos[i], end=pos[i + 1])
             for i in range(len(pos) - 1)]
    return Template(slots=slots, reference_bpm=120.0)


# --- the hard rule ------------------------------------------------------

@pytest.mark.parametrize("bad_key", [
    "start_seconds", "duration_sec", "end_ms", "timecode",
    "offset_seconds", "t_s", "cut_time_ms", "seconds",
])
def test_absolute_time_keys_are_rejected(bad_key):
    """Any key that smuggles wall-clock time into a template must fail loudly."""
    payload = {"slots": [{"index": 0, bad_key: 1.4}]}
    with pytest.raises(TemplateError, match="absolute time"):
        assert_no_absolute_time(payload)


def test_absolute_time_rejected_when_nested_deep():
    payload = {"slots": [{"index": 0, "meta": {"inner": {"duration_ms": 900}}}]}
    with pytest.raises(TemplateError, match="absolute time"):
        assert_no_absolute_time(payload)


def test_provenance_fields_are_allowed():
    """Source metadata may carry seconds; it never places a cut."""
    assert_no_absolute_time({"reference_duration_seconds": 30.0, "source_fps": 30})


def test_rhythm_keys_pass():
    assert_no_absolute_time({
        "slots": [{"index": 0,
                   "start": {"beat": 0, "subdivision": 0.0, "phrase": 0},
                   "end": {"beat": 4, "subdivision": 0.5, "phrase": 0}}]
    })


def test_loading_a_template_with_seconds_fails():
    """End-to-end: the loader refuses it, not just the walker."""
    raw = make_template().to_dict()
    raw["slots"][0]["start_seconds"] = 0.0
    with pytest.raises(TemplateError, match="absolute time"):
        Template.from_dict(raw)


# --- tempo portability: the reason the rule exists ----------------------

def test_same_template_resolves_differently_per_tempo():
    tpl = make_template()
    slow = tpl.resolve(bpm=60.0)
    fast = tpl.resolve(bpm=120.0)
    # Twice the tempo, half the wall-clock duration -- same musical structure.
    assert slow[0] == (0.0, 4.0)
    assert fast[0] == (0.0, 2.0)
    for (s0, e0), (s1, e1) in zip(slow, fast):
        assert pytest.approx(e0 - s0, rel=1e-9) == 2 * (e1 - s1)


def test_cuts_still_land_on_beats_after_retempo():
    """The whole point: re-map onto any track and cuts stay on the grid."""
    tpl = make_template(cuts=(0, 4, 8, 16))
    for bpm in (78.0, 96.5, 120.0, 174.0):
        beat_len = 60.0 / bpm
        for start, end in tpl.resolve(bpm):
            assert pytest.approx(start / beat_len, abs=1e-9) == round(start / beat_len)
            assert pytest.approx(end / beat_len, abs=1e-9) == round(end / beat_len)


def test_subdivision_survives_retempo():
    off = RhythmPosition(beat=4, subdivision=0.5, bar=1, beat_in_bar=0)
    assert off.resolve(bpm=120.0) == pytest.approx(2.25)
    assert off.resolve(bpm=60.0) == pytest.approx(4.5)


# --- structure ----------------------------------------------------------

def test_phrase_position_is_derived():
    pos = positions_from_beats([0, 4, 32, 33], beats_per_phrase=32)
    assert (pos[0].bar, pos[0].beat_in_bar) == (0, 0)
    assert (pos[1].bar, pos[1].beat_in_bar) == (1, 0)
    assert pos[2].phrase == 1 and pos[2].beat_in_phrase == 0
    assert pos[3].phrase == 1 and pos[3].beat_in_phrase == 1


def test_zero_length_slot_rejected():
    p = RhythmPosition(beat=4)
    with pytest.raises(TemplateError, match="must be after"):
        Slot(index=0, start=p, end=p)


def test_overlapping_slots_rejected():
    pos = positions_from_beats([0, 8, 4, 12])
    tpl = Template(slots=[Slot(index=0, start=pos[0], end=pos[1]),
                          Slot(index=1, start=pos[2], end=pos[3])])
    with pytest.raises(TemplateError, match="overlap"):
        tpl.validate()


def test_non_contiguous_indices_rejected():
    pos = positions_from_beats([0, 4, 8])
    tpl = Template(slots=[Slot(index=0, start=pos[0], end=pos[1]),
                          Slot(index=7, start=pos[1], end=pos[2])])
    with pytest.raises(TemplateError, match="contiguous"):
        tpl.validate()


def test_bad_subdivision_rejected():
    with pytest.raises(TemplateError, match="subdivision"):
        RhythmPosition(beat=0, subdivision=1.0)


def test_schema_version_mismatch_rejected():
    tpl = make_template()
    tpl.schema_version = "0.9"
    with pytest.raises(TemplateError, match="schema version"):
        tpl.validate()


def test_resolve_requires_positive_tempo():
    with pytest.raises(TemplateError, match="bpm"):
        make_template().resolve(bpm=0.0)


# --- round trip and gaps ------------------------------------------------

def test_round_trip_preserves_structure(tmp_path):
    tpl = make_template()
    tpl.slots[1].shot_size = "close up"
    tpl.slots[1].description = "hands on a steering wheel"
    path = tmp_path / "t.json"
    tpl.save(path)
    back = Template.load(path)
    assert back.schema_version == SCHEMA_VERSION
    assert [s.duration_beats for s in back.slots] == [s.duration_beats for s in tpl.slots]
    assert back.slots[1].shot_size == "close up"


def test_gap_carries_both_prompt_and_anchor_image_through_round_trip(tmp_path):
    """A gap needs two things, and losing either one silently breaks the loop.

    The prompt says what to generate; the anchor says what it should look like.
    External video models are image-to-video, so a prompt that survives
    serialisation without its anchor produces a clip with the wrong face and
    the wrong room -- which only shows up once it is cut against its neighbour.
    """
    tpl = make_template()
    gap = tpl.slots[1]
    gap.matched_asset = None
    gap.generation_prompt = "Close-up, single subject, side-lit, 1.2 seconds"
    gap.generation_reference_asset = "user_clip_07.mp4"

    path = tmp_path / "t.json"
    tpl.save(path)
    back = Template.load(path)

    assert back.slots[1].is_gap
    assert back.slots[1].generation_prompt == gap.generation_prompt
    assert back.slots[1].generation_reference_asset == "user_clip_07.mp4"


def test_anchor_is_absent_on_a_filled_slot(tmp_path):
    """Only gaps carry an anchor. A filled slot with one means stage 7 ran
    somewhere it should not have."""
    tpl = make_template()
    tpl.slots[0].matched_asset = "user_clip_01.mp4"
    tpl.slots[0].match_confidence = 0.88
    path = tmp_path / "t.json"
    tpl.save(path)
    back = Template.load(path)
    assert not back.slots[0].is_gap
    assert back.slots[0].generation_reference_asset is None


def test_saved_json_contains_no_seconds_key(tmp_path):
    path = tmp_path / "t.json"
    make_template().save(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert_no_absolute_time(raw)   # must not raise


def test_unmatched_slots_are_gaps():
    tpl = make_template()
    assert len(tpl.gaps()) == len(tpl.slots)
    tpl.slots[0].matched_asset = "clip_01.mp4"
    tpl.slots[0].match_confidence = 0.81
    assert len(tpl.gaps()) == len(tpl.slots) - 1


def test_confidence_out_of_range_rejected():
    pos = positions_from_beats([0, 4])
    with pytest.raises(TemplateError, match="confidence"):
        Slot(index=0, start=pos[0], end=pos[1], match_confidence=1.4)
