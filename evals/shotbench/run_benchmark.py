#!/usr/bin/env python3
"""
ShotBench harness - compare cinematic-understanding VLMs for the reel editor.

Runs local HF vision models and the Gemini API against the ShotBench test set
(3,572 MCQ items over 8 cinematography dimensions) and reports per-dimension
accuracy, latency and cost.

Why this exists: the published ShotBench leaderboard's newest commercial entry is
Gemini-2.5-flash-preview (April 2025) and ShotVL-7B has not been updated since
September 2025. Whether a specialist model on a stale base still beats a modern
generalist is unmeasured. This measures it.

Design notes:
  - Results are appended to JSONL per model, one line per item. Re-running skips
    completed items, so a spot-instance eviction costs only the in-flight item.
  - Prompting matches VLMEvalKit's MCQ convention (the format ShotBench ships in)
    so the ShotVL-7B number is directly comparable to the published 70.1%.
  - Models are loaded one at a time and freed, so a 24GB card is enough.

Usage:
    python run_benchmark.py --list-gemini-models     # discover the exact API id
    python run_benchmark.py --models shotvl-7b
    python run_benchmark.py --models all --limit 200 # quick smoke run
    python run_benchmark.py --report                 # score whatever is done
"""

from __future__ import annotations

import argparse
import ast
import gc
import json
import os
import re
import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

HF_DATASET = "Vchitect/ShotBench"

# The two dimensions the reel-editor template actually depends on. Overall
# average is the wrong metric for us -- lens size and lighting don't feed the
# template, shot size and framing do.
KEY_CATEGORIES = ("shot size", "shot framing")

# USD per million tokens, verified against ai.google.dev/gemini-api/docs/pricing
# on 2026-09-10. The 3.6/3.7/3.8 Flash rates are INTRODUCTORY through 2026-12-31
# and double on 2027-01-01. Flash-Lite is not introductory, so it does not move.
#
# Thinking tokens bill as output. On gemini-3.8-flash they are ~473 of 474 output
# tokens for a one-letter MCQ answer, so they dominate cost -- measured, not
# assumed. Flash-Lite emits none.
GEMINI_PRICING: dict[str, dict[str, float]] = {
    "gemini-3.8-flash":      {"in": 0.75, "out": 3.75, "doubles_2027": 1},
    "gemini-3.7-flash":      {"in": 0.75, "out": 3.75, "doubles_2027": 1},
    "gemini-3.6-flash":      {"in": 0.75, "out": 3.75, "doubles_2027": 1},
    "gemini-3.5-flash":      {"in": 1.50, "out": 9.00, "doubles_2027": 0},
    "gemini-3.5-flash-lite": {"in": 0.30, "out": 2.50, "doubles_2027": 0},
    "gemini-2.5-flash":      {"in": 0.30, "out": 2.50, "doubles_2027": 0},
    "gemini-2.5-flash-lite": {"in": 0.10, "out": 0.40, "doubles_2027": 0},
}
DEFAULT_PRICING = {"in": 0.75, "out": 3.75, "doubles_2027": 1}


def pricing_for(model_id: str) -> dict[str, float]:
    if model_id in GEMINI_PRICING:
        return GEMINI_PRICING[model_id]
    for known, rates in GEMINI_PRICING.items():  # tolerate -preview / date suffixes
        if model_id.startswith(known):
            return rates
    return DEFAULT_PRICING


