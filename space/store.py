import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTHS = {
    "query": 50,
    "activity_id": 150,
    "post_url": 250,
    "author_name": 50,
    "author_type": 10,
    "author_vanity": 100,
    "linkedin_url": 150,
    "headline": 50,
    "post_snippet": 50,
    "post_text": 250,
    "date_raw": 10,
    "fetched_at": 20,
    "apollo_list": 80,
    "vote": 10,
    "voted_at": 20,
    "in_apollo": 10,
    "apollo_contact_id": 50,
}
FULL_TEXT = {"headline", "post_snippet", "post_text"}


def flat(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def width_for(key):
    return max(len(key), WIDTHS.get(key, 50))


def cell(value, width=None):
    text = flat(value)
    if width and len(text) > width:
        return text[:width]
    return text


def _writer(handle, fields):
    return csv.DictWriter(
        handle,
        fieldnames=fields,
        extrasaction="ignore",
        quoting=csv.QUOTE_ALL,
    )


def write_header(path, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        _writer(handle, fields).writerow({key: cell(key, width_for(key)) for key in fields})


def write_row(path, fields, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {key: cell(row.get(key, ""), width_for(key)) for key in fields}
    with path.open("a", newline="", encoding="utf-8") as handle:
        _writer(handle, fields).writerow(out)


def load_ids(path, *keys):
    ids = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            normalized = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            for key in keys:
                value = normalized.get(key, "")
                if value:
                    ids.add(value)
    return ids
