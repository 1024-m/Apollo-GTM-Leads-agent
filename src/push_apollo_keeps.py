#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone

from apollo import add_contacts_to_list, create_contact, require_list, search_contacts
from dataset_io import (
    apollo_state_urls,
    load_list_rows,
    mark_profiles_in_apollo,
    norm_linkedin,
    row_linkedin,
    upsert_apollo_state,
)

BATCH = 50


def _match_contact(profile, contacts):
    wanted = norm_linkedin(profile)
    if not wanted:
        return None
    for row in contacts:
        url = norm_linkedin(row.get("linkedin_url") or "")
        if url and (url == wanted or wanted in url or url in wanted):
            return row
    return None


def _resolve_contact(row):
    profile = row_linkedin(row)
    if not profile:
        return None
    vanity = (row.get("author_vanity") or "").strip()
    name = (row.get("author_name") or "").strip()
    title = (row.get("headline") or "").strip()
    found = search_contacts(vanity) if vanity else []
    matched = _match_contact(profile, found)
    if matched:
        return matched
    found = search_contacts(profile) or found
    matched = _match_contact(profile, found)
    if matched:
        return matched
    return create_contact(name, profile, title)


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
        already = apollo_state_urls(apollo_list)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 2
    pending = []
    seen = set()
    for row in rows:
        if (row.get("vote") or "").strip().lower() != "keep":
            continue
        profile = norm_linkedin(row_linkedin(row))
        if not profile or profile in seen:
            continue
        seen.add(profile)
        if profile in already:
            continue
        if (row.get("in_apollo") or "").strip().lower() == "y":
            continue
        pending.append(row)
    already_keeps = [
        row
        for row in rows
        if (row.get("vote") or "").strip().lower() == "keep"
        and norm_linkedin(row_linkedin(row)) in already
        and (row.get("in_apollo") or "").strip().lower() != "y"
    ]
    if already_keeps:
        mark_profiles_in_apollo(
            apollo_list,
            [row_linkedin(row) for row in already_keeps],
        )
    if not pending:
        print("0")
        return 0
    ids = []
    ok_rows = []
    failed = 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state_rows = []
    for row in pending:
        try:
            contact = _resolve_contact(row)
        except Exception as exc:
            print(exc, file=sys.stderr)
            failed += 1
            continue
        contact_id = (contact or {}).get("id") if isinstance(contact, dict) else None
        if not contact_id:
            failed += 1
            continue
        ids.append(contact_id)
        ok_rows.append(row)
        state_rows.append(
            {
                "linkedin_url": row_linkedin(row),
                "apollo_contact_id": contact_id,
                "name": (contact.get("name") or row.get("author_name") or "").strip(),
                "fetched_at": now,
            }
        )
    added = 0
    for start in range(0, len(ids), BATCH):
        chunk = ids[start : start + BATCH]
        try:
            add_contacts_to_list(apollo_list, chunk)
            added += len(chunk)
        except Exception as exc:
            print(exc, file=sys.stderr)
            return 2
    flipped = mark_profiles_in_apollo(apollo_list, [row_linkedin(row) for row in ok_rows])
    upsert_apollo_state(apollo_list, state_rows)
    print(f"people={len(pending)} added={added} flagged={flipped} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
