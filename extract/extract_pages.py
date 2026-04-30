"""Main extraction loop: call VLM for every Part A and Part B page."""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from .config import PAGES_DIR, RAW_VLM_DIR, TABLE_RANGES
from .vlm_client import call_part_a, call_part_b


def _out_path(pdf_page: int) -> Path:
    return RAW_VLM_DIR / f"p{pdf_page:03d}_raw.json"


def _process_page(pdf_page: int, part: str, table_key: str) -> tuple[int, str, list | str]:
    image_path = PAGES_DIR / f"p{pdf_page:03d}.png"
    if not image_path.exists():
        return pdf_page, "error", f"Image not found: {image_path}"
    try:
        if part == "A":
            rows = call_part_a(pdf_page, image_path, table_key)
        else:
            rows = call_part_b(pdf_page, image_path, table_key)
        return pdf_page, "ok", rows
    except Exception as e:
        return pdf_page, "error", str(e)


def run(workers: int = 1, force: bool = False) -> None:
    RAW_VLM_DIR.mkdir(parents=True, exist_ok=True)

    # Build task list: (pdf_page, part, table_key)
    tasks: list[tuple[int, str, str]] = []
    for table_key, info in TABLE_RANGES.items():
        for a_page, b_page in info["pairs"]:
            for page, part in [(a_page, "A"), (b_page, "B")]:
                if force or not _out_path(page).exists():
                    tasks.append((page, part, table_key))

    if not tasks:
        print("All pages already extracted. Use --force to re-run.")
        return

    print(f"Extracting {len(tasks)} pages with {workers} worker(s)...")
    errors: list[tuple[int, str]] = []

    if workers == 1:
        for task in tqdm(tasks, desc="Extracting"):
            pdf_page, part, table_key = task
            _, status, result = _process_page(pdf_page, part, table_key)
            if status == "ok":
                _out_path(pdf_page).write_text(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"\n  ERROR p{pdf_page}: {result}", file=sys.stderr)
                errors.append((pdf_page, result))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_page, *t): t for t in tasks}
            for future in tqdm(as_completed(futures), total=len(tasks), desc="Extracting"):
                pdf_page, status, result = future.result()
                if status == "ok":
                    _out_path(pdf_page).write_text(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"\n  ERROR p{pdf_page}: {result}", file=sys.stderr)
                    errors.append((pdf_page, result))

    if errors:
        print(f"\n{len(errors)} page(s) failed:")
        for pg, msg in errors:
            print(f"  p{pg}: {msg}")
    else:
        print("All pages extracted successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(workers=args.workers, force=args.force)
