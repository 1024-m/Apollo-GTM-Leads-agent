#!/usr/bin/env python3
import argparse
import sys

from apollo import create_contact_list


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
        create_contact_list(apollo_list)
    except Exception:
        return 2
    print(apollo_list)
    return 0


if __name__ == "__main__":
    sys.exit(main())
