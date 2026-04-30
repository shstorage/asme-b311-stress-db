"""Merge Part A + Part B for every table pair and save to data/merged/.

Now uses parse_text.py directly (no VLM required).
"""
import argparse
import json
import sys

from tqdm import tqdm

from .config import MERGED_DIR, TABLE_RANGES
from .parse_text import parse_part_a, parse_part_b


def _merge_pair(
    table_key: str,
    a_page: int,
    b_page: int,
    prev_spec_no: str | None,
    prev_section: str | None,
) -> tuple[list[dict], str | None, str | None]:
    info    = TABLE_RANGES[table_key]
    no_ef   = info.get("no_ef", False)
    ef_on_b = info.get("ef_on_partb", False)

    rows_a = parse_part_a(a_page, table_key)
    rows_b = parse_part_b(b_page, table_key)

    if abs(len(rows_a) - len(rows_b)) > 3:
        print(
            f"  WARNING: Row count mismatch at pair ({a_page},{b_page}): "
            f"Part A={len(rows_a)}, Part B={len(rows_b)}",
            file=sys.stderr,
        )

    # Pair rows by index; Part B may have more or fewer due to section headers
    merged: list[dict] = []
    last_spec_no = prev_spec_no
    last_section = prev_section

    # Use zip (up to the shorter) and fall back to extending with None
    max_rows = max(len(rows_a), len(rows_b))
    for i in range(max_rows):
        row_a = rows_a[i] if i < len(rows_a) else {}
        row_b = rows_b[i] if i < len(rows_b) else {}

        # Forward-fill spec_no from previous rows
        spec_no = row_a.get("spec_no") or last_spec_no
        if row_a.get("spec_no"):
            last_spec_no = row_a["spec_no"]

        section = row_a.get("section") or last_section
        if row_a.get("section"):
            last_section = row_a["section"]

        # Cross-validate grade hint if both present
        grade = row_a.get("grade")
        grade_hint = row_b.get("grade_hint")
        if grade and grade_hint and grade != grade_hint:
            # Minor mismatch — keep Part A value as authoritative
            pass

        # E/F factor
        ef_factor: float | None = None
        if not no_ef:
            ef_factor = row_b.get("ef_factor") if ef_on_b else row_a.get("ef_factor")

        stresses = row_b.get("stresses", [])

        if not spec_no and not grade:
            continue  # skip empty rows

        merged.append({
            "table_name":      table_key,
            "table_desc":      info["name"],
            "section":         section,
            "spec_no":         spec_no,
            "grade":           grade,
            "type_or_class":   row_a.get("type_or_class"),
            "nominal_comp":    row_a.get("nominal_comp"),
            "p_no":            row_a.get("p_no"),
            "notes":           row_a.get("notes"),
            "min_tensile_ksi": row_a.get("min_tensile_ksi"),
            "min_yield_ksi":   row_a.get("min_yield_ksi"),
            "ef_factor":       ef_factor,
            "stresses":        stresses,
            "source_pair_page": a_page,
        })

    return merged, last_spec_no, last_section


def run(force: bool = False) -> None:
    MERGED_DIR.mkdir(parents=True, exist_ok=True)

    for table_key, info in tqdm(TABLE_RANGES.items(), desc="Merging tables"):
        prev_spec_no: str | None = None
        prev_section: str | None = None

        for a_page, b_page in info["pairs"]:
            out_path = MERGED_DIR / f"pair_{a_page:03d}.json"
            if not force and out_path.exists():
                existing = json.loads(out_path.read_text())
                if existing:
                    last = existing[-1]
                    prev_spec_no = last.get("spec_no", prev_spec_no)
                    prev_section = last.get("section", prev_section)
                continue

            merged, prev_spec_no, prev_section = _merge_pair(
                table_key, a_page, b_page, prev_spec_no, prev_section
            )
            out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2))

    print("Merge complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(force=args.force)
