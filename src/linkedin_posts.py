#!/usr/bin/env python3
import csv
import re
import sys
import time
import warnings
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from store import load_ids as load_id_set
from store import write_row

warnings.filterwarnings("ignore")

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "linkedin_posts.csv"
FIELDS = [
    "query",
    "activity_id",
    "post_url",
    "author_name",
    "author_type",
    "author_vanity",
    "profile_url_guess",
    "headline",
    "post_snippet",
    "post_text",
    "date_raw",
    "fetched_at",
]
STATUS_LINES = 9

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

try:
    import requests
except ImportError:
    requests = None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def draw(asked, progress, done, successful, failed, duplicates, drawn):
    lines = [
        "=============================",
        f"asked for : {asked}",
        f"in-progress : {progress}",
        f"done : {done}",
        "=============================",
        f"successful : {successful}",
        f"failed/errors : {failed}",
        f"duplicates : {duplicates}",
        "============================",
    ]
    if drawn:
        sys.stdout.write(f"\033[{STATUS_LINES}A")
    for line in lines:
        sys.stdout.write(f"\r{line}\033[K\n")
    sys.stdout.flush()
    return True


def load_ids(path):
    return load_id_set(path, "activity_id", "post_url")


def append_row(path, row):
    write_row(path, FIELDS, row, "linkedin_posts", "activity_id", "post_text")


def clean_url(url):
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def activity_id_from_url(url):
    match = re.search(r"activity-(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"ugcPost-(\d+)", url)
    if match:
        return match.group(1)
    return ""


def vanity_from_url(url):
    match = re.search(r"/posts/([^/?#]+)", url)
    if not match:
        match = re.search(r"/in/([^/?#]+)", url)
        return match.group(1) if match else ""
    return match.group(1).split("_")[0]


def name_from_title(title):
    match = re.search(r"\|\s*(.+?)\s+posted on the topic", title or "", re.I)
    if match:
        return match.group(1).strip()
    parts = [part.strip() for part in (title or "").split("|")]
    if len(parts) >= 2 and parts[-1].lower() == "linkedin":
        return parts[-2]
    return (title or "").strip()


def meta_content(html, *names):
    for name in names:
        escaped = re.escape(name)
        for attr in ("property", "name"):
            patterns = (
                rf"<meta[^>]+{attr}=[\"']{escaped}[\"'][^>]+content=[\"']([^\"']*)[\"']",
                rf"<meta[^>]+content=[\"']([^\"']*)[\"'][^>]+{attr}=[\"']{escaped}[\"']",
            )
            for pattern in patterns:
                match = re.search(pattern, html, re.I)
                if match:
                    return unescape(match.group(1)).strip()
    return ""


def relative_date(html):
    match = re.search(r"\b(\d+\s*(?:s|m|h|d|w|mo|yr|year|years|week|weeks|day|days|hour|hours|minute|minutes)s?)\b", html, re.I)
    return match.group(1).replace(" ", "") if match else ""


def classify_author(url, html, vanity):
    path = (urlparse(url).path or "").lower()
    if "/newsletters/" in path:
        return "newsletter"
    if "/pulse/" in path:
        return "article"
    html = html or ""
    vanity_l = (vanity or "").lower()
    if vanity_l:
        if re.search(rf"linkedin\.com/company/{re.escape(vanity_l)}\b", html, re.I):
            return "company"
        if re.search(rf"linkedin\.com/in/{re.escape(vanity_l)}\b", html, re.I):
            return "person"
    head = html[:80000]
    org = bool(re.search(r"urn:li:(?:organization|fsd_company|company):", head, re.I))
    person = bool(re.search(r"urn:li:(?:person|fsd_profile|member):", head, re.I))
    if org and not person:
        return "company"
    if person and not org:
        return "person"
    if "ugcpost-" in path:
        return "person"
    return "unknown"


def profile_url_for(author_type, vanity):
    if not vanity:
        return ""
    if author_type == "company":
        return f"https://www.linkedin.com/company/{vanity}"
    if author_type in {"person", "unknown"}:
        return f"https://www.linkedin.com/in/{vanity}"
    return ""


def fetch_post(url):
    if requests is None:
        return "", "", "", "", ""
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=20,
    )
    response.raise_for_status()
    html = response.text
    title = meta_content(html, "og:title", "twitter:title")
    description = meta_content(html, "og:description", "twitter:description")
    headline = ""
    headline_match = re.search(
        r"posted on the topic\s*\|\s*LinkedIn\s*</title>.*?<div[^>]*>\s*([^<]{8,160})\s*</div>",
        html,
        re.I | re.S,
    )
    if headline_match:
        headline = unescape(headline_match.group(1)).strip()
    if not headline:
        for line in re.findall(r">([^<]{12,140})<", html):
            text = unescape(line).strip()
            if "|" in text and "linkedin" not in text.lower() and "agree" not in text.lower():
                headline = text
                break
    return name_from_title(title), headline, description, relative_date(html), html


