import html
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from apollo import contact_list_names
from dataset_io import append_vote_row, refresh_apollo_state, skip_sets
from linkedin_posts import collect_posts, parse_exclude

app = FastAPI()
SESSIONS: dict[str, dict[str, Any]] = {}

REGIONS = [
    ("", "none"),
    ("xa-ar", "Arabia"),
    ("xa-en", "Arabia (en)"),
    ("ar-es", "Argentina"),
    ("au-en", "Australia"),
    ("at-de", "Austria"),
    ("be-fr", "Belgium (fr)"),
    ("be-nl", "Belgium (nl)"),
    ("br-pt", "Brazil"),
    ("bg-bg", "Bulgaria"),
    ("ca-en", "Canada"),
    ("ca-fr", "Canada (fr)"),
    ("ct-ca", "Catalan"),
    ("cl-es", "Chile"),
    ("cn-zh", "China"),
    ("co-es", "Colombia"),
    ("hr-hr", "Croatia"),
    ("cz-cs", "Czech Republic"),
    ("dk-da", "Denmark"),
    ("ee-et", "Estonia"),
    ("fi-fi", "Finland"),
    ("fr-fr", "France"),
    ("de-de", "Germany"),
    ("gr-el", "Greece"),
    ("hk-tzh", "Hong Kong"),
    ("hu-hu", "Hungary"),
    ("in-en", "India"),
    ("id-id", "Indonesia"),
    ("id-en", "Indonesia (en)"),
    ("ie-en", "Ireland"),
    ("il-he", "Israel"),
    ("it-it", "Italy"),
    ("jp-jp", "Japan"),
    ("kr-kr", "Korea"),
    ("lv-lv", "Latvia"),
    ("lt-lt", "Lithuania"),
    ("xl-es", "Latin America"),
    ("my-ms", "Malaysia"),
    ("my-en", "Malaysia (en)"),
    ("mx-es", "Mexico"),
    ("nl-nl", "Netherlands"),
    ("nz-en", "New Zealand"),
    ("no-no", "Norway"),
    ("pe-es", "Peru"),
    ("ph-en", "Philippines"),
    ("ph-tl", "Philippines (tl)"),
    ("pl-pl", "Poland"),
    ("pt-pt", "Portugal"),
    ("ro-ro", "Romania"),
    ("ru-ru", "Russia"),
    ("sg-en", "Singapore"),
    ("sk-sk", "Slovak Republic"),
    ("sl-sl", "Slovenia"),
    ("za-en", "South Africa"),
    ("es-es", "Spain"),
    ("se-sv", "Sweden"),
    ("ch-de", "Switzerland (de)"),
    ("ch-fr", "Switzerland (fr)"),
    ("ch-it", "Switzerland (it)"),
    ("tw-tzh", "Taiwan"),
    ("th-th", "Thailand"),
    ("tr-tr", "Turkey"),
    ("ua-uk", "Ukraine"),
    ("uk-en", "United Kingdom"),
    ("us-en", "United States"),
    ("ue-es", "United States (es)"),
    ("ve-es", "Venezuela"),
    ("vn-vi", "Vietnam"),
    ("wt-wt", "No region"),
]

TIMELINES = [("", "none"), ("d", "d"), ("w", "w"), ("m", "m"), ("y", "y")]


def _empty_session() -> dict[str, Any]:
    return {
        "rows": [],
        "index": 0,
        "list": "",
        "list_ready": False,
        "state_count": 0,
        "msg": "ready",
        "apollo_lists": [],
        "form": {
            "query": "",
            "count": "10",
            "timeline": "",
            "region": "",
            "exclude_text": "",
        },
    }


def _session_id(request: Request) -> str:
    sid = request.cookies.get("sid")
    if sid and sid in SESSIONS:
        return sid
    sid = secrets.token_urlsafe(16)
    SESSIONS[sid] = _empty_session()
    return sid


def _get_session(request: Request) -> dict[str, Any]:
    sid = _session_id(request)
    if sid not in SESSIONS:
        SESSIONS[sid] = _empty_session()
    return SESSIONS[sid]


def _ensure_lists(session: dict[str, Any]) -> None:
    if session.get("apollo_lists"):
        return
    try:
        session["apollo_lists"] = contact_list_names()
    except Exception:
        pass


def _select(name: str, options: list[tuple[str, str]], selected: str, extra: str = "") -> str:
    extra_attr = f" {extra}" if extra else ""
    parts = [f'<select name="{name}"{extra_attr}>']
    for value, label in options:
        val = html.escape(value, quote=True)
        text = html.escape(label)
        sel = " selected" if value == selected else ""
        parts.append(f'<option value="{val}"{sel}>{text}</option>')
    parts.append("</select>")
    return "".join(parts)


