"""Single source of truth for structured tape quantity/breakdown extraction.

ponytail: heuristic over free text. Upgrade path: once the shop uses a structured
order form, replace ``parse_tapes_deterministic`` with field-driven parsing and keep
``build_tape_columns`` as the only write gate.
"""

import json
import re
from dataclasses import dataclass
from typing import NamedTuple

from src.models.order import TapeItem

# Medium/stock words that can be preceded by a count. Regex is built from this
# constants tuple so there is only one list of units in the codebase.
TAPE_UNITS = (
    "bang",
    "cuon",
    "phoi",
    "dia",
    "ud",
    "ur",
    "hf",
    "sony",
    "maxell",
    "tdk",
    "cd",
)

_UNIT_ALT = "|".join(TAPE_UNITS)
_NUMBER_UNIT_RE = re.compile(rf"(\d+)\s*({_UNIT_ALT})\b")
_PAREN_RE = re.compile(r"\(([^)]*)\)")
_TRACK_RE = re.compile(r"^\d+\s+\S")


@dataclass(frozen=True)
class TapeBreakdown:
    """Deterministic tape quantity plus per-medium breakdown."""

    quantity: int
    tapes: list[TapeItem]


class TapeColumns(NamedTuple):
    """The four derived order columns, written together or not at all."""

    quantity: int
    tapes_json: str
    genres_json: str
    artists_json: str


def _clean_label(text: str) -> str:
    """Lowercase, unaccent, collapse spaces and strip punctuation from a label."""
    from src.db.connection import remove_accents  # local import avoids import cycle

    label = remove_accents(text)
    label = re.sub(r"\s+", " ", label)
    return label.strip(" .,;:()[]-")


# Generic medium words: on their own they say nothing about which phôi to take.
_GENERIC_UNITS = {"bang", "cuon", "phoi", "dia"}
# Brand/medium words that actually identify the phôi.
_SPECIFIC_UNITS = tuple(u for u in TAPE_UNITS if u not in _GENERIC_UNITS)
_SPECIFIC_RE = re.compile(rf"(?:{'|'.join(_SPECIFIC_UNITS)})", re.IGNORECASE)

UNKNOWN_TAPE_LABEL = "khong ro"


def _derive_label(unit: str, full_text: str) -> str:
    """Label must describe the phôi, never the artist/content that follows it.

    ``"3 cuốn Thanh Tuyền"`` means 3 tapes of an unnamed medium -> ``khong ro``.
    ``"6 băng maxell 90p"`` names a real medium -> ``maxell 90p``.
    """
    if unit not in _GENERIC_UNITS:
        label = _clean_label(full_text[full_text.find(unit) :]) if unit in full_text else unit
        return label or unit

    specific = _SPECIFIC_RE.search(full_text)
    if not specific:
        return UNKNOWN_TAPE_LABEL
    label = _clean_label(full_text[specific.start() :])
    return label or UNKNOWN_TAPE_LABEL


def _split_entries(text: str) -> list[str]:
    return [e.strip() for e in text.split(",") if e.strip()]


