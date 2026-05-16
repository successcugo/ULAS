"""
github_db.py
All persistence is through the GitHub Contents API against successcugo/ULASDATA.
Every function reads from st.session_state cache first and writes back to GitHub
immediately on mutation.

File layout in ULASDATA:
  users/users.json          - all course rep accounts
  settings/settings.json    - TOKEN_LIFETIME, advisor accounts, etc.
  active/<key>.json         - live attendance sessions
  devicemap/<key>.json      - device→matric anti-cheat map (NOT in CSVs)
"""

import json
import base64
import urllib.request
import urllib.error
import streamlit as st

# ── Config from Streamlit secrets ─────────────────────────────────────────────
def _pat():
    return st.secrets["GITHUB_PAT"]

DATA_OWNER = "successcugo"
DATA_REPO  = "ULASDATA"
LAVA_OWNER = "successcugo"
LAVA_REPO  = "LAVA"

HEADERS = lambda: {
    "Authorization": f"token {_pat()}",
    "Accept": "application/vnd.github.v3+json",
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Low-level GitHub API ───────────────────────────────────────────────────────
def _api_url(owner, repo, path):
    return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"

def _gh_get(owner, repo, path):
    """Returns (content_dict, sha) or (None, None) if not found."""
    url = _api_url(owner, repo, path)
    req = urllib.request.Request(url, headers=HEADERS())
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content), data["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise
    except Exception as e:
        st.error(f"GitHub read error ({path}): {e}")
        return None, None

def _gh_put(owner, repo, path, content_dict, sha=None, message=None):
    """Write JSON to GitHub. Returns new sha or None on failure."""
    url = _api_url(owner, repo, path)
    encoded = base64.b64encode(
        json.dumps(content_dict, indent=2, ensure_ascii=False).encode()
    ).decode()
    payload = {
        "message": message or f"ULAS update: {path}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS(), method="PUT")
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read())
            return resp["content"]["sha"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        import sys; print(f"[ULAS] db write {e.code} {path}: {body[:200]}", file=sys.stderr)
        return None

def _gh_put_raw(owner, repo, path, raw_bytes, sha=None, message=None):
    """Write raw bytes (e.g. CSV) to GitHub."""
    url = _api_url(owner, repo, path)
    encoded = base64.b64encode(raw_bytes).decode()
    payload = {"message": message or f"ULAS: {path}", "content": encoded}
    if sha:
        payload["sha"] = sha
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS(), method="PUT")
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read())
            return resp["content"]["sha"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        import sys; print(f"[ULAS] db write {e.code} {path}: {body[:200]}", file=sys.stderr)
        return None

def _gh_delete(owner, repo, path, sha, message=None):
    url = _api_url(owner, repo, path)
    payload = {"message": message or f"ULAS delete: {path}", "sha": sha}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS(), method="DELETE")
    try:
        with urllib.request.urlopen(req):
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        import sys; print(f"[ULAS] db delete {e.code} {path}: {body[:200]}", file=sys.stderr)
        return False

# ── Cache helpers ──────────────────────────────────────────────────────────────
def _cache_key(path):
    return f"__ghcache__{path}"

def _sha_key(path):
    return f"__ghsha__{path}"

def _read(path, force=False):
    """Read from cache or GitHub."""
    ck = _cache_key(path)
    sk = _sha_key(path)
    if not force and ck in st.session_state:
        return st.session_state[ck], st.session_state.get(sk)
    content, sha = _gh_get(DATA_OWNER, DATA_REPO, path)
    st.session_state[ck] = content
    st.session_state[sk] = sha
    return content, sha
