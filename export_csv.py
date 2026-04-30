"""Export asme_b311.db to CSV files."""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH  = Path(__file__).parent / "asme_b311.db"
OUT_DIR  = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)

con = sqlite3.connect(DB_PATH)

# 1. materials 테이블
df_mat = pd.read_sql("SELECT * FROM materials", con)
df_mat.to_csv(OUT_DIR / "materials.csv", index=False)
print(f"materials.csv       : {len(df_mat):,} rows")

# 2. stress_values 테이블
df_sv = pd.read_sql("SELECT * FROM stress_values", con)
df_sv.to_csv(OUT_DIR / "stress_values.csv", index=False)
print(f"stress_values.csv   : {len(df_sv):,} rows")

# 3. stress_lookup 뷰 (두 테이블 JOIN — 두께 계산에 바로 쓸 수 있는 넓은 형태)
df_lk = pd.read_sql("SELECT * FROM stress_lookup", con)
df_lk.to_csv(OUT_DIR / "stress_lookup.csv", index=False)
print(f"stress_lookup.csv   : {len(df_lk):,} rows")

# 4. wide-format (ASME 표 그대로 — 온도별 열로 펼침)
df_wide = pd.read_sql("""
    SELECT
        m.table_name,
        m.table_desc,
        m.section,
        m.spec_no,
        m.grade,
        m.type_or_class,
        m.nominal_comp,
        m.p_no,
        m.notes,
        m.min_tensile_ksi,
        m.min_yield_ksi,
        m.ef_factor,
        sv.temp_f,
        sv.stress_ksi,
        sv.is_creep
    FROM materials m
    JOIN stress_values sv ON sv.material_id = m.id
""", con)

# 온도 컬럼 헤더 형식: "100°F", "200°F", ...
df_wide["temp_col"] = df_wide["temp_f"].astype(str) + "°F"

# 크리프 구간은 값 뒤에 * 표시
df_wide["stress_display"] = df_wide.apply(
    lambda r: f"{r['stress_ksi']}*" if r["is_creep"] and pd.notna(r["stress_ksi"])
              else (str(r["stress_ksi"]) if pd.notna(r["stress_ksi"]) else ""),
    axis=1,
)

META_COLS = ["table_name", "table_desc", "section", "spec_no", "grade",
             "type_or_class", "nominal_comp", "p_no", "notes",
             "min_tensile_ksi", "min_yield_ksi", "ef_factor"]

pivot = df_wide.pivot_table(
    index=META_COLS,
    columns="temp_col",
    values="stress_display",
    aggfunc="first",
).reset_index()

# 온도 컬럼 순서 정렬 (숫자 순)
temp_cols_sorted = sorted(
    [c for c in pivot.columns if c.endswith("°F")],
    key=lambda x: int(x.replace("°F", "")),
)
pivot = pivot[META_COLS + temp_cols_sorted]

# 컬럼명을 ASME 표 스타일로 변경
pivot.columns = (
    ["Table", "Table Description", "Section",
     "Spec. No.", "Grade", "Type or Class", "Nominal Composition",
     "P-No.", "Notes",
     "Specified Minimum Tensile, ksi", "Specified Minimum Yield, ksi",
     "E or F"]
    + temp_cols_sorted
)

pivot = pivot.fillna("")
pivot.to_csv(OUT_DIR / "stress_wide.csv", index=False)
print(f"stress_wide.csv     : {len(pivot):,} rows × {len(pivot.columns)} cols  (* = creep regime)")

con.close()
print(f"\n저장 위치: {OUT_DIR.resolve()}")
