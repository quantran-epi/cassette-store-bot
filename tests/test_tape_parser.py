import json

import pytest

from src.models.order import TapeItem
from src.services.tape_parser import (
    build_tape_columns,
    format_tape_summary,
    parse_tapes_deterministic,
)

# Real items_text strings from cassette_store.db (DESIGN 261026-tpe).
REAL_CASES = [
    (
        "1 Lk Tuấn Vũ, 2 Chế Linh Làng Văn, 3 Ngày còn Em bên tôi, 4 Ai khổ vì ai, "
        "5 Chế Linh nhạc yêu cầu, 6 Giao Linh Tuấn vũ Đôi mắt người xưa, 6 sony 90p",
        6,
    ),
    ("Khánh ly (hạ trắng), Duy khánh (mưa trên phố huế), Thanh thuý, 3 ud xám 90p", 3),
    ("cd thói đời, băng MaxellLN90p (1 băng)", 1),
    # Parenthesised spec wins: phôi for the listed tapes, not extra. 6, not 11.
    ("1 Ngọc Sơn vol1, 5 Băng ca sĩ khác nhạc hải ngoại (6 sony 90p)", 6),
    (
        "Tuấn Vũ, Thanh Tuyền, boney79, Tuấn vũ, chế Linh, "
        "tiếng hát Sơn Tuyền (Chọn cho chủ đề hay là được), 6 băng maxell 90p",
        6,
    ),
    ("1 băng như ảnh ko dán tem", 1),
]


@pytest.mark.parametrize("items_text,expected", REAL_CASES)
def test_parse_real_items_text(items_text, expected):
    result = parse_tapes_deterministic(items_text)
    assert result.quantity == expected
    assert sum(t.qty for t in result.tapes) == result.quantity


@pytest.mark.parametrize("items_text,expected", REAL_CASES)
def test_invariant_holds_for_real_cases(items_text, expected):  # noqa: ARG001
    """tape_quantity must always equal sum of per-tape qty."""
    result = parse_tapes_deterministic(items_text)
    assert result.quantity == sum(t.qty for t in result.tapes)


def test_parse_empty_returns_zero():
    result = parse_tapes_deterministic("")
    assert result.quantity == 0
    assert result.tapes == []
    assert parse_tapes_deterministic(None).quantity == 0
    assert parse_tapes_deterministic("   ").quantity == 0


def test_parse_no_digits_counts_comma_entries():
    assert parse_tapes_deterministic("Tuấn Vũ, Chế Linh").quantity == 2


def test_parse_track_numbering_one_per_entry():
    assert parse_tapes_deterministic("1 Chế Linh, 2 Tuấn Vũ, 3 Duy Khánh").quantity == 3


def test_parse_label_is_medium_never_artist_or_content():
    """A bare medium word must not turn the artist/content into the phôi label."""
    artist = parse_tapes_deterministic("3 cuốn Thanh Tuyền")
    assert artist.tapes[0].label == "khong ro"

    filler = parse_tapes_deterministic("1 băng như ảnh ko dán tem")
    assert filler.tapes[0].label == "khong ro"

    # A real medium is kept, even when prefixed by a generic word.
    assert parse_tapes_deterministic("6 băng maxell 90p").tapes[0].label == "maxell 90p"
    assert parse_tapes_deterministic("3 ud xám 90p").tapes[0].label == "ud xam 90p"


def test_build_tape_columns_ignores_llm_total_and_uses_sum():
    """LLM tape_quantity=99 with tapes summing to 6 -> stored 6.

    ExtractedOrder schema coverage lives in test_extractor.py (Task 2); here the
    raw LLM payload is passed straight to the helper.
    """
    llm_payload = {
        "customer_phone": "0912345678",
        "items_text": "6 sony 90p",
        "tape_quantity": 99,
        "tapes": [{"label": "sony 90p", "qty": 6}],
        "tape_genres": ["nhạc vàng"],
    }

    cols = build_tape_columns(
        llm_payload["items_text"],
        llm_payload["tapes"],
        llm_payload["tape_genres"],
        llm_payload.get("tape_artists"),
    )
    assert cols.quantity == 6
    assert "sony 90p" in cols.tapes_json
    assert "nhạc vàng" in cols.genres_json


def test_build_tape_columns_falls_back_when_llm_returns_no_tapes():
    cols = build_tape_columns("3 ud xám 90p", [], [])
    assert cols.quantity == 3
    assert "ud" in cols.tapes_json


def test_build_tape_columns_drops_empty_labels_and_bad_qty():
    cols = build_tape_columns(
        "2 băng", [{"label": "  ", "qty": 2}, {"label": "sony", "qty": 0}], []
    )
    # Both invalid -> deterministic fallback over "2 băng".
    assert cols.quantity == 2


def test_build_tape_columns_dedupes_artists_case_insensitively():
    cols = build_tape_columns(
        "2 băng sony 90p",
        [{"label": "sony 90p", "qty": 2}],
        ["nhạc vàng"],
        ["Chế Linh", "chế linh", " Thanh Tuyền ", ""],
    )
    assert json.loads(cols.artists_json) == ["Chế Linh", "Thanh Tuyền"]
    assert json.loads(cols.genres_json) == ["nhạc vàng"]


def test_format_tape_summary_none_renders_dash():
    assert format_tape_summary(None, []) == "—"


def test_format_tape_summary_with_breakdown():
    summary = format_tape_summary(6, [TapeItem(label="sony 90p", qty=6)])
    assert "6 cuốn" in summary
    assert "sony 90p" in summary