def query_variants(query):
    return [
        f"site:linkedin.com/posts {query}",
        f'site:linkedin.com/posts "{query}"',
        f"site:linkedin.com/pulse {query}",
        f"site:linkedin.com {query}",
    ]


def search(query, limit):
    if DDGS is None:
        raise RuntimeError("ddgs")
    hits = []
    client = DDGS()
    for item in client.text(query, max_results=limit):
        url = clean_url(item.get("href") or item.get("url") or "")
        if "linkedin.com" not in url:
            continue
        hits.append(
            {
                "url": url,
                "title": item.get("title") or "",
                "snippet": item.get("body") or item.get("description") or "",
            }
        )
    return hits


def parse_args(argv):
    if len(argv) != 3:
        return None
    try:
        count = int(argv[2])
    except ValueError:
        return None
    if count < 0:
        return None
    return argv[1], count


def main():
    parsed = parse_args(sys.argv)
    asked = parsed[1] if parsed else 0
    query = parsed[0] if parsed else ""
    successful = 0
    failed = 0
    duplicates = 0
    done = 0
    progress = 0
    drawn = False
    sys.stdout.write("\033[?25l")
    try:
        drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
        if parsed is None or asked == 0:
            return 2 if parsed is None else 0
        known = load_ids(DATA_PATH)
        per_search = max(asked, 10)
        for variant in query_variants(query):
            if successful >= asked:
                break
            try:
                hits = search(variant, per_search)
            except Exception:
                failed += 1
                done += 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                continue
            for hit in hits:
                if successful >= asked:
                    break
                progress = done + 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                url = hit["url"]
                activity_id = activity_id_from_url(url)
                if url in known or (activity_id and activity_id in known):
                    duplicates += 1
                    done += 1
                    drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                    continue
                vanity = vanity_from_url(url)
                name = name_from_title(hit["title"])
                headline = ""
                post_text = ""
                date_raw = ""
                html = ""
                try:
                    fetched_name, fetched_headline, fetched_text, fetched_date, html = fetch_post(url)
                    name = fetched_name or name
                    headline = fetched_headline
                    post_text = fetched_text
                    date_raw = fetched_date
                    time.sleep(0.8)
                except Exception:
                    pass
                author_type = classify_author(url, html, vanity)
                try:
                    append_row(
                        DATA_PATH,
                        {
                            "query": query,
                            "activity_id": activity_id,
                            "post_url": url,
                            "author_name": name,
                            "author_type": author_type,
                            "author_vanity": vanity,
                            "profile_url_guess": profile_url_for(author_type, vanity),
                            "headline": headline,
                            "post_snippet": hit["snippet"],
                            "post_text": post_text,
                            "date_raw": date_raw,
                            "fetched_at": now_iso(),
                        },
                    )
                    known.add(url)
                    if activity_id:
                        known.add(activity_id)
                    successful += 1
                except Exception:
                    failed += 1
                done += 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
        progress = done
        drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
        return 0
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
