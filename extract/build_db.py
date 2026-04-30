"""Build SQLite database from merged JSON files."""
import json
import sqlite3
from pathlib import Path

from tqdm import tqdm

from .config import DB_PATH, MERGED_DIR, TABLE_RANGES

DDL = """
CREATE TABLE IF NOT EXISTS materials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name      TEXT NOT NULL,
    table_desc      TEXT,
    section         TEXT,
    spec_no         TEXT NOT NULL,
    grade           TEXT,
    type_or_class   TEXT,
    nominal_comp    TEXT,
    p_no            TEXT,
    notes           TEXT,
    min_tensile_ksi REAL,
    min_yield_ksi   REAL,
    ef_factor       REAL,
    source_pair_page INTEGER
);

CREATE TABLE IF NOT EXISTS stress_values (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    temp_f      INTEGER NOT NULL,
    stress_ksi  REAL,
    is_creep    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_material ON materials(spec_no, grade, type_or_class);
CREATE INDEX IF NOT EXISTS idx_stress   ON stress_values(material_id, temp_f);

CREATE VIEW IF NOT EXISTS stress_lookup AS
SELECT
    m.table_name, m.table_desc, m.section,
    m.spec_no, m.grade, m.type_or_class, m.nominal_comp,
    m.p_no, m.ef_factor,
    sv.temp_f, sv.stress_ksi, sv.is_creep
FROM materials m
JOIN stress_values sv ON sv.material_id = m.id;
"""


def run(force: bool = False) -> None:
    if DB_PATH.exists() and force:
        DB_PATH.unlink()
    elif DB_PATH.exists():
        print(f"DB already exists at {DB_PATH}. Use --force to rebuild.")
        return

    con = sqlite3.connect(DB_PATH)
    con.executescript(DDL)
    con.commit()

    all_pairs: list[Path] = sorted(MERGED_DIR.glob("pair_*.json"))
    if not all_pairs:
        print("No merged JSON files found. Run merge_pairs first.")
        con.close()
        return

    total_materials = 0
    total_stresses = 0

    for pair_file in tqdm(all_pairs, desc="Building DB"):
        rows = json.loads(pair_file.read_text())
        for row in rows:
            if not row.get("spec_no"):
                continue

            cur = con.execute(
                """INSERT INTO materials
                   (table_name, table_desc, section, spec_no, grade, type_or_class,
                    nominal_comp, p_no, notes, min_tensile_ksi, min_yield_ksi,
                    ef_factor, source_pair_page)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["table_name"], row["table_desc"], row.get("section"),
                    row["spec_no"], row.get("grade"), row.get("type_or_class"),
                    row.get("nominal_comp"), row.get("p_no"), row.get("notes"),
                    row.get("min_tensile_ksi"), row.get("min_yield_ksi"),
                    row.get("ef_factor"), row.get("source_pair_page"),
                ),
            )
            mat_id = cur.lastrowid
            total_materials += 1

            for sv in row.get("stresses", []):
                con.execute(
                    "INSERT INTO stress_values (material_id, temp_f, stress_ksi, is_creep) VALUES (?,?,?,?)",
                    (mat_id, sv["temp_f"], sv.get("stress_ksi"), 1 if sv.get("is_creep") else 0),
                )
                total_stresses += 1

    con.commit()
    con.close()
    print(f"DB built: {total_materials} materials, {total_stresses} stress values → {DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(force=args.force)
