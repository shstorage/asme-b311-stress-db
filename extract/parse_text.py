"""Coordinate-based text parser for ASME B31.1 Allowable Stress Table pages.

Strategy:
- Part A: group words by y-row, classify by x-position and token format.
- Part B: detect temperature column x-centers from header, map values to temps.
- Italic (creep) detection: overlap with precomputed italic span bboxes.
"""
import json
import re
from pathlib import Path

import fitz

from .config import PDF_PATH, ITALIC_DIR, TABLE_RANGES

_DECIMAL_RE = re.compile(r"^\d+\.\d{2}$")        # e.g. 1.00, 0.85
_INTEGER_RE = re.compile(r"^\d+$")                # e.g. 48, 60
_NOTES_RE   = re.compile(r"^\(\d+\)$")            # e.g. (1), (22)
_FLOAT_RE   = re.compile(r"^\d+\.?\d*$")          # any number

_PAGE_MARKER_RE = re.compile(r"^[ðÞ]")  # only filter ð22Þ style revision markers


def _open_page_words(pdf_page: int) -> list[tuple]:
    """Return words as (x0, y0, x1, y1, text) from PDF page (1-indexed)."""
    doc = fitz.open(PDF_PATH)
    words = doc[pdf_page - 1].get_text("words")
    doc.close()
    return words


def _load_italic_bboxes(pdf_page: int) -> list[list[float]]:
    path = ITALIC_DIR / f"p{pdf_page:03d}_italics.json"
    if not path.exists():
        return []
    return [s["bbox"] for s in json.loads(path.read_text())]


def _group_by_row(words: list, y_tol: float = 2.5) -> list[list[tuple]]:
    """Group (x0, y0, x1, y1, text) words into rows by y0, sorted by x0."""
    rows: dict[float, list] = {}
    for w in words:
        x0, y0, x1, y1, text = w[:5]
        text = text.strip()
        if not text or _PAGE_MARKER_RE.match(text):
            continue
        # Find existing row within y_tol
        matched = None
        for ry in rows:
            if abs(ry - y0) <= y_tol:
                matched = ry
                break
        if matched is None:
            rows[y0] = []
            matched = y0
        rows[matched].append((x0, x1, y0, y1, text))
    return [sorted(row, key=lambda w: w[0]) for _, row in sorted(rows.items())]


def _is_creep(x0: float, y0: float, x1: float, y1: float, italic_bboxes: list) -> bool:
    """Check if a word's bbox overlaps with any italic span."""
    for ib in italic_bboxes:
        ix0, iy0, ix1, iy1 = ib
        if x0 < ix1 and x1 > ix0 and y0 < iy1 and y1 > iy0:
            return True
    return False


# ─── Part A ──────────────────────────────────────────────────────────────────

# X-position thresholds for Part A columns (calibrated from multiple tables).
# These are approximate — the "right-anchored" logic handles tensile/yield/ef.
_A_SPEC_X    = (50,   90)   # spec_no (A53 at x≈54, B161 at x≈60)
_A_GRADE_X   = (90,  152)   # grade / UNS alloy no. (A at x≈105, N02200 at x≈94)
_A_TYPE_X    = (152, 198)   # type or class / temper (S at x≈156, Annealed at x≈132-145)
_A_COMP_X    = (198, 283)   # nominal composition (C-Mn at x≈219, Ni at x≈198)
_A_PNO_X     = (283, 355)   # P-No. (1 at x≈292, 8 at x≈310, 41 at x≈354)
_A_NOTES_X   = (283, 435)   # Notes parenthesized tokens (x≈321-400)


def _classify_part_a_token(x: float, text: str) -> str:
    """Return column label for a token in Part A, based on x position."""
    # Notes take priority if token is parenthesized
    if _A_NOTES_X[0] <= x < _A_NOTES_X[1] and _NOTES_RE.match(text):
        return "notes"
    if _A_SPEC_X[0] <= x < _A_SPEC_X[1]:
        return "spec_no"
    if _A_GRADE_X[0] <= x < _A_GRADE_X[1]:
        return "grade"
    if _A_TYPE_X[0] <= x < _A_TYPE_X[1]:
        return "type_or_class"
    if _A_COMP_X[0] <= x < _A_COMP_X[1]:
        return "nominal_comp"
    if _A_PNO_X[0] <= x < _A_PNO_X[1]:
        return "p_no"
    return "other"