def load_env_file(path: Path) -> None:
    """Read KEY=value lines into the environment if not already set.

    Keeps the API key out of shell history and out of the process command line.
    Existing environment variables win, so an explicit export always overrides
    the file."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


@dataclass
class ModelSpec:
    key: str
    kind: str  # "hf" | "gemini"
    model_id: str
    note: str = ""
    # Approximate BF16 weight footprint in GB, for the preflight VRAM check.
    approx_vram_gb: float = 0.0


MODELS: dict[str, ModelSpec] = {
    "shotvl-3b": ModelSpec(
        "shotvl-3b", "hf", "Vchitect/ShotVL-3B",
        "Cinematic specialist, 3.75B. Published ShotBench avg 65.1.", 7.5,
    ),
    "shotvl-7b": ModelSpec(
        "shotvl-7b", "hf", "Vchitect/ShotVL-7B",
        "Cinematic specialist, 8.29B. Published ShotBench avg 70.1.", 16.6,
    ),
    "qwen3-vl-8b": ModelSpec(
        "qwen3-vl-8b", "hf", "Qwen/Qwen3-VL-8B-Instruct",
        "Generalist baseline, the generation after ShotVL's base.", 17.5,
    ),
    "qwen3.5-9b": ModelSpec(
        "qwen3.5-9b", "hf", "Qwen/Qwen3.5-9B",
        "Modern generalist (2026-03). The real test of specialist vs. base progress.", 19.3,
    ),
    # --- cheaper/newer generalists, added after surveying HuggingFace --------
    # The survey's main result was negative and worth recording: ShotVL-3B and
    # ShotVL-7B are the ONLY cinematography-tuned VLMs on the Hub. Searches for
    # cinematic / cinematography / shot-scale / shot-type / camera-angle return
    # image *generation* LoRAs (SDXL, Flux, LTX), not understanding models. The
    # specialist field is already fully tested; what is left is finding a
    # generalist that is cheaper or better.
    "qwen3-vl-2b": ModelSpec(
        "qwen3-vl-2b", "hf", "Qwen/Qwen3-VL-2B-Instruct",
        "Quarter the size of the 8B already tested. If it lands within a point "
        "or two, the hosting economics change completely.", 4.3,
    ),
    "qwen3-vl-4b": ModelSpec(
        "qwen3-vl-4b", "hf", "Qwen/Qwen3-VL-4B-Instruct",
        "Half the 8B. The middle point that says whether accuracy here scales "
        "with parameters at all.", 8.9,
    ),
    "qwen3.6-35b-a3b-fp8": ModelSpec(
        "qwen3.6-35b-a3b-fp8", "hf", "Qwen/Qwen3.6-35B-A3B-FP8",
        "Mixture-of-experts: ~3B parameters active per token against 35B of "
        "stored knowledge. FP8 because bf16 is 71.9GB and will not fit a 48GB "
        "card -- this build is 37.5GB, which fits with roughly 10GB spare.", 37.5,
    ),
    # google/gemma-4-31B-it (62.5GB) and gemma-4-26B-A4B-it (51.6GB) are both
    # too large for a 48GB L40S in bf16. They need an 80GB instance or a
    # community quantisation; deliberately not listed rather than listed and
    # failing preflight on the night.
    "dinov2-shotscale": ModelSpec(
        "dinov2-shotscale", "classifier", "aslakey/shot_scale",
        "Not a VLM: a 1.2GB DINOv2 classification head. Knows 5 classes, not "
        "7, so it is only comparable under --collapse5.", 1.2,
    ),
    "nv-nemotron-omni": ModelSpec(
        "nv-nemotron-omni", "nvidia", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "Cheapest per image measured: 284 input tokens vs Gemini's 1141 and "
        "Groq-Qwen's 1303. Omni-modal, and it answered a checkable colour "
        "question correctly.", 0.0,
    ),
    "nv-llama32-11b-vision": ModelSpec(
        "nv-llama32-11b-vision", "nvidia", "meta/llama-3.2-11b-vision-instruct",
        "Meta's VLM baseline. Works, but 1623 tokens per image is the most "
        "expensive of the three hosted options.", 0.0,
    ),
    "groq-qwen3.8-27b": ModelSpec(
        "groq-qwen3.8-27b", "groq", "qwen/qwen3.8-27b",
        "Open weights, someone else's GPU. Multimodal despite the name -- "
        "verified by sending an image, not by reading the model card. Free "
        "tier: 8k tokens/min, 1000 requests/day.", 0.0,
    ),
    "gemini": ModelSpec(
        "gemini", "gemini", "gemini-3.8-flash",
        "Commercial incumbent. Thinks by default; thinking bills as output.", 0.0,
    ),
    "gemini-lite": ModelSpec(
        "gemini-lite", "gemini", "gemini-3.5-flash-lite",
        "Cheaper, emits no thinking tokens, and is NOT on introductory pricing "
        "so it does not double on 2027-01-01.", 0.0,
    ),
}

DEFAULT_SET = ["shotvl-7b", "shotvl-3b", "qwen3-vl-8b", "qwen3.5-9b",
               "gemini", "gemini-lite"]


# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------

def _parse_listish(raw: str) -> list[str]:
    """test.tsv stores lists inconsistently: JSON for `type`, Python literals
    for `path`. Try both before giving up."""
    if raw is None:
        return []
    raw = raw.strip()
    if not raw:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            val = parser(raw)
            if isinstance(val, list):
                return [str(v) for v in val]
            return [str(val)]
        except Exception:
            continue
    return [raw]


@dataclass
class Item:
    index: int
    media_type: str
    paths: list[str]
    question: str
    options: dict[str, str]
    answer: str
    category: str


#: An independent shot-scale set, used to check ShotBench's verdict against a
#: source none of these models was tuned on. 2,919 frames from film-grab.com;
#: the test split is exactly the 863 human hand-labelled rows, which is the only
#: part we touch -- the rest carries DINOv2 and Claude Opus labels and would be
#: measuring another model's opinion rather than ground truth.
FILMSHOTS_DATASET = "szymonrucinski/types-of-film-shots"

#: Parquet stores `label` as an index into this list, alphabetical.
FILMSHOTS_CLASSES = ["ambiguous", "closeUp", "detail", "extremeLongShot",
                     "fullShot", "longShot", "mediumCloseUp", "mediumShot"]

#: Rendered into the prompt. `ambiguous` is deliberately absent: only 4 rows
#: carry it and "the label is unclear" is not a shot size a model can name.
FILMSHOTS_OPTIONS = {
    "extremeLongShot": "Extreme long shot",
    "longShot": "Long shot",
    "fullShot": "Full shot",
    "mediumShot": "Medium shot",
    "mediumCloseUp": "Medium close-up",
    "closeUp": "Close-up",
    "detail": "Detail / insert (extreme close-up)",
}

FILMSHOTS_CATEGORY = "shot scale (film-grab)"


def ensure_filmshots(data_dir: Path) -> list[tuple[str, str]]:
    """Fetch the human-labelled split and write its frames to disk.

    Returns (relative image path, class name) pairs. Images live in the parquet
    as raw bytes, so they are materialised once and then read through the same
    path as every other item.
    """
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    img_dir = data_dir / "filmshots"
    index = data_dir / "filmshots_index.tsv"
    if index.exists():
        rows = [tuple(l.rstrip("\n").split("\t"))
                for l in index.read_text(encoding="utf-8").splitlines()]
        return [(a, b) for a, b in rows]

    img_dir.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {FILMSHOTS_DATASET} (human split) ...")
    path = hf_hub_download(FILMSHOTS_DATASET,
                           "data/test-00000-of-00001.parquet",
                           repo_type="dataset")
    table = pq.read_table(path).to_pydict()

    out: list[tuple[str, str]] = []
    for i, (img, label, annot) in enumerate(zip(
            table["image"], table["label"], table["annotator"])):
        # Guard rather than assume: the split is all-human today, but a future
        # re-upload adding AI rows must not silently become ground truth.
        if annot != "human":
            continue
        name = FILMSHOTS_CLASSES[label]
        if name not in FILMSHOTS_OPTIONS:
            continue
        rel = f"filmshots/{i:05d}.jpg"
        (data_dir / rel).write_bytes(img["bytes"])
        out.append((rel, name))

    index.write_text("".join(f"{a}\t{b}\n" for a, b in out), encoding="utf-8")
    print(f"  {len(out)} human-labelled frames")
    return out


def load_filmshots(data_dir: Path, limit: int | None) -> list["Item"]:
    """Build MCQ items, shuffling the options per item.

    The options are shuffled -- deterministically, seeded by the item index so
    runs stay reproducible -- because a fixed order would hand free points to
    whichever model happens to favour the letter the answer sits at. That is not
    hypothetical here: on ShotBench, Qwen3-VL-8B chose A on 15.4% of its answers
    while A was correct 24.0% of the time. A fixed layout would measure that bias
    instead of measuring cinematography.
    """
    import random

    pairs = ensure_filmshots(data_dir)
    letters = "ABCDEFG"
    keys = list(FILMSHOTS_OPTIONS)
    items: list[Item] = []
    for i, (rel, gold_name) in enumerate(pairs):
        order = keys[:]
        random.Random(i).shuffle(order)
        options = {letters[j]: FILMSHOTS_OPTIONS[k] for j, k in enumerate(order)}
        answer = letters[order.index(gold_name)]
        items.append(Item(
            index=i,
            media_type="image",
            paths=[rel],
            question="What is the shot scale of this frame?",
            options=options,
            answer=answer,
            category=FILMSHOTS_CATEGORY,
        ))
        if limit and len(items) >= limit:
            break
    return items


def load_reels(tsv: Path, limit: int | None) -> list["Item"]:
    """Your own labelled reel frames, from evals/reels/label.py.

    The only test on the app's actual input distribution. ShotBench and
    film-grab are both landscape feature film; the product ingests vertical
    phone video, and a model can be good at one and poor at the other.

    Same 7 classes and the same seeded option shuffle as the film-grab loader,
    so the two numbers are directly comparable -- that comparison is the whole
    point, since it measures how far a score earned on cinema carries over.
    """
    import random

    if not tsv.exists():
        sys.exit(f"--reels-tsv not found: {tsv}\n"
                 f"Build it first:  python evals/reels/label.py extract ... "
                 f"then label, then export")
    root = tsv.parent
    letters, keys = "ABCDEFG", list(FILMSHOTS_OPTIONS)
    items: list[Item] = []
    for i, line in enumerate(tsv.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        rel, _, gold_name = line.partition("\t")
        gold_name = gold_name.strip()
        if gold_name not in FILMSHOTS_OPTIONS:
            sys.exit(f"{tsv}:{i+1}: unknown class {gold_name!r}. "
                     f"Expected one of {list(FILMSHOTS_OPTIONS)}")
        if not (root / rel).exists():
            sys.exit(f"{tsv}:{i+1}: missing frame {root / rel}")
        order = keys[:]
        random.Random(i).shuffle(order)
        items.append(Item(
            index=i,
            media_type="image",
            paths=[rel],
            question="What is the shot scale of this frame?",
            options={letters[j]: FILMSHOTS_OPTIONS[k] for j, k in enumerate(order)},
            answer=letters[order.index(gold_name)],
            category="shot scale (own reels)",
        ))
        if limit and len(items) >= limit:
            break
    return items


def ensure_dataset(data_dir: Path, want_videos: bool,
                   want_media: bool = True) -> Path:
    """Download and extract ShotBench. images.tar is 2.2GB, videos.tar 1.2GB.

    `want_media=False` fetches only the TSV. The --no-image ablation never opens
    a single frame, so pulling 3.4GB of media for it would be 3.4GB of rented
    bandwidth and minutes of billed time spent on files the run cannot touch.
    """
    from huggingface_hub import hf_hub_download

    data_dir.mkdir(parents=True, exist_ok=True)
    tsv = data_dir / "test.tsv"
    if not tsv.exists():
        print("  downloading test.tsv ...")
        src = hf_hub_download(HF_DATASET, "test.tsv", repo_type="dataset")
        tsv.write_bytes(Path(src).read_bytes())

    if not want_media:
        print("  --no-image: skipping images.tar and videos.tar (3.4GB unused)")
        return tsv

    wanted = [("images.tar", "image")]
    if want_videos:
        wanted.append(("videos.tar", "video"))

    for archive, marker in wanted:
        # The tars expand to image/ and video/ directories.
        if (data_dir / marker).exists():
            continue
        print(f"  downloading {archive} (this is the slow part) ...")
        src = hf_hub_download(HF_DATASET, archive, repo_type="dataset")
        print(f"  extracting {archive} ...")
        with tarfile.open(src) as tf:
            tf.extractall(data_dir)
    return tsv


def load_items(tsv: Path, categories: list[str] | None, limit: int | None,
               skip_video: bool) -> list[Item]:
    import csv

    items: list[Item] = []
    with tsv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            types = _parse_listish(row.get("type", ""))
            media_type = (types[0] if types else "image").lower()
            if skip_video and media_type == "video":
                continue
            category = (row.get("category") or "").strip()
            if categories and category not in categories:
                continue
            try:
                options = json.loads(row["options"])
            except Exception:
                options = ast.literal_eval(row["options"])
            items.append(Item(
                index=int(row["index"]),
                media_type=media_type,
                paths=_parse_listish(row.get("path", "")),
                question=(row.get("question") or "").strip(),
                options={k: str(v) for k, v in options.items()},
                answer=(row.get("answer") or "").strip().upper(),
                category=category,
            ))
            if limit and len(items) >= limit:
                break
    return items


# --------------------------------------------------------------------------
# Prompting and answer extraction
# --------------------------------------------------------------------------

def build_prompt(item: Item) -> str:
    """VLMEvalKit MCQ convention -- matches how ShotBench was scored, so our
    ShotVL-7B number is comparable to the published one."""
    lines = [item.question]
    for letter in sorted(item.options):
        lines.append(f"{letter}. {item.options[letter]}")
    lines.append("Answer with the option's letter from the given choices directly.")
    return "\n".join(lines)


def extract_answer(text: str, options: dict[str, str]) -> str | None:
    """Models don't reliably obey 'letter only'.

    Order matters here. Matching option *text* has to come before the loose
    bare-letter scan, otherwise the English article "a" in a sentence like
    "This is a Close Up shot" is read as option A. And option-text matching has
    to prefer the longest hit, or "Extreme Close Up" is shadowed by the "Close
    Up" substring and the item is scored as unparsed."""
    if not text:
        return None
    text = text.strip()
    valid = set(options)

    # The letter class comes from the options, never a hardcoded A-D. ShotBench
    # is 4-option so A-D was invisible for 3572 items x 4 models; on the 7-option
    # film-grab set it silently discarded every E, F and G as unparsed and scored
    # them wrong. It hit the models that answer with a bare letter hardest --
    # ShotVL-7B lost 51% of its answers that way and appeared to collapse -- so
    # the bug read as a finding about model quality. It was not.
    letters = "".join(sorted(valid))
    cls = f"[{letters}{letters.lower()}]"

    # 1. The expected case: the whole reply is a letter.
    m = re.match(rf"^\s*\(?({cls})\)?\s*[\.\):,]?\s*$", text)
    if m and m.group(1).upper() in valid:
        return m.group(1).upper()

    # 2. "Answer: C" / "the answer is B" / "option D".
    m = re.search(rf"\b(?:answer|option)\b\W{{0,12}}({cls})\b", text, re.I)
    if m and m.group(1).upper() in valid:
        return m.group(1).upper()

    # 3. Leading "C) Close Up" or "C. Close Up".
    m = re.match(rf"^\s*\(?({cls})[\.\):,\-]\s+\S", text)
    if m and m.group(1).upper() in valid:
        return m.group(1).upper()

    # 4. The option text appears verbatim; longest wins.
    low = text.lower()
    hits = sorted(
        ((len(v.strip()), k) for k, v in options.items() if v.strip().lower() in low),
        reverse=True,
    )
    if hits and (len(hits) == 1 or hits[0][0] > hits[1][0]):
        return hits[0][1]

    # 5. Last resort: a standalone capital letter. Lowercase is excluded to
    #    avoid the article "a"; ambiguity ("A or B") scores as unparsed.
    found = {c for c in re.findall(rf"(?<![A-Za-z])([{letters}])(?![A-Za-z])", text)}
    found &= valid
    if len(found) == 1:
        return found.pop()
    return None


