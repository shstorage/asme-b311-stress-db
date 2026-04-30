"""Render PDF pages to PNG and extract italic text spans."""
import json
import fitz
from tqdm import tqdm
from .config import PDF_PATH, PAGES_DIR, ITALIC_DIR, TABLE_RANGES

RENDER_DPI = 300
MATRIX = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)


def _all_pages() -> list[int]:
    pages = set()
    for info in TABLE_RANGES.values():
        for a, b in info["pairs"]:
            pages.add(a)
            pages.add(b)
    return sorted(pages)


def render_all(force: bool = False) -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    ITALIC_DIR.mkdir(parents=True, exist_ok=True)

    pages = _all_pages()
    doc = fitz.open(PDF_PATH)

    for pg in tqdm(pages, desc="Rendering pages"):
        png_path = PAGES_DIR / f"p{pg:03d}.png"
        italic_path = ITALIC_DIR / f"p{pg:03d}_italics.json"

        if not force and png_path.exists() and italic_path.exists():
            continue

        page = doc[pg - 1]  # fitz is 0-indexed

        # Render
        pix = page.get_pixmap(matrix=MATRIX)
        pix.save(png_path)

        # Extract italic spans (rawdict has per-char data; build text from chars)
        italic_spans = []
        raw = page.get_text("rawdict")
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if "ital" not in span.get("font", "").lower():
                        continue
                    chars = span.get("chars", [])
                    text = "".join(c.get("c", "") for c in chars).strip()
                    if text:
                        italic_spans.append({
                            "text": text,
                            "bbox": list(span["bbox"]),
                        })

        italic_path.write_text(json.dumps(italic_spans, ensure_ascii=False))

    doc.close()
    print(f"Rendered {len(pages)} pages to {PAGES_DIR}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    render_all(force=args.force)
