import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from env import load_env
from hf import dataset_id, hf_token
from store import FULL_TEXT, WIDTHS, cell, width_for

try:
    from huggingface_hub import HfApi, hf_hub_download, list_repo_files
except ImportError:
    HfApi = None
    hf_hub_download = None
    list_repo_files = None

SHARD_FIELDS = [
    "query",
    "activity_id",
    "post_url",
    "author_name",
    "author_type",
    "author_vanity",
    "linkedin_url",
    "headline",
    "post_snippet",
    "post_text",
    "date_raw",
    "fetched_at",
    "apollo_list",
    "vote",
    "voted_at",
    "in_apollo",
]
DATA_EXTS = {".csv", ".json", ".jsonl"}
STATE_NAME = "apollo-state.csv"
STATE_FIELDS = ["linkedin_url", "apollo_contact_id", "name", "fetched_at"]


def list_dir_name(apollo_list):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", (apollo_list or "").strip()).strip("._")[:80]
    return safe or "list"


def norm_linkedin(url):
    text = (url or "").strip().split("?")[0].rstrip("/").lower()
    return text


def row_linkedin(row):
    return (row.get("linkedin_url") or row.get("profile_url_guess") or "").strip()


def is_state_file(path):
    return Path(path).name == STATE_NAME


def apollo_state_path(apollo_list):
    return f"{list_dir_name(apollo_list)}/{STATE_NAME}"


def _api():
    if HfApi is None:
        raise RuntimeError("huggingface_hub")
    load_env()
    return HfApi(token=hf_token())


def _norm_row(row):
    return {(k or "").strip(): ("" if v is None else str(v)).strip() for k, v in (row or {}).items()}


def _read_csv_text(text):
    rows = []
    handle = io.StringIO(text)
    for row in csv.DictReader(handle):
        rows.append(_norm_row(row))
    return rows


def _read_json_text(text):
    payload = json.loads(text)
    if isinstance(payload, list):
        return [_norm_row(row) for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [_norm_row(payload)]
    return []


def _read_jsonl_text(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(_norm_row(payload))
    return rows


def parse_bytes(path, raw):
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return _read_csv_text(text)
    if suffix == ".jsonl":
        return _read_jsonl_text(text)
    if suffix == ".json":
        return _read_json_text(text)
    return []


def rows_to_csv(rows, fields=None):
    keys = fields or SHARD_FIELDS
    extra = []
    for row in rows:
        for key in row:
            if key not in keys and key not in extra:
                extra.append(key)
    keys = list(keys) + extra
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore", quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: cell(
                    row.get(key, ""),
                    None if key in FULL_TEXT else (width_for(key) if key in WIDTHS else max(len(key), 50)),
                )
                for key in keys
            }
        )
    return handle.getvalue()


def repo_data_files(apollo_list=None, votes_only=False):
    repo = dataset_id()
    prefix = f"{list_dir_name(apollo_list)}/" if apollo_list else ""
    files = []
    for path in list_repo_files(repo_id=repo, repo_type="dataset", token=hf_token()):
        suffix = Path(path).suffix.lower()
        if suffix not in DATA_EXTS:
            continue
        if prefix and not path.startswith(prefix):
            continue
        if votes_only and is_state_file(path):
            continue
        files.append(path)
    return repo, files


def load_list_files(apollo_list, votes_only=True):
    repo, files = repo_data_files(apollo_list, votes_only=votes_only)
    out = []
    for path in files:
        local = hf_hub_download(repo_id=repo, repo_type="dataset", filename=path, token=hf_token())
        out.append((path, parse_bytes(path, Path(local).read_bytes())))
    return out


def load_list_rows(apollo_list):
    rows = []
    for _, file_rows in load_list_files(apollo_list):
        rows.extend(file_rows)
    return rows


def skip_sets(apollo_list):
    post_urls = set()
    keep_profiles = set()
    try:
        rows = load_list_rows(apollo_list)
        state = load_apollo_state(apollo_list)
    except Exception:
        return post_urls, keep_profiles
    for row in rows:
        post_url = row.get("post_url", "")
        activity_id = row.get("activity_id", "")
        profile = row_linkedin(row)
        vote = (row.get("vote") or "").strip().lower()
        if post_url:
            post_urls.add(post_url)
        if activity_id:
            post_urls.add(activity_id)
        if vote == "keep" and profile:
            keep_profiles.add(norm_linkedin(profile) or profile)
        if (row.get("in_apollo") or "").strip().lower() == "y" and profile:
            keep_profiles.add(norm_linkedin(profile) or profile)
    for row in state:
        url = norm_linkedin(row.get("linkedin_url", ""))
        if url:
            keep_profiles.add(url)
    return post_urls, keep_profiles