# --------------------------------------------------------------------------
# Media loading
# --------------------------------------------------------------------------

def load_media(item: Item, data_dir: Path, video_frames: int) -> list[Any]:
    """Return a list of PIL images. Video items are uniformly frame-sampled --
    an approximation that will understate camera-movement scores relative to
    native video input. Documented, not hidden."""
    from PIL import Image

    out: list[Any] = []
    for rel in item.paths:
        path = data_dir / rel
        if not path.exists():
            alt = list(data_dir.rglob(Path(rel).name))
            if not alt:
                raise FileNotFoundError(f"missing media: {rel}")
            path = alt[0]

        if item.media_type == "video":
            out.extend(_sample_video_frames(path, video_frames))
        else:
            out.append(Image.open(path).convert("RGB"))
    return out


def _sample_video_frames(path: Path, n: int) -> list[Any]:
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total <= 0:
        cap.release()
        raise RuntimeError(f"unreadable video: {path}")
    idxs = [int(round(i * (total - 1) / max(n - 1, 1))) for i in range(n)]
    frames = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if ok:
            frames.append(Image.fromarray(frame[:, :, ::-1]))
    cap.release()
    if not frames:
        raise RuntimeError(f"no frames decoded: {path}")
    return frames


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------

class HFBackend:
    """Local transformers VLM. Uses the unified image-text-to-text API, which
    covers Qwen2.5-VL (ShotVL's base), Qwen3-VL and Qwen3.5."""

    def __init__(self, model_id: str, max_new_tokens: int = 128):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.torch = torch
        self.max_new_tokens = max_new_tokens
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        print(f"  loading {model_id} ...")
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            dtype=dtype,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True,
        )
        self.model.eval()

    def generate(self, images: list[Any], prompt: str) -> tuple[str, dict]:
        content = [{"type": "image", "image": im} for im in images]
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]

        # enable_thinking=False suppresses the chain-of-thought block on models
        # that have one. Measured on the full test set: Qwen3.5-9B scored 0.0%
        # across all 3572 items -- not because it cannot see, but because every
        # answer began "The user wants me to identify the shot size of the
        # provided image.\n\n1" and was cut off by the token budget before it
        # ever reached a letter. ShotVL-7B hit the same wall on 110 items.
        #
        # Templates that do not define this variable ignore it -- unknown kwargs
        # land in the Jinja context unused -- so it is safe for every model here.
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=False,
        )
        inputs = {k: (v.to(self.model.device) if hasattr(v, "to") else v)
                  for k, v in inputs.items()}

        with self.torch.inference_mode():
            out = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        trimmed = out[0][inputs["input_ids"].shape[1]:]
        text = self.processor.decode(trimmed, skip_special_tokens=True)
        return text.strip(), {}

    def close(self):
        del self.model
        gc.collect()
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set. Put it in .env beside this script, "
                 "or export it, then re-run.")
    return key