def parse_part_a(pdf_page: int, table_key: str) -> list[dict]:
    """Parse Part A (material spec) page."""
    info = TABLE_RANGES[table_key]
    no_ef    = info.get("no_ef", False)
    ef_on_b  = info.get("ef_on_partb", False)
    has_ef   = not (no_ef or ef_on_b)

    words = _open_page_words(pdf_page)
    all_rows = _group_by_row(words)

    # "ksi" appears ONLY in the column header rows (tensile/yield labels),
    # never in actual data rows, making it a safe header-boundary detector.
    header_y_max = 100.0
    for row in all_rows:
        if any(w[4].lower() == "ksi" for w in row):
            row_y = row[0][2]
            if row_y > header_y_max:
                header_y_max = row_y
    data_rows = [row for row in all_rows if row[0][2] > header_y_max + 1]

    last_spec_no: str | None = None
    last_section: str | None = None
    result: list[dict] = []

    for row in data_rows:
        # row: list of (x0, x1, y0, y1, text)
        tokens  = [w[4] for w in row]
        xs      = [w[0] for w in row]

        if not tokens:
            continue

        # ── Detect section header ──
        # A section header has NO numeric values anywhere in the row.
        # Data rows always have at least one number (tensile, yield, or ef_factor).
        has_any_number = any(
            _DECIMAL_RE.match(t) or _INTEGER_RE.match(t)
            for t in tokens
        )
        if not has_any_number:
            if all(t == "…" for t in tokens):
                continue  # skip "…" only rows
            last_section = " ".join(t for t in tokens if t != "…")
            continue

        # ── Extract right-anchored numeric fields ──
        # Work from right to left: ef_factor (decimal), min_yield, min_tensile
        row_rev = list(zip(xs, tokens))  # [(x, text), ...]

        ef_factor   : float | None = None
        min_yield   : float | None = None
        min_tensile : float | None = None

        # ef_factor: rightmost decimal (only if table has ef in Part A)
        if has_ef and _DECIMAL_RE.match(row_rev[-1][1]):
            ef_factor = float(row_rev.pop()[1])

        # min_yield: next integer from right (x > 400)
        if row_rev and _INTEGER_RE.match(row_rev[-1][1]) and row_rev[-1][0] > 380:
            min_yield = float(row_rev.pop()[1])

        # min_tensile: next integer from right (x > 350)
        if row_rev and _INTEGER_RE.match(row_rev[-1][1]) and row_rev[-1][0] > 350:
            min_tensile = float(row_rev.pop()[1])

        # ── Parse left-side metadata ──
        cols: dict[str, list[str]] = {
            "spec_no": [], "grade": [], "type_or_class": [],
            "nominal_comp": [], "p_no": [], "notes": [],
        }
        for x, text in row_rev:
            if text == "…":
                continue  # inherited from above
            label = _classify_part_a_token(x, text)
            if label != "other":
                cols[label].append(text)

        def _join(lst: list[str]) -> str | None:
            v = " ".join(lst).strip()
            return v if v else None

        spec_no = _join(cols["spec_no"])
        if spec_no:
            last_spec_no = spec_no

        result.append({
            "section":       last_section,
            "spec_no":       spec_no,
            "grade":         _join(cols["grade"]),
            "type_or_class": _join(cols["type_or_class"]),
            "nominal_comp":  _join(cols["nominal_comp"]),
            "p_no":          _join(cols["p_no"]),
            "notes":         _join(cols["notes"]),
            "min_tensile_ksi": min_tensile,
            "min_yield_ksi":   min_yield,
            "ef_factor":       ef_factor,
        })

    return result


# ─── Part B ──────────────────────────────────────────────────────────────────

def _detect_temp_columns(words: list, temps: list[int]) -> tuple[dict[int, float], float]:
    """
    Detect x-centers of temperature columns from the header row.
    Returns ({temp_f: x_center}, header_y_max).
    header_y_max is the y0 of the last detected temperature label row.
    """
    temp_strs: dict[str, int] = {str(t): t for t in temps}
    for t in temps:
        temp_strs[f"{t:,}"] = t

    temp_x: dict[int, float] = {}
    header_y: float = 0.0

    for w in words:
        x, y, _, _, text = w[:5]
        if text in temp_strs:
            temp_x[temp_strs[text]] = x
            if y > header_y:
                header_y = y

    return temp_x, header_y


