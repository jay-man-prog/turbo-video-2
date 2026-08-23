"""Local-only planning and defaults for the R&H Essendon simple workflow."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import random
import threading
from pathlib import Path

from app.utils import utils

_MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a"}
_music_selection_lock = threading.Lock()


def eligible_music_tracks(song_dir: str | None = None) -> list[str]:
    """Return decodable, non-hidden audio files directly under resource/songs."""
    directory = Path(song_dir or utils.song_dir())
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    tracks = []
    for entry in entries:
        if not entry.is_file() or entry.name.startswith((".", "~")):
            continue
        if entry.suffix.lower() not in _MUSIC_EXTENSIONS:
            continue
        try:
            from moviepy import AudioFileClip
            clip = AudioFileClip(str(entry))
            valid = bool(clip.duration and clip.duration > 0)
            clip.close()
        except Exception:
            valid = False
        if valid:
            tracks.append(entry.name)
    return sorted(tracks, key=str.lower)


def select_music_track(task_id: str, selector=random.choice) -> tuple[str, str]:
    """Choose one top-level R&H track once per task, avoiding immediate repeats."""
    tracks = eligible_music_tracks()
    if not tracks:
        return "", "No usable R&H music tracks were found in resource/songs. The video will be generated without background music."
    marker = Path(utils.storage_dir("rh-music", create=True)) / "last-selected.txt"
    with _music_selection_lock:
        try:
            previous = marker.read_text(encoding="utf-8").strip()
        except OSError:
            previous = ""
        candidates = [track for track in tracks if track != previous] or tracks
        selected = selector(candidates)
        try:
            marker.write_text(selected, encoding="utf-8")
        except OSError:
            pass
    return selected, ""
import re


CONTENT_TYPES = (
    "Seller Tip",
    "Buyer Tip",
    "Landlord Tip",
    "Market Update",
    "Just Listed",
    "Just Sold",
    "General Property Advice",
)

RH_SIMPLE_SYSTEM_PROMPT = """
You write short social-video scripts for Raine & Horne Essendon in natural Australian English.
Sound warm, bright, positive and animated, with a lively professional rhythm. Write one cohesive script with a confident hook, natural contractions, varied sentence rhythm and comfortable conversational pauses. Emphasise the practical advice through precise phrasing, not shouting. Do not create a stiff list-reading cadence or force slang, hype, pressure, clichés or generic marketing language. End with a natural call to action suited to sellers, buyers or landlords. Avoid excessive exclamation marks, fake enthusiasm and a sales-announcer voice. Never invent market statistics, property facts, results, legal claims or suburb data. For a market update, use only facts supplied in the brief. Do not narrate a phone number: contact details appear only on the closing card. Return only the spoken script, with no headings or markdown.
""".strip()


@dataclass(frozen=True)
class VisualBeat:
    sentence: str
    query: str
    fallback_query: str
    duration: float


def simple_script_prompt(content_type: str, target_seconds: int, extra_facts: str) -> str:
    facts = (extra_facts or "").strip()
    market_guard = (
        "This is a market update: include no market fact unless it is in the supplied facts."
        if content_type == "Market Update"
        else ""
    )
    return "\n".join(
        item
        for item in (
            RH_SIMPLE_SYSTEM_PROMPT,
            f"Content type: {content_type}.",
            f"Target spoken length: about { {20: '45–52', 30: '65–75', 45: '95–110', 60: '125–145'}.get(target_seconds, '45–52') } words.",
            market_guard,
            f"Supplied facts/instructions: {facts or 'None. Do not invent any.'}",
        )
        if item
    )


def split_script_into_beats(script: str) -> list[str]:
    """Split narration into natural, ordered visual beats without an LLM call."""
    cleaned = re.sub(r"\s+", " ", script or "").strip()
    if not cleaned:
        return []
    beats = [part.strip(" -–—") for part in re.split(r"(?<=[.!?])\s+", cleaned)]
    return [beat for beat in beats if beat]


def _keywords(sentence: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", sentence.lower())
    ignored = {"this", "that", "with", "from", "your", "about", "there", "their", "they", "have", "will", "into", "when", "than", "then", "just", "really", "more", "what", "which"}
    return [word for word in words if word not in ignored][:7]


def plan_visual_beats(script: str, content_type: str = "General Property Advice") -> list[VisualBeat]:
    """Create one precise English Pexels query and a property-safe fallback per beat."""
    fallback_by_type = {
        "Seller Tip": "Australian homeowner preparing house for sale",
        "Buyer Tip": "Australian couple inspecting modern home",
        "Landlord Tip": "landlord inspecting clean rental property",
        "Market Update": "Australian suburban residential street homes",
        "Just Listed": "bright modern home exterior and garden",
        "Just Sold": "home sold sign suburban house exterior",
    }
    fallback = fallback_by_type.get(content_type, "Australian residential home interior lifestyle")
    beats = []
    for sentence in split_script_into_beats(script):
        keywords = " ".join(_keywords(sentence))
        query = f"Australian residential property {keywords}".strip()
        word_count = max(1, len(_keywords(sentence)))
        duration = min(4.0, max(2.0, word_count / 2.4))
        beats.append(VisualBeat(sentence, query, fallback, duration))
    return beats


def visual_terms(beats: list[VisualBeat]) -> list[dict[str, object]]:
    return [
        {"query": beat.query, "fallback_query": beat.fallback_query, "duration": beat.duration}
        for beat in beats
    ]


def allocate_beat_durations(beats: list[dict], audio_duration: float) -> list[float]:
    """Allocate the finished voice duration proportionally, retaining calm cuts."""
    if not beats or audio_duration <= 0:
        return []
    words = [max(1, len(re.findall(r"[A-Za-z][A-Za-z'-]+", str(b.get("narration", ""))))) for b in beats]
    total = sum(words)
    return [max(2.0, min(8.0, audio_duration * count / total)) for count in words]


def generate_semantic_visual_plan(script: str, content_type: str, target_seconds: int) -> list[dict]:
    """Ask the configured LLM for an editable, structured visual plan.

    Any malformed/failed response uses the deterministic planner; this function
    never makes a stock-media request itself.
    """
    target_beats = {20: "3 to 4", 30: "4 to 6", 45: "6 to 8", 60: "8 to 10"}.get(target_seconds, "3 to 4")
    prompt = f'''Return JSON only: an array of {target_beats} visual beats for this real-estate narration.
Each item must have narration, query, alternates (exactly two strings), fallback, duration.
The narration must quote the exact contiguous words it supports. Queries must be concise English Pexels searches with visible subject, action and setting (3–7 useful words). Do not use abstract words, marketing terms, generic city, office, construction, cooking, skyline or overseas-street imagery. Prefer residential interiors, gardens, inspections, home preparation and suburban lifestyle. Preserve narration order.
Content type: {content_type}
Script: {script}'''
    try:
        from app.services import llm
        response = llm._generate_response(prompt)
        data = json.loads(llm._strip_code_fence(response))
        if not isinstance(data, list) or not data:
            raise ValueError("scene plan is not a non-empty array")
        plan = []
        for item in data:
            alternates = item.get("alternates", []) if isinstance(item, dict) else []
            if not isinstance(alternates, list) or len(alternates) != 2:
                raise ValueError("scene plan alternates are invalid")
            query = str(item.get("query", "")).strip()
            narration = str(item.get("narration", "")).strip()
            fallback = str(item.get("fallback", "Australian residential home interior")).strip()
            if not narration or not query or not all(str(value).strip() for value in alternates):
                raise ValueError("scene plan fields are incomplete")
            plan.append({"narration": narration, "query": query, "alternates": [str(value).strip() for value in alternates], "fallback_query": fallback, "duration": float(item.get("duration", 3))})
        return plan
    except Exception:
        return [
            {"narration": beat.sentence, "query": beat.query, "alternates": [], "fallback_query": beat.fallback_query, "duration": beat.duration}
            for beat in plan_visual_beats(script, content_type)
        ]