def _post_json(url: str, payload: dict, key: str, timeout: int = 180) -> dict:
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


class GeminiBackend:
    """Gemini via plain REST.

    Deliberately not using the google-genai SDK: version 2.22.0 raises
    "Cannot send a request, as the client has been closed" against httpx 0.28,
    and a benchmark that runs unattended on a rented GPU box should not carry a
    dependency that can break like that. urllib is in the standard library.

    max_output_tokens defaults high on purpose. Gemini 3 models think by default,
    and thinking spends the output budget before any answer is emitted -- at 16
    tokens every reply comes back empty with finishReason=MAX_TOKENS, which
    scores as 0% and looks like a model failure rather than a harness bug."""

    def __init__(self, model_id: str, media_resolution: str | None = None,
                 thinking_level: str | None = None, max_output_tokens: int = 512):
        self.key = _api_key()
        self.model_id = model_id
        self.media_resolution = media_resolution
        self.thinking_level = thinking_level
        self.max_output_tokens = max_output_tokens
        self.rates = pricing_for(model_id)
        self.in_tokens = 0
        self.out_tokens = 0      # billable output: answer + thinking
        self.think_tokens = 0    # tracked separately so its share is visible
        self.truncated = 0

    def generate(self, images: list[Any], prompt: str) -> tuple[str, dict]:
        import base64
        import io
        import urllib.error

        parts: list[dict] = []
        for im in images:
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=90)
            parts.append({"inline_data": {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(buf.getvalue()).decode("ascii"),
            }})
        parts.append({"text": prompt})

        gen_cfg: dict[str, Any] = {
            "temperature": 0.0,
            "maxOutputTokens": self.max_output_tokens,
        }
        if self.media_resolution:
            gen_cfg["mediaResolution"] = self.media_resolution
        if self.thinking_level:
            gen_cfg["thinkingConfig"] = {"thinkingLevel": self.thinking_level}

        payload = {"contents": [{"role": "user", "parts": parts}],
                   "generationConfig": gen_cfg}
        url = f"{API_ROOT}/models/{self.model_id}:generateContent"

        last_err: Exception | None = None
        for attempt in range(6):
            try:
                data = _post_json(url, payload, self.key)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:200]
                last_err = RuntimeError(f"HTTP {exc.code}: {body}")
                # 503 is common on gemini-3.8-flash under load; 429 is quota.
                if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                    time.sleep(min(2 ** attempt * 2, 45))
                    continue
                raise last_err
            except Exception as exc:
                last_err = exc
                if attempt < 5:
                    time.sleep(min(2 ** attempt * 2, 45))
                    continue
                raise

            usage = data.get("usageMetadata", {}) or {}
            pt = usage.get("promptTokenCount", 0) or 0
            ct = usage.get("candidatesTokenCount", 0) or 0
            th = usage.get("thoughtsTokenCount", 0) or 0
            self.in_tokens += pt
            self.out_tokens += ct + th
            self.think_tokens += th

            cand = (data.get("candidates") or [{}])[0]
            finish = cand.get("finishReason")
            text = "".join(
                p.get("text", "")
                for p in ((cand.get("content") or {}).get("parts") or [])
            )
            if finish == "MAX_TOKENS" and not text.strip():
                self.truncated += 1
            return text.strip(), {
                "in_tokens": pt, "out_tokens": ct, "think_tokens": th,
                "finish": finish,
            }
        raise RuntimeError(f"gemini failed after retries: {last_err}")

    def cost_usd(self) -> float:
        return (self.in_tokens / 1e6 * self.rates["in"]
                + self.out_tokens / 1e6 * self.rates["out"])

    def close(self):
        pass


#: aslakey/shot_scale predicts 5 classes; this benchmark uses 7. Mapping ours
#: onto theirs is the only honest direction -- theirs cannot be split, ours can
#: be merged. Both `extremeLongShot` and `longShot` become `wide`, and both
#: `mediumShot` and `mediumCloseUp` become `medium`, so scoring happens in the
#: coarser 5-class space for every model or the comparison is rigged.
COLLAPSE_5 = {
    "extremeLongShot": "wide",
    "longShot": "wide",
    "fullShot": "full",
    "mediumShot": "medium",
    "mediumCloseUp": "medium",
    "closeUp": "close_up",
    "detail": "extreme_close_up",
}


class ClassifierBackend:
    """A plain image classifier, not a VLM.

    Worth measuring because it is a different answer to the problem. The task is
    mapping an image to one of seven labels; it does not need a model that can
    converse. aslakey/shot_scale is a 1.2GB DINOv2 head against 4.3-37.5GB for
    the VLMs here, runs on CPU, and emits no tokens at all -- so if it is
    accurate it wins on cost by two orders of magnitude.

    Evidence the approach works: the film-grab dataset this harness already uses
    was itself labelled by a DINOv2 classifier, with Claude Opus reviewing the
    low-confidence cases.

    The caveat is the taxonomy. It knows 5 classes and this benchmark asks 7, so
    it can never distinguish `extremeLongShot` from `longShot`. Scoring it
    against the 7-class gold would therefore measure the mismatch, not the
    model. `generate` returns the class name; `--collapse5` in the report maps
    gold and prediction into the 5-class space for every model alike.

    ethz-mtc/shot_scale_classifier-resnet50 looked like a second candidate at
    0.1GB but ships no config.json -- a bare .bin with no id2label, so its
    output indices mean nothing without guessing. Not usable.
    """

    def __init__(self, model_id: str):
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        self.torch = torch
        print(f"  loading classifier {model_id} ...")
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModelForImageClassification.from_pretrained(model_id)
        self.model.eval()
        if torch.cuda.is_available():
            self.model.to("cuda")
        self.id2label = self.model.config.id2label
        print(f"  classes: {list(self.id2label.values())}")
        self.in_tokens = self.out_tokens = self.think_tokens = self.truncated = 0

    def generate(self, images: list[Any], prompt: str) -> tuple[str, dict]:
        """Ignores the prompt -- a classifier has no prompt. Returns its raw
        class name, which only the collapsed scoring path can interpret."""
        if not images:
            # The --no-image control is meaningless here: with no image there is
            # nothing to classify, and returning a constant would fake a score.
            return "", {}
        inputs = self.processor(images=images[0], return_tensors="pt")
        if self.torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits
        return self.id2label[int(logits.argmax(-1).item())], {}

    def cost_usd(self) -> float:
        return 0.0

    def close(self):
        del self.model
        gc.collect()
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


