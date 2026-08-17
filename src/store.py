import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BODIES = ROOT / "data" / "bodies"
WIDTHS = {
    "query": 50,
    "activity_id": 150,
    "post_url": 250,
    "author_name": 50,
    "author_type": 10,
    "author_vanity": 100,
    "profile_url_guess": 120,
    "headline": 50,
    "post_snippet": 50,
    "post_text": 250,
    "date_raw": 10,
    "fetched_at": 20,
    "post_id": 20,
    "title": 125,
    "author": 50,
    "author_url": 120,
    "subreddit": 50,
    "subreddit_url": 80,
    "created_at": 40,
    "outbound_url": 250,
}


def flat(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def width_for(key):
    return max(len(key), WIDTHS.get(key, 50))


def cell(value, width):
    text = flat(value)
    if len(text) > width:
        return text[:width]
    return text.ljust(width)


def save_body(table, item_id, text):
    if not item_id or not text:
        return
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(item_id)).strip("._")[:180] or "unknown"
    path = BODIES / table / f"{safe}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text), encoding="utf-8")


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


def write_row(path, fields, row, table, id_field, body_field):
    item_id = flat(row.get(id_field, "")) or flat(row.get("post_url") or row.get("comment_url") or "")
    save_body(table, item_id, row.get(body_field, ""))
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
