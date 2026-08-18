import os

from env import load_env

DEFAULT_DATASET_ID = "Lexsi/Apollo-Leads-Lists"


def hf_token():
    load_env()
    key = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if not key or key == "XXX":
        raise RuntimeError("HF_TOKEN")
    return key


def dataset_id():
    load_env()
    return (os.environ.get("HF_DATASET_ID") or DEFAULT_DATASET_ID).strip()
