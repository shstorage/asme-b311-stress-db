"""Validation checks for the extracted ASME B31.1 stress DB."""
import sqlite3
import sys

from extract.config import DB_PATH

# Known correct values: (spec_no, grade, type_or_class, temp_f, expected_stress_ksi)
# type_or_class: 'S'=Seamless, 'E'=ERW, None=any
SPOT_CHECKS = [
    ("A53",  "A", "S",   100, 13.7),   # Seamless
    ("A53",  "B", "S",   100, 17.1),   # Seamless
    ("A53",  "B", "S",   800, 10.8),   # Seamless (creep regime)
    ("A53",  "A", "E",   100, 11.7),   # ERW (= 13.7 * 0.85)
    ("A106", "B", None,  100, 17.1),
    ("A106", "B", None,  700, 15.6),   # 700°F is in creep regime for carbon steel
]


def check_spot_values(con: sqlite3.Connection) -> int:
    failures = 0
    for spec_no, grade, toc, temp_f, expected in SPOT_CHECKS:
        query = """
            SELECT stress_ksi FROM stress_lookup
            WHERE spec_no = ? AND grade = ?
              AND (? IS NULL OR type_or_class = ?)
              AND temp_f = ?
            LIMIT 1
        """
        row = con.execute(query, (spec_no, grade, toc, toc, temp_f)).fetchone()
        if row is None:
            print(f"  FAIL spot-check: {spec_no} {grade} {temp_f}°F — not found")
            failures += 1
        elif abs(row[0] - expected) > 0.15:
            print(f"  FAIL spot-check: {spec_no} {grade} {temp_f}°F — got {row[0]}, expected {expected}")
            failures += 1
        else:
            print(f"  OK   {spec_no} {grade} {temp_f}°F = {row[0]} ksi")
    return failures


def check_creep_temperatures(con: sqlite3.Connection) -> int:
    """Creep (is_creep=1) should not appear below 700°F for any material."""
    rows = con.execute("""
        SELECT m.spec_no, m.grade, sv.temp_f, sv.stress_ksi
        FROM stress_values sv
        JOIN materials m ON m.id = sv.material_id
        WHERE sv.is_creep = 1 AND sv.temp_f < 700
        LIMIT 20
    """).fetchall()
    if rows:
        print(f"  WARNING: {len(rows)} creep-flagged values below 700°F:")
        for r in rows[:5]:
            print(f"    {r[0]} {r[1]} @ {r[2]}°F = {r[3]} ksi")
    return len(rows)


def check_null_gaps(con: sqlite3.Connection) -> int:
    """NULL stress value surrounded by non-NULL values is suspicious."""
    issues = con.execute("""
        SELECT m.spec_no, m.grade, sv.temp_f
        FROM stress_values sv
        JOIN materials m ON m.id = sv.material_id
        WHERE sv.stress_ksi IS NULL
          AND EXISTS (
              SELECT 1 FROM stress_values sv2
              WHERE sv2.material_id = sv.material_id AND sv2.temp_f < sv.temp_f AND sv2.stress_ksi IS NOT NULL
          )
          AND EXISTS (
              SELECT 1 FROM stress_values sv3
              WHERE sv3.material_id = sv.material_id AND sv3.temp_f > sv.temp_f AND sv3.stress_ksi IS NOT NULL
          )
        LIMIT 20
    """).fetchall()
    if issues:
        print(f"  WARNING: {len(issues)} NULL values with non-NULL values on both sides:")
        for r in issues[:5]:
            print(f"    {r[0]} {r[1]} @ {r[2]}°F")
    return len(issues)


def check_row_counts(con: sqlite3.Connection) -> None:
    rows = con.execute("""
        SELECT table_name, COUNT(DISTINCT id) as n_materials
        FROM materials GROUP BY table_name ORDER BY table_name
    """).fetchall()
    print("\n  Materials per table:")
    for r in rows:
        print(f"    {r[0]}: {r[1]} rows")


def main() -> None:
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}. Run build_db first.")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    print("=== Spot-check known values ===")
    spot_failures = check_spot_values(con)

    print("\n=== Creep temperature sanity ===")
    creep_issues = check_creep_temperatures(con)
    if not creep_issues:
        print("  OK — no creep flags below 700°F")

    print("\n=== NULL gap check ===")
    null_issues = check_null_gaps(con)
    if not null_issues:
        print("  OK — no suspicious NULL gaps")

    print("\n=== Row counts ===")
    check_row_counts(con)

    con.close()
    print()
    if spot_failures:
        print(f"VALIDATION FAILED: {spot_failures} spot-check(s) failed.")
        sys.exit(1)
    else:
        print("Validation passed.")


if __name__ == "__main__":
    main()
