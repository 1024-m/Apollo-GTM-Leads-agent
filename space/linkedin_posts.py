#!/usr/bin/env python3
import argparse
import ast
import csv
import re
import sys
import time
import warnings
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from apollo import require_list
from dataset_io import skip_sets, norm_linkedin
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
    "linkedin_url",
    "headline",
    "post_snippet",
    "post_text",
    "date_raw",
    "fetched_at",
    "apollo_list",
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
    write_row(path, FIELDS, row)


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


def is_posts_url(url):
    path = (urlparse(url).path or "").lower()
    if "/pulse/" in path or "/newsletters/" in path or "/feed/" in path:
        return False
    match = re.search(r"/posts/([^/?#]+)", path)
    return bool(match and match.group(1))


def vanity_from_url(url):
    match = re.search(r"/posts/([^/?#]+)", urlparse(url).path or "")
    if not match:
        return ""
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


def minus_terms(excludes):
    parts = [f'-"{item}"' for item in excludes if item]
    return (" " + " ".join(parts)) if parts else ""


def query_variants(query, excludes):
    extra = minus_terms(excludes)
    return [
        f"site:linkedin.com/posts {query}{extra}",
        f'site:linkedin.com/posts "{query}"{extra}',
    ]


def search(query, limit, timeline=None, region=None):
    if DDGS is None:
        raise RuntimeError("ddgs")
    hits = []
    client = DDGS()
    kwargs = {"max_results": limit}
    if timeline:
        kwargs["timelimit"] = timeline
    if region:
        kwargs["region"] = region
    for item in client.text(query, **kwargs):
        url = clean_url(item.get("href") or item.get("url") or "")
        if "linkedin.com" not in url or not is_posts_url(url):
            continue
        hits.append(
            {
                "url": url,
                "title": item.get("title") or "",
                "snippet": item.get("body") or item.get("description") or "",
            }
        )
    return hits


def build_row(query, hit, apollo_list):
    url = hit["url"]
    activity_id = activity_id_from_url(url)
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
    return {
        "query": query,
        "activity_id": activity_id,
        "post_url": url,
        "author_name": name,
        "author_type": author_type,
        "author_vanity": vanity,
        "linkedin_url": profile_url_for(author_type, vanity),
        "headline": headline,
        "post_snippet": hit["snippet"],
        "post_text": post_text,
        "date_raw": date_raw,
        "fetched_at": now_iso(),
        "apollo_list": apollo_list,
    }


def collect_posts(query, asked, timeline, excludes, region, apollo_list, skip_post_urls=None, skip_keep_profiles=None):
    skip_post_urls = skip_post_urls or set()
    skip_keep_profiles = skip_keep_profiles or set()
    rows = []
    seen = set(skip_post_urls)
    done = 0
    for variant in query_variants(query, excludes):
        remaining = asked - done
        if remaining <= 0:
            break
        try:
            hits = search(variant, remaining, timeline=timeline, region=region)[:remaining]
        except Exception:
            done += 1
            continue
        for hit in hits:
            if done >= asked:
                break
            url = hit["url"]
            if not is_posts_url(url):
                continue
            activity_id = activity_id_from_url(url)
            if url in seen or (activity_id and activity_id in seen):
                done += 1
                continue
            row = build_row(query, hit, apollo_list)
            profile = row.get("linkedin_url") or ""
            if (norm_linkedin(profile) or profile) in skip_keep_profiles:
                seen.add(url)
                if activity_id:
                    seen.add(activity_id)
                done += 1
                continue
            rows.append(row)
            seen.add(url)
            if activity_id:
                seen.add(activity_id)
            done += 1
    return rows


def parse_exclude(value):
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, list):
        raise ValueError
    return [str(item).strip() for item in parsed if str(item).strip()]


def parse_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("query")
    parser.add_argument("count", type=int)
    parser.add_argument("--timeline", choices=["d", "w", "m", "y"], default=None)
    parser.add_argument("--exclude", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--list", dest="apollo_list", required=True)
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        return None
    if args.count < 0:
        return None
    apollo_list = args.apollo_list.strip()
    if not apollo_list:
        return None
    excludes = []
    if args.exclude is not None:
        try:
            excludes = parse_exclude(args.exclude)
        except (ValueError, SyntaxError):
            return None
    return args.query, args.count, args.timeline, excludes, args.region, apollo_list


def main():
    parsed = parse_args(sys.argv)
    if parsed is None:
        return 2
    query, asked, timeline, excludes, region, apollo_list = parsed
    if asked == 0:
        return 0
    try:
        require_list(apollo_list)
        skip_posts, skip_keeps = skip_sets(apollo_list)
    except Exception:
        return 2
    successful = 0
    failed = 0
    duplicates = 0
    done = 0
    progress = 0
    drawn = False
    sys.stdout.write("\033[?25l")
    try:
        drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
        seen = set(skip_posts)
        for variant in query_variants(query, excludes):
            remaining = asked - done
            if remaining <= 0:
                break
            try:
                hits = search(variant, remaining, timeline=timeline, region=region)[:remaining]
            except Exception:
                failed += 1
                done += 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                continue
            for hit in hits:
                if done >= asked:
                    break
                progress = done + 1
                drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                url = hit["url"]
                if not is_posts_url(url):
                    continue
                activity_id = activity_id_from_url(url)
                if url in seen or (activity_id and activity_id in seen):
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
                profile = profile_url_for(author_type, vanity)
                if profile and (norm_linkedin(profile) or profile) in skip_keeps:
                    duplicates += 1
                    seen.add(url)
                    if activity_id:
                        seen.add(activity_id)
                    done += 1
                    drawn = draw(asked, progress, done, successful, failed, duplicates, drawn)
                    continue
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
                            "linkedin_url": profile,
                            "headline": headline,
                            "post_snippet": hit["snippet"],
                            "post_text": post_text,
                            "date_raw": date_raw,
                            "fetched_at": now_iso(),
                            "apollo_list": apollo_list,
                        },
                    )
                    seen.add(url)
                    if activity_id:
                        seen.add(activity_id)
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