def hour_shard_path(apollo_list, when=None):
    when = when or datetime.now(timezone.utc)
    name = when.strftime("%d%m%Y-%H") + ".csv"
    return f"{list_dir_name(apollo_list)}/{name}"


def merge_filename(apollo_list, ext=".csv", when=None):
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%d%m%Y-%H%M")
    return f"{stamp}-{list_dir_name(apollo_list)}{ext}"


def upload_rows(apollo_list, path, rows, fields=None):
    csv_text = rows_to_csv(rows, fields=fields)
    tmp = Path("/tmp") / Path(path).name
    tmp.write_text(csv_text, encoding="utf-8")
    _api().upload_file(
        path_or_fileobj=str(tmp),
        path_in_repo=path,
        repo_id=dataset_id(),
        repo_type="dataset",
        commit_message=f"update {path}",
    )


def append_vote_row(apollo_list, row):
    path = hour_shard_path(apollo_list)
    existing = []
    repo = dataset_id()
    try:
        local = hf_hub_download(repo_id=repo, repo_type="dataset", filename=path, token=hf_token())
        existing = parse_bytes(path, Path(local).read_bytes())
    except Exception:
        existing = []
    row = _norm_row(row)
    if not row.get("in_apollo"):
        row["in_apollo"] = "n"
    profile = norm_linkedin(row_linkedin(row))
    if profile and profile in apollo_state_urls(apollo_list):
        row["in_apollo"] = "y"
    existing.append(row)
    upload_rows(apollo_list, path, existing)
    return path


def mark_profiles_in_apollo(apollo_list, profiles):
    wanted = {norm_linkedin(item) for item in profiles if norm_linkedin(item)}
    if not wanted:
        return 0
    flipped = 0
    for path, rows in load_list_files(apollo_list):
        changed = False
        for row in rows:
            profile = norm_linkedin(row_linkedin(row))
            vote = (row.get("vote") or "").strip().lower()
            if vote != "keep" or profile not in wanted:
                continue
            if (row.get("in_apollo") or "").strip().lower() == "y":
                continue
            row["in_apollo"] = "y"
            flipped += 1
            changed = True
        if changed:
            upload_rows(apollo_list, path, rows)
    return flipped


def load_apollo_state(apollo_list):
    repo = dataset_id()
    path = apollo_state_path(apollo_list)
    try:
        local = hf_hub_download(repo_id=repo, repo_type="dataset", filename=path, token=hf_token())
        return parse_bytes(path, Path(local).read_bytes())
    except Exception:
        return []


def apollo_state_urls(apollo_list):
    return {norm_linkedin(row.get("linkedin_url", "")) for row in load_apollo_state(apollo_list) if norm_linkedin(row.get("linkedin_url", ""))}


def save_apollo_state(apollo_list, rows):
    by_url = {}
    for row in rows:
        url = norm_linkedin(row.get("linkedin_url", ""))
        if not url:
            continue
        by_url[url] = {
            "linkedin_url": url,
            "apollo_contact_id": (row.get("apollo_contact_id") or "").strip(),
            "name": (row.get("name") or "").strip(),
            "fetched_at": (row.get("fetched_at") or "").strip(),
        }
    upload_rows(apollo_list, apollo_state_path(apollo_list), list(by_url.values()), fields=STATE_FIELDS)
    return len(by_url)


def upsert_apollo_state(apollo_list, rows):
    existing = load_apollo_state(apollo_list)
    return save_apollo_state(apollo_list, existing + list(rows))


def refresh_apollo_state(apollo_list):
    from apollo import list_contacts_on_list, require_list

    wanted = require_list(apollo_list)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for contact in list_contacts_on_list(wanted):
        url = (contact.get("linkedin_url") or "").strip()
        if not url:
            continue
        rows.append(
            {
                "linkedin_url": url,
                "apollo_contact_id": (contact.get("id") or "").strip(),
                "name": (contact.get("name") or "").strip(),
                "fetched_at": now,
            }
        )
    return wanted, save_apollo_state(wanted, rows)