class NvidiaBackend:
    """NVIDIA NIM, OpenAI-compatible REST.

    A third hosted option for open weights, and the cheapest per image measured
    so far: nemotron-3-nano-omni bills 284 input tokens against Gemini's 1141
    and Groq-Qwen's 1303.

    What the catalogue says and what a key can call are different things.
    Probing all 82 ids this key lists, with a real image and a question whose
    answer is checkable ("what colour is this?" on a blue square):

        meta/llama-3.2-11b-vision-instruct       1623 tok  "Blue."
        nvidia/nemotron-3-nano-omni-30b...        284 tok  "Blue"
        nvidia/ising-calibration-1.5-31b          282 tok  "Blue"   (quantum charts)
        four more accepted the payload and returned an empty string
        55 returned 404, 10 said "not a multimodal model"
        meta/llama-3.2-90b-vision-instruct timed out at both 45s and 180s

    Accepting an image is not the same as seeing one -- gpt-oss-20b takes the
    payload here and rejects it on Groq, and answers nothing either way. Only a
    checkable reply proves vision, which is why the probe asked for a colour.

    NIM uses `max_tokens`, not Groq's `max_completion_tokens`, and its endpoints
    cold-start: a first call can 503 with ResourceExhausted and succeed on
    retry, so 503 is treated as retryable rather than fatal.
    """

    ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"

    def __init__(self, model_id: str, max_tokens: int = 16):
        self.key = os.environ.get("NVIDIA_API_KEY", "").strip()
        if not self.key:
            sys.exit("NVIDIA_API_KEY not set (put it in evals/shotbench/.env)")
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.in_tokens = 0
        self.out_tokens = 0
        self.think_tokens = 0
        self.truncated = 0

    def generate(self, images: list[Any], prompt: str) -> tuple[str, dict]:
        import base64
        import io
        import urllib.error
        import urllib.request

        content: list[dict[str, Any]] = []
        for im in images:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=90)
            b64 = base64.b64encode(buf.getvalue()).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        content.append({"type": "text", "text": prompt})

        payload = {"model": self.model_id, "max_tokens": self.max_tokens,
                   "temperature": 0,
                   "messages": [{"role": "user", "content": content}]}

        for attempt in range(6):
            req = urllib.request.Request(
                self.ENDPOINT, data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {self.key}",
                         "Content-Type": "application/json",
                         "Accept": "application/json",
                         "User-Agent": "curl/8.0"})
            try:
                data = json.load(urllib.request.urlopen(req, timeout=180))
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:200]
                # 503 here is usually a cold worker, not a real outage.
                if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                    time.sleep(min(2 ** attempt * 3, 60))
                    continue
                raise RuntimeError(f"nvidia {exc.code}: {body}") from None
            except Exception:
                if attempt < 5:
                    time.sleep(min(2 ** attempt * 3, 60))
                    continue
                raise
        else:
            raise RuntimeError("nvidia: retries exhausted")

        usage = data.get("usage", {}) or {}
        self.in_tokens += usage.get("prompt_tokens", 0)
        self.out_tokens += usage.get("completion_tokens", 0)
        choices = data.get("choices") or []
        text = ((choices[0]["message"].get("content") or "").strip()
                if choices else "")
        if not text:
            self.truncated += 1
        return text, {"in_tokens": usage.get("prompt_tokens", 0),
                      "out_tokens": usage.get("completion_tokens", 0)}

    def cost_usd(self) -> float:
        return 0.0   # free evaluation tier; paid rates not modelled here

    def close(self):
        pass


class GroqBackend:
    """Groq-hosted open models, OpenAI-compatible REST.

    Worth an arm because it is a third deployment shape: the weights are open
    like the local models, but someone else pays for the GPU. If an open model
    served here matches Gemini, the self-hosting break-even calculation
    (~37,800 reels/month before a dedicated GPU beats an API) never has to be
    reached at all.

    Two things about this endpoint are not obvious:

    The default urllib User-Agent gets a bare 403. Any normal UA works, so this
    reads as bot filtering rather than auth -- a key that looks revoked may be
    fine.

    Multimodality is not in the model name. `qwen/qwen3.8-27b` carries no "VL"
    and is not documented here as a vision model, but it accepts image_url
    content and answers correctly; `openai/gpt-oss-120b` and `groq/compound`
    reject it with "content must be a string". Verified by sending an image, not
    by reading names.

    Free-tier limits are the real constraint: 8,000 tokens/minute and 1,000
    requests/day. At ~848 tokens per image that is 9.4 images/minute, so this
    class paces itself from the x-ratelimit headers rather than sleeping a fixed
    amount and hoping.
    """

    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model_id: str, max_completion_tokens: int = 16):
        self.key = os.environ.get("GROQ_API_KEY", "").strip()
        if not self.key:
            sys.exit("GROQ_API_KEY not set (put it in evals/shotbench/.env)")
        self.model_id = model_id
        self.max_completion_tokens = max_completion_tokens
        self.in_tokens = 0
        self.out_tokens = 0
        self.think_tokens = 0
        self.truncated = 0
        self._next_ok = 0.0      # epoch seconds before which we must not send

    def generate(self, images: list[Any], prompt: str) -> tuple[str, dict]:
        import base64
        import io
        import urllib.error
        import urllib.request

        content: list[dict[str, Any]] = []
        for im in images:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=90)
            b64 = base64.b64encode(buf.getvalue()).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        content.append({"type": "text", "text": prompt})

        payload = {
            "model": self.model_id,
            "max_completion_tokens": self.max_completion_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": content}],
        }

        for attempt in range(6):
            wait = self._next_ok - time.time()
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(
                self.ENDPOINT, data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {self.key}",
                         "Content-Type": "application/json",
                         # A bare urllib UA is 403'd. Not auth -- bot filtering.
                         "User-Agent": "curl/8.0"})
            try:
                resp = urllib.request.urlopen(req, timeout=120)
                data = json.load(resp)
                self._pace(dict(resp.headers))
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:200]
                if exc.code == 429 and attempt < 5:
                    # Prefer the server's own number over a guess.
                    retry = exc.headers.get("retry-after")
                    delay = float(retry) if retry and retry.replace(".", "").isdigit() \
                        else min(2 ** attempt * 5, 70)
                    time.sleep(delay)
                    continue
                if exc.code in (500, 502, 503, 504) and attempt < 5:
                    time.sleep(min(2 ** attempt * 2, 45))
                    continue
                raise RuntimeError(f"groq {exc.code}: {body}") from None
        else:
            raise RuntimeError("groq: retries exhausted")

        usage = data.get("usage", {}) or {}
        self.in_tokens += usage.get("prompt_tokens", 0)
        self.out_tokens += usage.get("completion_tokens", 0)
        text = (data["choices"][0]["message"].get("content") or "").strip()
        if not text:
            self.truncated += 1
        return text, {"in_tokens": usage.get("prompt_tokens", 0),
                      "out_tokens": usage.get("completion_tokens", 0)}

    def _pace(self, headers: dict[str, str]) -> None:
        """Hold off if the token bucket is nearly empty.

        Sleeping a fixed interval either wastes quota or trips 429s as the image
        size varies. The remaining-token header is the truth, so spend against it.
        """
        try:
            remaining = float(headers.get("x-ratelimit-remaining-tokens", "1e9"))
            reset = headers.get("x-ratelimit-reset-tokens", "0s")
            secs = float(reset.rstrip("s")) if reset.endswith("s") and \
                reset[:-1].replace(".", "").isdigit() else 0.0
        except (TypeError, ValueError):
            return
        # Below roughly two images' worth, wait for the window to roll over.
        if remaining < 2000:
            self._next_ok = time.time() + max(secs, 1.0)

    def cost_usd(self) -> float:
        return 0.0   # free tier; paid rates differ and are not modelled here

    def close(self):
        pass