def parse_tapes_deterministic(items_text: str | None) -> TapeBreakdown:
    """Derive tape quantity and breakdown from free-text ``items_text``.

    Rule order (DESIGN 261026-tpe):
    1. Parenthesised ``<N> <unit>`` spec wins (phôi for the tapes already listed).
    2. Otherwise sum every ``<N> <unit>``, grouping by label.
    3. Otherwise, if every comma entry is track-numbered, 1 tape per entry.
    4. Otherwise 1 tape per comma entry, minimum 1 for non-empty text.
    """
    from src.db.connection import remove_accents  # local import avoids import cycle

    clean = remove_accents(items_text or "")
    if not clean.strip():
        return TapeBreakdown(0, [])

    # Rule 1: last parenthesised group carrying "<N> <unit>" wins.
    for group in reversed(_PAREN_RE.findall(clean)):
        match = _NUMBER_UNIT_RE.search(group)
        if match:
            qty = int(match.group(1))
            label = _derive_label(match.group(2), group)
            return TapeBreakdown(qty, [TapeItem(label=label, qty=qty)])

    # Rule 2: sum every "<N> <unit>", accumulating per label.
    grouped: dict[str, int] = {}
    order: list[str] = []
    for entry in _split_entries(clean):
        match = _NUMBER_UNIT_RE.search(entry)
        if not match:
            continue
        qty = int(match.group(1))
        label = _derive_label(match.group(2), entry)
        if label not in grouped:
            order.append(label)
            grouped[label] = 0
        grouped[label] += qty

    if grouped:
        tapes = [TapeItem(label=label, qty=grouped[label]) for label in order]
        return TapeBreakdown(sum(t.qty for t in tapes), tapes)

    entries = _split_entries(clean)

    # Rule 3: every entry is track-numbered ("1 Chế Linh, 2 Tuấn Vũ") -> 1 tape each.
    if entries and all(_TRACK_RE.match(e) for e in entries):
        tapes = [
            TapeItem(label=_clean_label(re.sub(r"^\d+\s+", "", e)) or "bang", qty=1)
            for e in entries
        ]
        return TapeBreakdown(len(tapes), tapes)

    # Rule 4: one tape per entry, minimum 1 for non-empty text.
    if not entries:
        entries = [clean.strip()]
    tapes = [TapeItem(label=_clean_label(e) or "bang", qty=1) for e in entries]
    return TapeBreakdown(len(tapes), tapes)


def _normalize_names(values: list[str] | None, *, lower: bool) -> list[str]:
    """Trim, optionally lowercase, drop empties, and dedupe case-insensitively.

    The first spelling and position win so "Chế Linh" is preserved verbatim
    while a later "chế linh" is dropped as a duplicate.
    """
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        if not isinstance(value, str):
            continue
        name = value.strip()
        if lower:
            name = name.lower()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def build_tape_columns(
    items_text: str | None,
    llm_tapes: list | None,
    llm_genres: list[str] | None,
    llm_artists: list[str] | None = None,
) -> TapeColumns:
    """Compute the four DB values from one source, enforcing the invariant.

    LLM-provided totals are never trusted: any ``tape_quantity`` field is ignored
    and the total is always ``sum(t.qty for t in tapes)``.
    """
    tapes: list[TapeItem] = []
    for item in llm_tapes or []:
        try:
            tape = TapeItem.model_validate(item)
        except Exception:
            continue
        # Lowercase labels so "MaxellLN90p" and "maxell 90p" group as the same phôi.
        label = " ".join(tape.label.strip().lower().split())
        if not label or tape.qty < 1:
            continue
        tapes.append(TapeItem(label=label, qty=tape.qty))

    if not tapes:
        tapes = list(parse_tapes_deterministic(items_text).tapes)

    quantity = sum(t.qty for t in tapes)
    assert quantity == sum(t.qty for t in tapes)

    genres = _normalize_names(llm_genres, lower=True)
    artists = _normalize_names(llm_artists, lower=False)

    return TapeColumns(
        quantity=quantity,
        tapes_json=json.dumps([t.model_dump() for t in tapes], ensure_ascii=False),
        genres_json=json.dumps(genres, ensure_ascii=False),
        artists_json=json.dumps(artists, ensure_ascii=False),
    )


def format_tape_summary(tape_quantity: int | None, tapes: list[TapeItem]) -> str:
    """Human-readable tape summary; ``None`` renders as ``—`` for legacy rows."""
    if tape_quantity is None:
        return "—"
    summary = f"{tape_quantity} cuốn"
    if tapes:
        breakdown = ", ".join(f"{t.label} ×{t.qty}" for t in tapes)
        summary = f"{summary} ({breakdown})"
    return summary


def format_artist_summary(artists: list[str]) -> str:
    """Comma-joined artist names, or ``—`` when the order carries none."""
    return ", ".join(artists) if artists else "—"
