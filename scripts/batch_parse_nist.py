#!/usr/bin/env python3
"""Parse every COBOL source file in ``tests/testdata/gov/nist/`` to its AST,
measure elapsed time per file, and stream results one line at a time to a JSONL
output file.

Output: ``docs/nist_parse_results.jsonl`` (one JSON object per line).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NIST_DIR = Path("tests/testdata/gov/nist")
OUTPUT_DIR = Path("docs")
SOURCE_EXTS = {".CBL", ".cbl", ".COB", ".cob"}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch parse NIST COBOL test files")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from existing JSONL, skip already-processed files")
    args = parser.parse_args()

    nist_dir = NIST_DIR.resolve()
    if not nist_dir.is_dir():
        print(f"ERROR: directory not found: {nist_dir}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "nist_parse_results.jsonl"

    # Determine which files to process
    files: list[Path] = sorted(
        p
        for p in nist_dir.iterdir()
        if p.is_file() and p.suffix in SOURCE_EXTS
    )

    processed: set[str] = set()
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    processed.add(r["filename"])
                except json.JSONDecodeError:
                    pass
        print(f"Resuming: {len(processed)} already processed, skipping them")

    remaining = [f for f in files if f.name not in processed]
    total = len(files)
    remaining_total = len(remaining)
    print(f"Found {total} COBOL source files in {nist_dir}")
    if remaining_total < total:
        print(f"  {remaining_total} remaining to process")

    if not remaining:
        print("All files already processed.")
        return

    # Import heavies once
    from cobol_py import (
        CobolParserRunner,
        CobolParserParams,
        CobolPreprocessorException,
        CobolParserException,
    )

    ok_count = sum(1 for f in processed if f in processed)  # placeholder, recalc later
    err_count = 0
    # Recalculate ok/err from existing file
    _ok = 0
    _err = 0
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("status") == "ok":
                        _ok += 1
                    else:
                        _err += 1
                except json.JSONDecodeError:
                    pass
    ok_count = _ok
    err_count = _err

    mode = "a" if args.resume else "w"
    with open(out_path, mode, encoding="utf-8") as out_fh:
        for i, cobol_file in enumerate(remaining, 1):
            rel = cobol_file.relative_to(nist_dir.parent.parent)
            result: dict = {
                "file": str(rel),
                "filename": cobol_file.name,
                "size_bytes": cobol_file.stat().st_size,
                "status": "ok",
                "elapsed_ms": None,
                "error_type": None,
                "error_message": None,
            }

            t0 = time.perf_counter()
            try:
                runner = CobolParserRunner()
                params = CobolParserParams()
                params.ignore_missing_copy = True
                params.copy_book_directories = [nist_dir]
                params.copy_book_extensions = ["CPY", "cpy"]

                runner.parse_file(str(cobol_file))
                result["status"] = "ok"
                result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                ok_count += 1
            except (CobolPreprocessorException, CobolParserException) as e:
                result["status"] = "parse_error"
                result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                result["error_type"] = type(e).__name__
                result["error_message"] = str(e)[:500]
                err_count += 1
            except Exception as e:
                result["status"] = "unknown_error"
                result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                result["error_type"] = type(e).__name__
                result["error_message"] = str(e)[:500]
                result["traceback"] = traceback.format_exc()[-2000:]
                err_count += 1

            # Write immediately after each file
            out_fh.write(json.dumps(result, ensure_ascii=False) + "\n")
            out_fh.flush()

            # Progress to stdout
            elapsed_str = f"{result['elapsed_ms']:8.1f}ms" if result["elapsed_ms"] else "     N/A"
            status_flag = "✓" if result["status"] == "ok" else "✗"
            print(
                f"  [{i:4d}/{remaining_total}] {status_flag} {elapsed_str}  {result['filename']}"
                + (f"  {result['error_type']}" if result["error_type"] else "")
            )

    # Summary
    processed_total = len(processed) + remaining_total
    total_ok = ok_count
    total_err = err_count
    print(f"\nDone.  Total: {processed_total}  OK: {total_ok}  Errors: {total_err}")
    print(f"Output → {out_path.resolve()}")


if __name__ == "__main__":
    main()
