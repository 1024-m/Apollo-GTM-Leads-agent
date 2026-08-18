import os

from env import load_env

try:
    import requests
except ImportError:
    requests = None

LABELS_URL = "https://api.apollo.io/api/v1/labels"
CONTACTS_URL = "https://api.apollo.io/api/v1/contacts"
CONTACTS_SEARCH_URL = "https://api.apollo.io/api/v1/contacts/search"
ADD_TO_LIST_URL = "https://api.apollo.io/api/v1/labels/add_entity_ids_to_label_names"


def _headers():
    return {
        "x-api-key": api_key(),
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }


def _error_text(response):
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        return (payload.get("error") or payload.get("message") or "").strip() or response.text
    return (response.text or "").strip()


def _request(method, url, **kwargs):
    if requests is None:
        raise RuntimeError("requests")
    timeout = kwargs.pop("timeout", 30)
    response = requests.request(method, url, headers=_headers(), timeout=timeout, **kwargs)
    if not response.ok:
        raise RuntimeError(f"{response.status_code} {_error_text(response)}".strip())
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception:
        return {}


def api_key():
    load_env()
    key = (os.environ.get("APOLLO_API_KEY") or "").strip()
    if not key or key == "XXX":
        raise RuntimeError("APOLLO_API_KEY")
    return key


def contact_lists():
    payload = _request("GET", LABELS_URL)
    rows = payload if isinstance(payload, list) else payload.get("labels") or payload.get("tags") or []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (row.get("modality") or "").lower() != "contacts":
            continue
        name = (row.get("name") or "").strip()
        list_id = (row.get("id") or row.get("_id") or "").strip()
        if name and list_id:
            out.append({"id": list_id, "name": name})
    return out


def contact_list_names():
    return [row["name"] for row in contact_lists()]


def contact_list_id(name):
    wanted = require_list(name)
    for row in contact_lists():
        if row["name"] == wanted:
            return row["id"]
    raise RuntimeError("list")


def search_contacts_page(page=1, per_page=100, keywords="", label_ids=None):
    body = {"page": page, "per_page": per_page}
    if (keywords or "").strip():
        body["q_keywords"] = keywords.strip()
    if label_ids:
        body["contact_label_ids"] = list(label_ids)
    payload = _request("POST", CONTACTS_SEARCH_URL, json=body)
    rows = payload.get("contacts") or []
    pagination = payload.get("pagination") or {}
    return [row for row in rows if isinstance(row, dict)], pagination


def list_contacts_on_list(name):
    label_id = contact_list_id(name)
    page = 1
    out = []
    while page <= 500:
        rows, pagination = search_contacts_page(page=page, per_page=100, label_ids=[label_id])
        out.extend(rows)
        total_pages = int(pagination.get("total_pages") or 1)
        if page >= total_pages or not rows:
            break
        page += 1
    return out


def require_list(name):
    wanted = (name or "").strip()
    if not wanted:
        raise RuntimeError("list")
    names = contact_list_names()
    if wanted not in names:
        raise RuntimeError("list")
    return wanted


def create_contact_list(name):
    wanted = (name or "").strip()
    if not wanted:
        raise RuntimeError("list")
    return _request("POST", LABELS_URL, json={"name": wanted, "modality": "contacts"})


def search_contacts(keywords, per_page=25):
    rows, _pagination = search_contacts_page(page=1, per_page=per_page, keywords=keywords)
    return rows


def create_contact(name, linkedin_url, title=""):
    if requests is None:
        raise RuntimeError("requests")
    linkedin_url = (linkedin_url or "").strip()
    if not linkedin_url:
        raise RuntimeError("linkedin_url")
    parts = (name or "").strip().split()
    first = parts[0] if parts else "Unknown"
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    body = {
        "first_name": first,
        "last_name": last,
        "name": (name or "").strip() or first,
        "linkedin_url": linkedin_url,
        "run_dedupe": True,
    }
    if (title or "").strip():
        body["title"] = title.strip()
    payload = _request("POST", CONTACTS_URL, json=body)
    contact = payload.get("contact") if isinstance(payload, dict) else payload
    if not isinstance(contact, dict) or not contact.get("id"):
        raise RuntimeError("contact")
    return contact


def add_contacts_to_list(list_name, entity_ids):
    if requests is None:
        raise RuntimeError("requests")
    wanted = (list_name or "").strip()
    ids = [item for item in entity_ids if item]
    if not wanted or not ids:
        raise RuntimeError("list")
    return _request(
        "POST",
        ADD_TO_LIST_URL,
        json={"entity_ids": ids, "label_names": [wanted], "modality": "contacts"},
        timeout=60,
    )