def _card(row: dict, index: int, total: int) -> str:
    if not row:
        return "<p>No posts in queue.</p>"
    profile = row.get("linkedin_url") or row.get("profile_url_guess") or ""
    post_url = row.get("post_url") or ""
    profile_html = (
        f'<p><a href="{html.escape(profile, quote=True)}" target="_blank" rel="noopener">profile</a></p>'
        if profile
        else "<p>no profile url</p>"
    )
    post_link = (
        f'<p><a href="{html.escape(post_url, quote=True)}" target="_blank" rel="noopener">post</a></p>'
        if post_url
        else ""
    )
    name = html.escape(row.get("author_name") or "")
    kind = html.escape(row.get("author_type") or "")
    return (
        f"<p><strong>{index + 1} / {total}</strong></p>"
        f"<h3>{name} ({kind})</h3>"
        f"{profile_html}{post_link}"
    )


def _page(request: Request, session: dict[str, Any]) -> HTMLResponse:
    _ensure_lists(session)
    rows = session.get("rows") or []
    idx = int(session.get("index") or 0)
    msg = session.get("msg") or ""
    form = session.get("form") or _empty_session()["form"]
    apollo_lists = session.get("apollo_lists") or []
    selected_list = session.get("list") or ""
    list_ready = bool(session.get("list_ready")) and bool(selected_list)
    state_count = int(session.get("state_count") or 0)
    card = _card(rows[idx], idx, len(rows)) if rows and idx < len(rows) else "<p>Nothing loaded. Fetch first.</p>"
    left = max(len(rows) - idx, 0) if rows else 0
    flash_html = f'<p class="flash">{html.escape(msg)}</p>' if msg else ""

    list_options = [("", "pick a list")]
    list_options.extend((name, name) for name in apollo_lists)
    list_select = _select("apollo_list", list_options, selected_list, extra='onchange="this.form.submit()"')
    region_select = _select("region", REGIONS, form.get("region", ""))
    timeline_select = _select("timeline", TIMELINES, form.get("timeline", ""))

    query_val = html.escape(form.get("query", ""), quote=True)
    count_val = html.escape(form.get("count", "10"), quote=True)
    exclude_val = html.escape(form.get("exclude_text", ""), quote=True)
    list_label = html.escape(selected_list)

    if list_ready:
        state_html = (
            f'<p class="ok">list <strong>{list_label}</strong> — '
            f"{state_count} members in apollo-state.csv</p>"
        )
        fetch_html = f"""
  <section>
    <h2>2. fetch posts</h2>
    <form method="post" action="/fetch">
      <div class="row">
        <div><label>query</label><input name="query" required placeholder="unsloth local finetune" value="{query_val}"/></div>
        <div><label>count</label><input name="count" type="number" min="1" value="{count_val}" required/></div>
      </div>
      <div class="row">
        <div><label>timeline</label>{timeline_select}</div>
        <div><label>region</label>{region_select}</div>
        <div><label>exclude</label><input name="exclude_text" placeholder="['phrase one', 'phrase two']" value="{exclude_val}"/></div>
      </div>
      <p><button class="fetch" type="submit">fetch</button></p>
    </form>
  </section>
"""
    else:
        state_html = "<p class=\"sub\">Pick a list. That loads current Apollo members into apollo-state.csv.</p>"
        fetch_html = "<section><h2>2. fetch posts</h2><p class=\"sub\">Select a list first.</p></section>"

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Apollo-Leads-GTM</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 24px auto; padding: 0 16px; background: #111; color: #eee; }}
    input, select, button {{ font: inherit; padding: 8px; margin: 4px 0; }}
    input, select {{ width: 100%; box-sizing: border-box; background: #222; color: #eee; border: 1px solid #444; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
    .card {{ border: 1px solid #333; padding: 16px; margin: 16px 0; background: #1a1a1a; }}
    .flash {{ color: #f9a825; }}
    .ok {{ color: #81c784; }}
    .actions {{ display: flex; gap: 12px; margin-top: 12px; }}
    .keep {{ background: #2e7d32; color: #fff; border: 0; cursor: pointer; }}
    .ignore {{ background: #c62828; color: #fff; border: 0; cursor: pointer; }}
    .later {{ background: #f9a825; color: #111; border: 0; cursor: pointer; }}
    .fetch, .load {{ background: #1565c0; color: #fff; border: 0; cursor: pointer; padding: 10px 16px; }}
    .refresh {{ background: #455a64; color: #fff; border: 0; cursor: pointer; padding: 8px 12px; }}
    label {{ display: block; font-size: 12px; color: #aaa; margin-top: 8px; }}
    h1 {{ margin-bottom: 4px; }}
    h2 {{ font-size: 16px; margin: 24px 0 8px; }}
    p.sub {{ color: #aaa; margin-top: 0; }}
    .top {{ display: flex; justify-content: flex-end; }}
  </style>
</head>
<body>
  <div class="top">
    <form method="post" action="/refresh-lists">
      <button class="refresh" type="submit">refresh lists</button>
    </form>
  </div>
  <h1>Apollo-Leads-GTM</h1>
  <p class="sub">Pick a list, then fetch LinkedIn posts. Vote Keep / Ignore / Later.</p>
  {flash_html}
  <section>
    <h2>1. list</h2>
    <form method="post" action="/select-list">
      <label>apollo list</label>
      {list_select}
      <p><button class="load" type="submit">load list</button></p>
    </form>
    {state_html}
  </section>
  {fetch_html}
  <div class="card">{card}</div>
  <p><strong>{left} left</strong></p>
  <form method="post" action="/vote" class="actions">
    <input type="hidden" name="choice" value="keep"/>
    <button class="keep" type="submit">Keep</button>
  </form>
  <form method="post" action="/vote" class="actions">
    <input type="hidden" name="choice" value="ignore"/>
    <button class="ignore" type="submit">Ignore</button>
  </form>
  <form method="post" action="/vote" class="actions">
    <input type="hidden" name="choice" value="later"/>
    <button class="later" type="submit">Later</button>
  </form>
</body>
</html>"""
    sid = _session_id(request)
    resp = HTMLResponse(body)
    if request.cookies.get("sid") != sid:
        resp.set_cookie("sid", sid, httponly=True, samesite="lax")
    return resp


def _save_form(session: dict[str, Any], **fields: str) -> None:
    form = session.setdefault("form", _empty_session()["form"])
    form.update(fields)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return _page(request, _get_session(request))


@app.post("/refresh-lists")
def refresh_lists(request: Request):
    session = _get_session(request)
    try:
        names = contact_list_names()
    except Exception as exc:
        session["msg"] = str(exc)[:220] or "apollo list refresh failed"
        return _page(request, session)
    session["apollo_lists"] = names
    if session.get("list") not in names:
        session["list"] = ""
        session["list_ready"] = False
        session["state_count"] = 0
    session["msg"] = f"loaded {len(names)} apollo lists"
    return _page(request, session)


@app.post("/select-list")
def select_list(request: Request, apollo_list: str = Form("")):
    session = _get_session(request)
    apollo_list = apollo_list.strip()
    if not apollo_list:
        session.update({"list": "", "list_ready": False, "state_count": 0, "rows": [], "index": 0, "msg": "pick a list"})
        return _page(request, session)
    try:
        name, count = refresh_apollo_state(apollo_list)
    except Exception as exc:
        session.update({"list": "", "list_ready": False, "state_count": 0, "msg": str(exc)[:220] or "list sync failed"})
        return _page(request, session)
    session.update(
        {
            "list": name,
            "list_ready": True,
            "state_count": count,
            "rows": [],
            "index": 0,
            "msg": f"synced {count} members for {name}",
        }
    )
    return _page(request, session)


@app.post("/fetch")
def fetch(
    request: Request,
    query: str = Form(""),
    count: str = Form("10"),
    timeline: str = Form(""),
    region: str = Form(""),
    exclude_text: str = Form(""),
):
    session = _get_session(request)
    query = query.strip()
    apollo_list = (session.get("list") or "").strip()
    timeline = timeline.strip() or None
    region = region.strip() or None
    _save_form(
        session,
        query=query,
        count=count.strip() or "10",
        timeline=timeline or "",
        region=region or "",
        exclude_text=exclude_text,
    )
    try:
        n = int(count)
    except ValueError:
        session["msg"] = "bad count"
        return _page(request, session)
    if not session.get("list_ready") or not apollo_list:
        session["msg"] = "pick a list first"
        return _page(request, session)
    if not query or n < 1:
        session["msg"] = "query and count required"
        return _page(request, session)
    try:
        excludes = parse_exclude(exclude_text) if exclude_text.strip() else []
        skip_posts, skip_keeps = skip_sets(apollo_list)
        rows = collect_posts(query, n, timeline, excludes, region, apollo_list, skip_posts, skip_keeps)
    except Exception:
        session.update({"rows": [], "index": 0, "msg": "fetch failed"})
        return _page(request, session)
    if not rows:
        session.update({"rows": [], "index": 0, "msg": "no new posts for this list"})
        return _page(request, session)
    session.update({"rows": rows, "index": 0, "msg": f"loaded {len(rows)} posts"})
    return _page(request, session)


@app.post("/vote")
def vote(request: Request, choice: str = Form("keep")):
    session = _get_session(request)
    rows = session.get("rows") or []
    idx = int(session.get("index") or 0)
    apollo_list = session.get("list") or ""
    if not rows or idx >= len(rows) or not apollo_list:
        session["msg"] = "queue empty"
        return _page(request, session)
    row = dict(rows[idx])
    row["vote"] = choice.strip().lower()
    row["voted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row["in_apollo"] = "n"
    try:
        append_vote_row(apollo_list, row)
    except Exception:
        session["msg"] = "vote upload failed"
        return _page(request, session)
    idx += 1
    session["index"] = idx
    if idx >= len(rows):
        session["msg"] = "done"
    else:
        session["msg"] = f"voted {choice}"
    return _page(request, session)
