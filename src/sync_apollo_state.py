#!/usr/bin/env python3
import argparse
import sys

from dataset_io import refresh_apollo_state


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
        name, count = refresh_apollo_state(apollo_list)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"{name} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