def parse_part_b(pdf_page: int, table_key: str) -> list[dict]:
    """Parse Part B (stress values) page."""
    info     = TABLE_RANGES[table_key]
    temps    = info["temps"]
    ef_on_b  = info.get("ef_on_partb", False)

    words         = _open_page_words(pdf_page)
    italic_bboxes = _load_italic_bboxes(pdf_page)
    temp_x, header_y = _detect_temp_columns(words, temps)

    if len(temp_x) < len(temps) * 0.7:
        # Fallback: distribute evenly based on first/last detected column
        detected = sorted(temp_x.items(), key=lambda kv: kv[1])
        if len(detected) >= 2:
            x_min = detected[0][1]
            x_max = detected[-1][1]
            step = (x_max - x_min) / (len(temps) - 1)
            temp_x = {t: x_min + i * step for i, t in enumerate(temps)}
            header_y = max(header_y, x_min)  # rough approximation

    # Build a sorted list of (temp, x_center) for nearest-neighbor assignment
    temp_sorted = sorted(temp_x.items(), key=lambda kv: kv[1])

    # For A-8: E/F column is leftmost; estimate its x from first data row
    ef_x_max: float | None = None
    if ef_on_b and temp_sorted:
        ef_x_max = temp_sorted[0][1] - 10  # just left of the first temp column

    # X boundary for grade and spec_no at the right
    grade_x_min = temp_sorted[-1][1] + 20 if temp_sorted else 450
    spec_x_min  = grade_x_min + 40

    all_rows    = _group_by_row(words)
    # Only process rows below the temperature header row
    data_rows   = [row for row in all_rows if row[0][2] > header_y + 1]

    last_section: str | None = None
    result: list[dict] = []

    for row in data_rows:
        tokens = [w[4] for w in row]
        xs     = [w[0] for w in row]

        if not tokens:
            continue

        # Detect section header: first token is on the right side
        # (section headers in Part B are on the right half of the page)
        first_x = xs[0]
        if first_x > grade_x_min - 20 and not _FLOAT_RE.match(tokens[0]):
            last_section = " ".join(tokens)
            continue

        # Skip rows with only non-numeric content in the temperature area
        temp_area_tokens = [
            t for x, t in zip(xs, tokens)
            if x < grade_x_min
        ]
        if not any(_FLOAT_RE.match(t) or t == "…" for t in temp_area_tokens):
            # Might still be a header; skip
            continue

        # ── Assign values to temperature columns ──
        stress_values: dict[int, float | None] = {t: None for t in temps}
        ef_factor: float | None = None
        grade_hint: str | None = None
        spec_no_hint: str | None = None

        for x, y0, _, y1, text in [(w[0], w[2], w[1], w[3], w[4]) for w in row]:
            # E/F column (A-8 only)
            if ef_on_b and ef_x_max and x < ef_x_max:
                if _DECIMAL_RE.match(text):
                    ef_factor = float(text)
                continue

            # Grade column
            if x >= grade_x_min and x < spec_x_min:
                if text != "…":
                    grade_hint = (grade_hint + " " + text).strip() if grade_hint else text
                continue

            # Spec.No. column
            if x >= spec_x_min:
                if text != "…":
                    spec_no_hint = (spec_no_hint + " " + text).strip() if spec_no_hint else text
                continue

            # Temperature value
            if _FLOAT_RE.match(text) or text == "…":
                # Assign to nearest temperature column
                nearest_temp = min(temp_sorted, key=lambda kv: abs(kv[1] - x))[0]
                if text == "…":
                    stress_values[nearest_temp] = None
                else:
                    val = float(text)
                    # Creep check using word bbox
                    w_obj = next((w for w in row if abs(w[0] - x) < 1), None)
                    if w_obj:
                        creep = _is_creep(w_obj[0], w_obj[2], w_obj[1], w_obj[3], italic_bboxes)
                    else:
                        creep = False
                    # Store as (value, is_creep) tuple
                    stress_values[nearest_temp] = (val, creep)

        stresses = []
        for t in temps:
            v = stress_values.get(t)
            if v is None:
                stresses.append({"temp_f": t, "stress_ksi": None, "is_creep": False})
            else:
                stresses.append({"temp_f": t, "stress_ksi": v[0], "is_creep": v[1]})

        result.append({
            "grade_hint":   grade_hint,
            "spec_no_hint": spec_no_hint,
            "ef_factor":    ef_factor,
            "stresses":     stresses,
        })

    return result
