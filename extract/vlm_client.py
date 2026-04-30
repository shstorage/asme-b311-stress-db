"""VLM API client with prompts for Part A and Part B extraction."""
import base64
import json
import re
from pathlib import Path

import fitz
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import PDF_PATH, VLM_URL, VLM_MODEL


def _get_page_text(pdf_page: int) -> str:
    doc = fitz.open(PDF_PATH)
    text = doc[pdf_page - 1].get_text("text")
    doc.close()
    return text


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _parse_json_response(raw: str) -> list[dict]:
    """Strip markdown fences and parse JSON array."""
    text = raw.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```[a-z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    return json.loads(text)


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key="EMPTY", base_url=VLM_URL)
    return _client


PART_A_PROMPT = """\
You are extracting data from an ASME B31.1 Allowable Stress Table page — the LEFT half \
showing material specifications.

The raw text extracted from this page is:
===
{page_text}
===

Extract each material data row as a JSON array. Each element must have exactly these keys:
- "row_index": integer, 1-based, strictly sequential for every data row on this page
- "section": section header text visible above this row (e.g. "Seamless Pipe and Tube"), or null
- "spec_no": ASTM/ASME spec number (e.g. "A53"), or null if continued from above
- "grade": grade text (e.g. "A", "B", "T5"), or null
- "type_or_class": type or class text, or null
- "nominal_comp": nominal composition (e.g. "C-Mn", "18Cr-8Ni"), or null
- "p_no": P-number string (e.g. "1", "5B"), or null
- "notes": notes reference string (e.g. "(1)(2)"), or null
- "min_tensile_ksi": specified minimum tensile strength as a number, or null
- "min_yield_ksi": specified minimum yield strength as a number, or null
- "ef_factor": E or F factor as a number (e.g. 1.00, 0.85), or null{ef_note}

Count every data row including sub-rows where only the grade changes.
Skip header rows and section title rows — only include actual material data rows.
Output ONLY the JSON array. No prose, no markdown fences.
"""

PART_A_NO_EF_NOTE = "\n  NOTE: This table (A-10 Bolts) has no E/F column — always use null for ef_factor."
PART_A_EF_ON_B_NOTE = "\n  NOTE: For this table (A-8), E/F appears on the stress-values page, not here — use null for ef_factor."

PART_B_PROMPT = """\
You are extracting data from an ASME B31.1 Allowable Stress Table page — the RIGHT half \
showing allowable stress values at temperature.

Table: {table_name}
Temperature columns left-to-right: {temp_list} (°F)
The rightmost columns are Grade and Spec. No. (for cross-reference only).{ef_on_b_note}

The raw text extracted from this page is:
===
{page_text}
===

Extract each data row as a JSON array with exactly these keys:
- "row_index": integer, 1-based, same sequential count as Part A for this page
- "grade_hint": grade text visible at the right margin of this row, or null
- "spec_no_hint": spec number visible at right (usually only on first row of a group), or null
- "stress_values": array of exactly {n_temps} numbers matching the temperature columns above
  Use null for any cell showing "…" (ellipsis) or blank{ef_on_b_field}

Count rows identically to Part A — include every sub-row where grade/stress changes.
Skip header rows and section-title rows.
Output ONLY the JSON array. No prose, no markdown fences.
"""

EF_ON_B_NOTE = "\nE or F factor column appears on the LEFT of the stress values on this page."
EF_ON_B_FIELD = '\n- "ef_factor": the E or F factor for this row (number), or null'


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def call_part_a(pdf_page: int, image_path: Path, table_key: str) -> list[dict]:
    info = _get_table_info(table_key)
    ef_note = ""
    if info.get("no_ef"):
        ef_note = PART_A_NO_EF_NOTE
    elif info.get("ef_on_partb"):
        ef_note = PART_A_EF_ON_B_NOTE

    prompt = PART_A_PROMPT.format(
        page_text=_get_page_text(pdf_page),
        ef_note=ef_note,
    )
    return _call_vlm(image_path, prompt)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def call_part_b(pdf_page: int, image_path: Path, table_key: str) -> list[dict]:
    from .config import TABLE_RANGES
    info = TABLE_RANGES[table_key]
    temps = info["temps"]
    ef_on_b = info.get("ef_on_partb", False)

    ef_on_b_note = EF_ON_B_NOTE if ef_on_b else ""
    ef_on_b_field = EF_ON_B_FIELD if ef_on_b else ""

    prompt = PART_B_PROMPT.format(
        table_name=f"{table_key} {info['name']}",
        temp_list=", ".join(str(t) for t in temps),
        n_temps=len(temps),
        page_text=_get_page_text(pdf_page),
        ef_on_b_note=ef_on_b_note,
        ef_on_b_field=ef_on_b_field,
    )
    return _call_vlm(image_path, prompt)


def _get_table_info(table_key: str) -> dict:
    from .config import TABLE_RANGES
    return TABLE_RANGES[table_key]


def _call_vlm(image_path: Path, prompt: str) -> list[dict]:
    b64 = _encode_image(image_path)
    client = _get_client()
    response = client.chat.completions.create(
        model=VLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        temperature=0.1,
        timeout=300,
    )
    raw = response.choices[0].message.content
    return _parse_json_response(raw)