def list_gemini_models() -> list[str]:
    import urllib.request

    req = urllib.request.Request(f"{API_ROOT}/models",
                                 headers={"x-goog-api-key": _api_key()})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    out = []
    for m in data.get("models", []):
        name = (m.get("name") or "").replace("models/", "")
        methods = m.get("supportedGenerationMethods") or []
        if not methods or "generateContent" in methods:
            out.append(name)
    return sorted(out)


def resolve_gemini_model(preferred: str | None) -> str:
    """Model ids move. Discover from the API rather than hardcoding a guess."""
    names = list_gemini_models()
    if preferred:
        if preferred in names:
            return preferred
        sys.exit(f"model '{preferred}' not available. Choices:\n  "
                 + "\n  ".join(names))
    for pat in ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3"):
        hits = [n for n in names
                if n.startswith(pat) and not any(
                    x in n for x in ("image", "tts", "audio", "transcribe"))]
        if hits:
            return hits[0]
    sys.exit("could not auto-pick a Gemini model. Run --list-gemini-models.")


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def completed_indices(path: Path) -> set[int]:
    done: set[int] = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                done.add(json.loads(line)["index"])
            except Exception:
                continue  # tolerate a torn final line from an eviction
    return done


def run_model(spec: ModelSpec, items: list[Item], data_dir: Path,
              out_dir: Path, args) -> None:
    # The ablation writes to its own file. Sharing one would poison the real
    # results with rows the model answered blind, and the resume logic would
    # then skip items it never actually saw.
    ds = "" if args.dataset == "shotbench" else f".{args.dataset}"
    suffix = ".noimage" if args.no_image else ""
    out_path = out_dir / f"{spec.key}{ds}{suffix}.jsonl"
    done = completed_indices(out_path)
    todo = [it for it in items if it.index not in done]

    print(f"\n=== {spec.key} ===")
    print(f"  {spec.note}")
    if done:
        print(f"  resuming: {len(done)} done, {len(todo)} remaining")
    if not todo:
        print("  nothing to do")
        return

    if spec.kind == "gemini":
        model_id = resolve_gemini_model(spec.model_id or args.gemini_model)
        effective_model_id = model_id
        print(f"  api model: {model_id}")
        backend: Any = GeminiBackend(
            model_id,
            media_resolution=args.media_resolution,
            thinking_level=args.thinking_level,
            max_output_tokens=args.max_output_tokens,
        )
        rates = pricing_for(model_id)
        print(f"  pricing: ${rates['in']}/M in, ${rates['out']}/M out"
              + ("  (introductory - doubles 2027-01-01)"
                 if rates.get("doubles_2027") else ""))
    elif spec.kind == "classifier":
        preflight_vram(spec)
        effective_model_id = spec.model_id
        backend = ClassifierBackend(spec.model_id)
    elif spec.kind == "nvidia":
        effective_model_id = spec.model_id
        print(f"  nvidia NIM: {spec.model_id}")
        backend = NvidiaBackend(spec.model_id, max_tokens=args.max_new_tokens)
    elif spec.kind == "groq":
        effective_model_id = spec.model_id
        print(f"  groq model: {spec.model_id}  (free tier: 8k tok/min, "
              f"1000 req/day -- paced from the rate-limit headers)")
        backend = GroqBackend(spec.model_id,
                              max_completion_tokens=args.max_new_tokens)
    else:
        preflight_vram(spec)
        effective_model_id = spec.model_id
        backend = HFBackend(spec.model_id, max_new_tokens=args.max_new_tokens)

    t_start = time.time()
    errors = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for n, item in enumerate(todo, 1):
            try:
                # --no-image is the contamination control. The question and its
                # options go to the model with the picture withheld, so anything
                # it scores above chance came from the text, not from seeing.
                #
                # This matters because ShotVL was fine-tuned on ShotQA -- 70k QA
                # pairs built by the same team, same eight dimensions, same
                # taxonomy, same multiple-choice shape as this benchmark. The
                # generalists have never seen that format. A raw score gap
                # therefore measures cinematography skill and exam familiarity
                # mixed together, and only this ablation separates them.
                # RefineShot (arXiv 2510.02423) reports option leakage in
                # ShotBench; this measures how much of it each model exploits.
                images = [] if args.no_image else load_media(
                    item, data_dir, args.video_frames)
                prompt = build_prompt(item)
                t0 = time.time()
                text, meta = backend.generate(images, prompt)
                latency = time.time() - t0
                if isinstance(backend, ClassifierBackend):
                    # A class name, not an option letter. `correct` is left
                    # False here on purpose: only the collapsed scorer can
                    # judge a 5-class prediction against 7-class gold, and
                    # writing a guess into the row would make a wrong number
                    # look authoritative.
                    pred = None
                else:
                    pred = extract_answer(text, item.options)
                rec = {
                    "index": item.index,
                    "model_id": effective_model_id,
                    "category": item.category,
                    "media_type": item.media_type,
                    "gold": item.answer,
                    "pred": pred,
                    "raw": text[:200],
                    "correct": bool(pred and pred == item.answer),
                    "unparsed": pred is None,
                    # Recorded so the report can compute chance per dataset.
                    # ShotBench is 4-option, film-grab 7; a hardcoded 25% called
                    # a below-chance 6.1% "near chance" on the latter.
                    "n_options": len(item.options),
                    "latency_s": round(latency, 3),
                    **meta,
                }
            except Exception as exc:
                errors += 1
                rec = {
                    "index": item.index,
                    "category": item.category,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                    "correct": False,
                    "unparsed": True,
                }
            fh.write(json.dumps(rec) + "\n")
            fh.flush()  # durable against eviction

            if n % 25 == 0 or n == len(todo):
                rate = n / max(time.time() - t_start, 1e-6)
                eta = (len(todo) - n) / max(rate, 1e-9)
                print(f"  {n}/{len(todo)}  {rate:.2f} it/s  eta {eta/60:.1f}m"
                      + (f"  errors={errors}" if errors else ""))

    if isinstance(backend, (GroqBackend, NvidiaBackend)):
        print(f"  tokens in={backend.in_tokens} out={backend.out_tokens} "
              f"cost=$0.0000 (free tier)")
        if backend.truncated:
            print(f"  WARNING: {backend.truncated} replies came back empty.")
    elif isinstance(backend, GeminiBackend):
        share = (100 * backend.think_tokens / backend.out_tokens
                 if backend.out_tokens else 0.0)
        print(f"  tokens in={backend.in_tokens} out={backend.out_tokens} "
              f"(thinking={backend.think_tokens}, {share:.0f}% of output) "
              f"cost=${backend.cost_usd():.4f}")
        if backend.truncated:
            print(f"  WARNING: {backend.truncated} replies hit MAX_TOKENS with no "
                  f"text. Raise --max-output-tokens; thinking is eating the budget.")
    backend.close()


