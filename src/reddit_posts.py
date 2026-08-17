#!/usr/bin/env python3
import csv
import re
import sys
import time
import warnings
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from store import load_ids as load_id_set
from store import write_row

warnings.filterwarnings("ignore")

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "reddit_posts.csv"
FIELDS = [
    "query",
    "post_id",
    "post_url",
    "title",
    "post_text",
    "author",
    "author_url",
    "subreddit",
    "subreddit_url",
    "created_at",
    "outbound_url",
    "fetched_at",
]
STATUS_LINES = 9
SORTS = ("new", "relevance", "top", "hot", "comments")
TIMES = ("day", "week", "month", "year", "all")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}

try:
    import feedparser
except ImportError:
    feedparser = None

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
    return load_id_set(path, "post_id")


def append_row(path, row):
    write_row(path, FIELDS, row, "reddit_posts", "post_id", "post_text")


def strip_html(text):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def post_parts(url):
    match = re.search(r"reddit\.com/r/([^/]+)/comments/([^/]+)/?", url or "")
    if not match:
        return "", "", ""
    subreddit, post_id = match.group(1), match.group(2)
    return post_id, subreddit, f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/"


def author_name(entry):
    raw = (getattr(entry, "author", None) or "").strip()
    raw = re.sub(r"^(/u/|u/)", "", raw)
    return raw


def entry_body(entry):
    if getattr(entry, "content", None):
        return strip_html(entry.content[0].value)
    return strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))


def entry_date(entry):
    return (
        getattr(entry, "published", None)
        or getattr(entry, "updated", None)
        or ""
    )


def outbound_url(entry, post_url):
    link = getattr(entry, "link", "") or ""
    if link and "reddit.com" not in urlparse(link).netloc:
        return link
    return ""


def rss_urls(query):
    encoded = quote_plus(query)
    hosts = ("https://www.reddit.com", "https://old.reddit.com")
    urls = []
    for host in hosts:
        for sort in SORTS:
            for window in TIMES:
                urls.append(
                    f"{host}/search.rss?q={encoded}&sort={sort}&t={window}&type=link"
                )
    return urls


def fetch_feed(url):
    if requests is None or feedparser is None:
        raise RuntimeError("deps")
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return feedparser.parse(response.content)


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
        for url in rss_urls(query):
            if successful >= asked:
                break
            progress = done + 1
            drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
            try:
                feed = fetch_feed(url)
                time.sleep(1.2)
            except Exception:
                failed += 1
                done += 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                continue
            entries = list(getattr(feed, "entries", []) or [])
            if not entries:
                done += 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                continue
            for entry in entries:
                if successful >= asked:
                    break
                progress = done + 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                link = getattr(entry, "link", "") or ""
                post_id, subreddit, post_url = post_parts(link)
                if not post_id:
                    failed += 1
                    done += 1
                    drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                    continue
                if post_id in known:
                    duplicates += 1
                    done += 1
                    drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                    continue
                author = author_name(entry)
                try:
                    append_row(
                        DATA_PATH,
                        {
                            "query": query,
                            "post_id": post_id,
                            "post_url": post_url or link,
                            "title": getattr(entry, "title", "") or "",
                            "post_text": entry_body(entry),
                            "author": author,
                            "author_url": f"https://www.reddit.com/user/{author}" if author else "",
                            "subreddit": subreddit,
                            "subreddit_url": f"https://www.reddit.com/r/{subreddit}" if subreddit else "",
                            "created_at": entry_date(entry),
                            "outbound_url": outbound_url(entry, post_url),
                            "fetched_at": now_iso(),
                        },
                    )
                    known.add(post_id)
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
