"""
github_store.py
All interaction with GitHub repos (ULASDATA and LAVA) goes through this module.
Uses the GitHub Contents API for reading and writing files.
"""
from __future__ import annotations

import json
import base64
import urllib.request
import urllib.error
import streamlit as st
from typing import Any


# ── Secrets ───────────────────────────────────────────────────────────────────

def _pat() -> str:
    return st.secrets["GITHUB_PAT"]

def _data_repo() -> str:
    return f"{st.secrets['DATA_OWNER']}/{st.secrets['DATA_REPO']}"

def _lava_repo() -> str:
    return f"{st.secrets['LAVA_OWNER']}/{st.secrets['LAVA_REPO']}"

def _headers() -> dict:
    return {
        "Authorization": f"token {_pat()}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ── Low-level GET / PUT ───────────────────────────────────────────────────────

def _gh_get(repo: str, path: str) -> dict | None:
    """Fetch a file from GitHub. Returns dict with 'content' and 'sha', or None if not found."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _gh_put(repo: str, path: str, content_bytes: bytes, message: str, sha: str | None = None) -> bool:
    """Write (create or update) a file on GitHub. Returns True on success."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
    }
    if sha:
        payload["sha"] = sha
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        st.error(f"GitHub write error ({e.code}) for {path}: {e.read().decode()[:300]}")
        return False


def _gh_delete(repo: str, path: str, sha: str, message: str) -> bool:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {"message": message, "sha": sha}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="DELETE")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 204)
    except urllib.error.HTTPError:
        return False


# ── JSON helpers (ULASDATA repo) ──────────────────────────────────────────────

def read_json(path: str) -> tuple[dict | list | None, str | None]:
    """
    Read a JSON file from ULASDATA.
    Returns (parsed_data, sha) or (None, None) if not found.
    """
    result = _gh_get(_data_repo(), path)
    if result is None:
        return None, None
    raw = base64.b64decode(result["content"]).decode()
    return json.loads(raw), result["sha"]


def write_json(path: str, data: dict | list, message: str, sha: str | None = None) -> str | None:
    """
    Write a JSON file to ULASDATA.
    Returns new SHA on success, None on failure.
    Pass sha= for updates, omit for creates.
    Fetches current SHA automatically if not provided and file exists.
    """
    if sha is None:
        existing = _gh_get(_data_repo(), path)
        if existing:
            sha = existing["sha"]

    content = json.dumps(data, indent=2, default=str).encode()
    ok = _gh_put(_data_repo(), path, content, message, sha)
    if not ok:
        return None
    # Fetch new SHA
    result = _gh_get(_data_repo(), path)
    return result["sha"] if result else None


def delete_file(path: str, message: str) -> bool:
    """Delete a file from ULASDATA."""
    result = _gh_get(_data_repo(), path)
    if not result:
        return True  # already gone
    return _gh_delete(_data_repo(), path, result["sha"], message)


# ── CSV push to LAVA repo ─────────────────────────────────────────────────────

def push_csv_to_lava(lava_path: str, csv_content: str, message: str) -> tuple[bool, str]:
    """Push a CSV file to the LAVA repo. Returns (success, message)."""
    repo = _lava_repo()
    existing = _gh_get(repo, lava_path)
    sha = existing["sha"] if existing else None
    ok = _gh_put(repo, lava_path, csv_content.encode(), message, sha)
    if ok:
        return True, f"Pushed to LAVA: {lava_path}"
    return False, f"Failed to push to LAVA: {lava_path}"


# ── Cached reads (st.session_state) ──────────────────────────────────────────

def cached_read_json(cache_key: str, path: str, default=None):
    """
    Read from st.session_state cache first; fall back to GitHub.
    Stores both the data and SHA in session state.
    """
    sha_key = cache_key + "__sha"
    if cache_key not in st.session_state:
        data, sha = read_json(path)
        if data is None:
            data = default if default is not None else {}
        st.session_state[cache_key] = data
        st.session_state[sha_key] = sha
    return st.session_state[cache_key], st.session_state.get(sha_key)


def invalidate_cache(cache_key: str):
    """Force a re-fetch from GitHub on next cached_read_json call."""
    sha_key = cache_key + "__sha"
    st.session_state.pop(cache_key, None)
    st.session_state.pop(sha_key, None)


def write_and_update_cache(cache_key: str, path: str, data: dict | list, message: str) -> bool:
    """Write to GitHub and update local cache with new SHA."""
    sha_key = cache_key + "__sha"
    current_sha = st.session_state.get(sha_key)
    new_sha = write_json(path, data, message, sha=current_sha)
    if new_sha:
        st.session_state[cache_key] = data
        st.session_state[sha_key] = new_sha
        return True
    return False