def preflight_vram(spec: ModelSpec) -> None:
    try:
        import torch
    except ImportError:
        return
    if not torch.cuda.is_available():
        print("  WARNING: no CUDA device -- this will be extremely slow on CPU.")
        return
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    name = torch.cuda.get_device_name(0)
    print(f"  gpu: {name} ({total:.1f} GB)")
    if spec.approx_vram_gb and spec.approx_vram_gb > total * 0.92:
        print(f"  WARNING: {spec.key} needs ~{spec.approx_vram_gb} GB at BF16 but "
              f"only {total:.1f} GB is present. Expect OOM; quantise or pick a "
              f"smaller model.")


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

#: Fallback only, for rows written before n_options was recorded. ShotBench is
#: 4-option; anything else must report its own chance level or the verdicts lie.
CHANCE = 25.0


def _report_leakage(table: dict[str, dict[str, Any]], width: int) -> None:
    """Pair each model with its --no-image run and show what sight was worth.

    Reading the columns:

      blind      what the model scores with the picture withheld. At CHANCE it
                 is genuinely guessing. Above it, the question leaks its own
                 answer -- through option wording, priors over which shot sizes
                 are common, or memorised items.
      sighted    the normal score.
      sight      sighted - blind. **This is the honest measure of vision.**
                 A model that scores 83 sighted and 55 blind contributes 28
                 points of actual looking; one that scores 70 sighted and 30
                 blind contributes 40.

    Why it matters here: ShotVL was fine-tuned on ShotQA, built by the same team
    in the same format as this benchmark, while the generalists have never seen
    that format. Raw scores mix skill with exam familiarity. `sight` does not --
    it is each model measured against itself, so format advantage cancels out.
    """
    pairs = [(k, f"{k}.noimage") for k in table
             if not k.endswith(".noimage") and f"{k}.noimage" in table]
    if not pairs:
        return

    def overall(key: str) -> tuple[float, int]:
        vals = [v for lst in table[key]["by_cat"].values() for v in lst]
        return (100 * sum(vals) / len(vals), len(vals)) if vals else (0.0, 0)

    print("\n" + "=" * 100)
    print("CONTAMINATION CONTROL - what the model scores without the image")
    print("=" * 100)
    print("  " + "model".ljust(width) + "blind".rjust(9) + "chance".rjust(9)
          + "sighted".rjust(10) + "sight".rjust(9) + "   verdict")
    for base, blind_key in sorted(pairs):
        b, _ = overall(blind_key)
        s, _ = overall(base)
        chance = table[blind_key].get("chance") or CHANCE
        if b >= s:
            verdict = "BROKEN - sight does not help at all"
        elif b > chance + 20:
            verdict = "severe leakage - answerable from text alone"
        elif b > chance + 10:
            verdict = "notable leakage"
        elif b > chance + 5:
            verdict = "mild leakage"
        elif b < chance - 3:
            verdict = "clean - below chance blind"
        else:
            verdict = "clean - at chance without the image"
        print("  " + base.ljust(width) + f"{b:8.1f}%" + f"{chance:8.1f}%"
              + f"{s:9.1f}%" + f"{s - b:+8.1f}" + f"   {verdict}")
    print("\n  Rank models by 'sight', not by 'sighted' -- sight is each model")
    print("  measured against itself, so an advantage from recognising the")
    print("  question format cancels out. Chance is per-dataset: ShotBench is")
    print("  4-option, the film-grab set 7.")


