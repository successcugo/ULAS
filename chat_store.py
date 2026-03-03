"""
chat_store.py — ULAS Advisor Chat
All chat persistence goes through this module.

Storage in ULASDATA:
  chat/global.json              — global room
  chat/school_{ABBR}.json       — per-school room
  chat/dm_{userA}_{userB}.json  — direct messages (users sorted alphabetically)
  chat/unread_{username}.json   — {room: last_seen_ts}

Message shape:
  { "id", "from", "display", "text", "ts", "file"? }
  file: { "name", "url", "mime", "size_kb" }
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from github_store import read_json, write_json

MAX_MESSAGES = 300
FUTO_TZ = timezone(timedelta(hours=1))

def _now_str():
    return datetime.now(FUTO_TZ).strftime("%Y-%m-%dT%H:%M:%S")

def _room_path(room):
    return f"chat/{room}.json"

def _unread_path(username):
    return f"chat/unread_{username}.json"

def dm_room(user_a, user_b):
    pair = sorted([user_a.lower(), user_b.lower()])
    return f"dm_{pair[0]}_{pair[1]}"

def school_room(school_abbr):
    return f"school_{school_abbr.upper()}"

def load_room(room):
    data, sha = read_json(_room_path(room))
    if data is None:
        return [], None
    return (data if isinstance(data, list) else []), sha

def post_message(room, from_user, display_name, text, file_info=None):
    messages, sha = load_room(room)
    msg = {
        "id":      uuid.uuid4().hex,
        "from":    from_user,
        "display": display_name,
        "text":    text.strip(),
        "ts":      _now_str(),
    }
    if file_info:
        msg["file"] = file_info
    messages.append(msg)
    if len(messages) > MAX_MESSAGES:
        messages = messages[-MAX_MESSAGES:]
    new_sha = write_json(_room_path(room), messages, f"chat:{from_user}>{room}", sha)
    return new_sha is not None

def delete_message(room, msg_id, requesting_user):
    messages, sha = load_room(room)
    target = next((m for m in messages if m["id"] == msg_id), None)
    if not target or target["from"] != requesting_user:
        return False
    messages = [m for m in messages if m["id"] != msg_id]
    return write_json(_room_path(room), messages, f"chat:del {msg_id[:8]}", sha) is not None

def get_unread(username):
    data, _ = read_json(_unread_path(username))
    return data if isinstance(data, dict) else {}

def mark_read(username, room):
    data, sha = read_json(_unread_path(username))
    counts = data if isinstance(data, dict) else {}
    counts[room] = _now_str()
    write_json(_unread_path(username), counts, f"read:{username}:{room}", sha)

def count_unread(messages, last_seen_ts):
    if not last_seen_ts:
        return len(messages)
    return sum(1 for m in messages if m.get("ts","") > last_seen_ts)

def build_display_name(username, school_abbr, dept_abbr):
    return f"{username} ({school_abbr}·{dept_abbr})"

def all_rooms_for_advisor(school_abbr):
    return {
        "global":                f"🌐 All FUTO",
        school_room(school_abbr): f"🏫 {school_abbr}",
    }
