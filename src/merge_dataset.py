#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from apollo import require_list
from dataset_io import load_list_rows, merge_filename, rows_to_csv

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "exports"


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--list", dest="apollo_list", required=True)
    try:
        args = parser.parse_args()
    except SystemExit:
        return 2
    apollo_list = args.apollo_list.strip()
    if not apollo_list:
        return 2
    try:
        require_list(apollo_list)
        rows = load_list_rows(apollo_list)
    except Exception:
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = merge_filename(apollo_list, ".csv")
    path = OUT_DIR / name
    path.write_text(rows_to_csv(rows), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