def report(out_dir: Path) -> None:
    files = sorted(out_dir.glob("*.jsonl"))
    if not files:
        print("no results yet")
        return

    table: dict[str, dict[str, Any]] = {}
    categories: set[str] = set()

    for path in files:
        key = path.stem
        by_cat: dict[str, list[bool]] = {}
        lat: list[float] = []
        unparsed = errs = 0
        tin = tout = tthink = 0
        model_id = ""
        opt_counts: list[int] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if "error" in r:
                    errs += 1
                cat = r.get("category", "?")
                by_cat.setdefault(cat, []).append(bool(r.get("correct")))
                categories.add(cat)
                if r.get("latency_s"):
                    lat.append(r["latency_s"])
                if r.get("unparsed"):
                    unparsed += 1
                if r.get("n_options"):
                    opt_counts.append(r["n_options"])
                tin += r.get("in_tokens", 0)
                # Thinking bills as output; fold it in so cost is not understated.
                tout += r.get("out_tokens", 0) + r.get("think_tokens", 0)
                tthink += r.get("think_tokens", 0)
                if not model_id:
                    model_id = r.get("model_id", "")
        table[key] = {
            "by_cat": by_cat, "lat": lat, "unparsed": unparsed,
            "errors": errs, "in": tin, "out": tout, "think": tthink,
            "model_id": model_id,
            # Chance depends on how many options each item offered, so it is
            # read from the data rather than assumed.
            "chance": (100.0 / (sum(opt_counts) / len(opt_counts))
                       if opt_counts else None),
        }

    ordered = sorted(categories)
    width = max(len(k) for k in table) + 2

    print("\n" + "=" * 100)
    print("ACCURACY BY DIMENSION (%)")
    print("=" * 100)
    header = "model".ljust(width) + "".join(c[:13].rjust(15) for c in ordered) + "overall".rjust(11) + "n".rjust(8)
    print(header)
    print("-" * len(header))

    for key, d in sorted(table.items()):
        cells = ""
        total_ok = total_n = 0
        for cat in ordered:
            vals = d["by_cat"].get(cat, [])
            if vals:
                acc = 100 * sum(vals) / len(vals)
                cells += f"{acc:14.1f} "
                total_ok += sum(vals)
                total_n += len(vals)
            else:
                cells += " " * 15
        overall = 100 * total_ok / total_n if total_n else 0
        print(key.ljust(width) + cells + f"{overall:10.1f} " + f"{total_n:7d}")

    # The metric that actually decides the architecture.
    print("\n" + "=" * 100)
    print(f"DECISION METRIC - {' + '.join(KEY_CATEGORIES)} only")
    print("(the two fields the template depends on; overall average is not the right metric here)")
    print("=" * 100)
    rows = []
    for key, d in table.items():
        ok = n = 0
        for cat in KEY_CATEGORIES:
            vals = d["by_cat"].get(cat, [])
            ok += sum(vals)
            n += len(vals)
        if n:
            rows.append((100 * ok / n, key, n))
    for acc, key, n in sorted(rows, reverse=True):
        print(f"  {key.ljust(width)} {acc:6.1f}%   (n={n})")

    _report_leakage(table, width)

    print("\n" + "=" * 100)
    print("OPERATIONS")
    print("=" * 100)
    print("model".ljust(width) + "med latency".rjust(13) + "unparsed".rjust(10)
          + "errors".rjust(8) + "tok in".rjust(10) + "tok out".rjust(10)
          + "think%".rjust(8) + "$/item".rjust(10) + "$/50 imgs".rjust(11))
    for key, d in sorted(table.items()):
        lat = sorted(d["lat"])
        med = lat[len(lat) // 2] if lat else 0.0
        rates = pricing_for(d.get("model_id") or "")
        n_items = sum(len(v) for v in d["by_cat"].values()) or 1
        if d["in"]:
            cost = d["in"] / 1e6 * rates["in"] + d["out"] / 1e6 * rates["out"]
            per_item = cost / n_items
            think_pct = 100 * d["think"] / d["out"] if d["out"] else 0.0
            tail = (f"{think_pct:7.0f}%" + f"${per_item:9.5f}"
                    + f"${per_item * 50:10.3f}")
        else:
            tail = "      -" + "     local" + "      local"
        print(key.ljust(width) + f"{med:12.2f}s" + f"{d['unparsed']:10d}"
              + f"{d['errors']:8d}" + f"{d['in']:10d}" + f"{d['out']:10d}" + tail)

    print("\n'$/50 imgs' projects one reference-reel analysis (SPEC assumes 40-60")
    print("images per reference). Thinking tokens bill as output and are included.")
    print("\nReference - published ShotBench: ShotVL-7B 70.1 | ShotVL-3B 65.1 | "
          "GPT-4o 59.3 | Gemini-2.5-flash 54.5")
    print("If shotvl-7b lands near 70.1 overall, the harness is calibrated.\n")


# --------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="+", default=None,
                   help=f"model keys, or 'all'. choices: {', '.join(MODELS)}")
    p.add_argument("--data-dir", default="./shotbench_data")
    p.add_argument("--out-dir", default="./results")
    p.add_argument("--limit", type=int, default=None, help="cap items (smoke test)")
    p.add_argument("--categories", nargs="+", default=None,
                   help="restrict to dimensions, e.g. --categories 'shot size' 'shot framing'")
    p.add_argument("--key-only", action="store_true",
                   help=f"shorthand for --categories {KEY_CATEGORIES}")
    p.add_argument("--skip-video", action="store_true",
                   help="images only; skips the 1.2GB videos.tar download")
    p.add_argument("--video-frames", type=int, default=8)
    p.add_argument("--reels-tsv", default="../reels/reels_test.tsv",
                   help="--dataset reels: path to the TSV from "
                        "evals/reels/label.py export")
    p.add_argument("--dataset", default="shotbench",
                   choices=["shotbench", "filmshots", "reels"],
                   help="'filmshots' is the independent check: 863 human-labelled "
                        "frames from film-grab.com, 7 options, chance 14.3%%. "
                        "No model here was tuned on it")
    p.add_argument("--no-image", action="store_true",
                   help="contamination control: withhold the image and ask the "
                        "question anyway. Anything above chance came from the "
                        "text. Writes to <model>.noimage.jsonl")
    p.add_argument("--max-new-tokens", type=int, default=128,
                   help="local HF models only. Was 16 on the assumption that "
                        "local models don't think; Qwen3.5-9B does, and scored "
                        "0.0%% on all 3572 items because of it")
    p.add_argument("--max-output-tokens", type=int, default=512,
                   help="Gemini only. Must leave room for thinking: at 16 the "
                        "reply comes back empty and every item scores 0.")
    p.add_argument("--thinking-level", default=None, choices=["low", "high"],
                   help="Gemini 3 thinking budget; 'low' cuts output tokens")
    p.add_argument("--gemini-model", default=None, help="exact API model id")
    p.add_argument("--media-resolution", default=None,
                   choices=["MEDIA_RESOLUTION_LOW", "MEDIA_RESOLUTION_MEDIUM",
                            "MEDIA_RESOLUTION_HIGH"],
                   help="Gemini token-per-image cap; LOW is the ~6x cost lever")
    p.add_argument("--list-gemini-models", action="store_true")
    p.add_argument("--report", action="store_true", help="score existing results and exit")
    p.add_argument("--env-file", default=None,
                   help="file of KEY=value lines (default: .env beside this script)")
    p.add_argument("--tsv", default=None,
                   help="override the test.tsv path (for running a prepared subset)")
    args = p.parse_args()

    load_env_file(Path(args.env_file) if args.env_file
                  else Path(__file__).resolve().parent / ".env")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.list_gemini_models:
        for name in list_gemini_models():
            rates = pricing_for(name)
            flag = " (introductory - doubles 2027-01-01)" if rates.get("doubles_2027") else ""
            known = name in GEMINI_PRICING or any(
                name.startswith(k) for k in GEMINI_PRICING)
            price = f"  ${rates['in']}/M in, ${rates['out']}/M out{flag}" if known else ""
            print(f"  {name}{price}")
        return

    if args.report:
        report(out_dir)
        return

    if args.key_only:
        args.categories = list(KEY_CATEGORIES)

    keys = args.models or DEFAULT_SET
    if keys == ["all"]:
        keys = DEFAULT_SET
    unknown = [k for k in keys if k not in MODELS]
    if unknown:
        sys.exit(f"unknown model(s): {unknown}. choices: {list(MODELS)}")

    data_dir = Path(args.data_dir)
    if args.dataset == "reels":
        print("Preparing your own labelled reel frames ...")
        items = load_reels(Path(args.reels_tsv), args.limit)
        print(f"  {len(items)} items, 7 options each (chance {100/7:.1f}%)")
    elif args.dataset == "filmshots":
        print("Preparing film-grab shot-scale set (independent of ShotBench) ...")
        items = load_filmshots(data_dir, args.limit)
        print(f"  {len(items)} items, 7 options each (chance {100/7:.1f}%)")
    else:
        if args.tsv:
            # A prepared subset: media assumed already extracted under data_dir.
            tsv = Path(args.tsv)
            if not tsv.exists():
                sys.exit(f"--tsv not found: {tsv}")
            print(f"Using prepared item list: {tsv}")
        else:
            print("Preparing ShotBench ...")
            tsv = ensure_dataset(data_dir, want_videos=not args.skip_video,
                                 want_media=not args.no_image)
        items = load_items(tsv, args.categories, args.limit, args.skip_video)
        print(f"  {len(items)} items"
              + (f" in {args.categories}" if args.categories else "")
              + (" (images only)" if args.skip_video else ""))
    if not items:
        sys.exit("no items matched the filters")

    for key in keys:
        try:
            run_model(MODELS[key], items, data_dir, out_dir, args)
        except KeyboardInterrupt:
            print("\ninterrupted; progress is saved, re-run to resume")
            break
        except SystemExit:
            raise
        except Exception as exc:
            print(f"  {key} FAILED: {type(exc).__name__}: {exc}")
            print("  continuing with the next model")

    report(out_dir)


if __name__ == "__main__":
    main()
