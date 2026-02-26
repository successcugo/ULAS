"""
core.py — Business logic for ULAS.
All persistence goes through github_store.py.

Roles:
  'ict'     — Master account. Stored in Streamlit secrets, not in users.json.
              Can create/delete advisors and change any advisor's password.
  'advisor' — Per-department. Can manage reps in their own dept.
              Can change passwords of reps and co-advisors in their own dept.
  'rep'     — Per-level. Manages attendance sessions.
"""
from __future__ import annotations

import hashlib
import random
import csv
import io
from datetime import datetime, timezone, timedelta
from github_store import (
    cached_read_json, write_and_update_cache, invalidate_cache,
    read_json, write_json, delete_file, push_csv_to_lava,
)
from futo_data import get_school_abbr
# ── Timezone ──────────────────────────────────────────────────────────────────
FUTO_TZ = timezone(timedelta(hours=1))

def futo_now() -> datetime:
    return datetime.now(FUTO_TZ)

def futo_now_str() -> str:
    return futo_now().strftime("%Y-%m-%d %H:%M:%S")

def futo_ts() -> float:
    return futo_now().timestamp()


# ── Paths in ULASDATA ─────────────────────────────────────────────────────────
USERS_PATH    = "data/users.json"
SETTINGS_PATH = "data/settings.json"

def _session_path(school: str, department: str, level: str) -> str:
    safe = lambda s: s.replace("/","_").replace(" ","_").replace("(","").replace(")","")
    return f"sessions/{safe(school)}__{safe(department)}__{level}.json"

def _device_map_path(school: str, department: str, level: str, course_code: str) -> str:
    safe = lambda s: s.replace("/","_").replace(" ","_").replace("(","").replace(")","")
    return f"devices/{safe(school)}__{safe(department)}__{level}__{course_code.upper()}.json"


# ── Password ──────────────────────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def verify_password(pw: str, hashed: str) -> bool:
    return hash_password(pw) == hashed


# ── Settings ──────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "TOKEN_LIFETIME": 7,
    "dept_abbreviations": {},   # {"Department Name": "ABC", ...}
}

def load_settings() -> dict:
    data, _ = cached_read_json("__settings", SETTINGS_PATH, default=DEFAULT_SETTINGS)
    for k, v in DEFAULT_SETTINGS.items():
        data.setdefault(k, v)
    return data

def save_settings(data: dict) -> bool:
    return write_and_update_cache("__settings", SETTINGS_PATH, data, "Update settings")


# ── ICT master authentication (credentials live in Streamlit secrets) ─────────
def authenticate_ict(username: str, password: str,
                      expected_user: str, expected_pw: str) -> bool:
    """
    ICT master account. Pass in credentials from st.secrets in the calling app.
    Returns True if credentials match.
    """
    return (
        bool(expected_pw)
        and username == expected_user
        and password == expected_pw
    )


# ── Users (advisors + reps stored in ULASDATA) ───────────────────────────────
def load_users() -> dict:
    data, _ = cached_read_json("__users", USERS_PATH, default={})
    return data

def save_users(users: dict) -> bool:
    ok = write_and_update_cache("__users", USERS_PATH, users, "Update users")
    if ok:
        invalidate_cache("__users")
    return ok

def authenticate_user(username: str, password: str, role: str) -> dict | None:
    """Authenticate advisor or rep. role = 'rep' | 'advisor'"""
    users = load_users()
    u = users.get(username)
    if u and u.get("role") == role and verify_password(password, u["password_hash"]):
        return u
    return None

def username_exists(username: str) -> bool:
    return username in load_users()

def create_user(username: str, password: str, role: str, school: str,
                department: str, level: str | None, created_by: str) -> tuple[bool, str]:
    users = load_users()
    if username in users:
        return False, f"Username '{username}' already exists across FUTO."
    users[username] = {
        "username":      username,
        "password_hash": hash_password(password),
        "role":          role,
        "school":        school,
        "department":    department,
        "level":         level,
        "created_by":    created_by,
        "created_at":    futo_now_str(),
    }
    ok = save_users(users)
    return (True, "Created.") if ok else (False, "GitHub write failed.")

def update_password(username: str, new_password: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    users[username]["password_hash"] = hash_password(new_password)
    return save_users(users)

def delete_user(username: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    del users[username]
    return save_users(users)

def get_reps_for_dept(school: str, department: str) -> list[dict]:
    users = load_users()
    return [u for u in users.values()
            if u.get("role") == "rep"
            and u["school"] == school
            and u["department"] == department]

def get_advisors_for_dept(school: str, department: str) -> list[dict]:
    users = load_users()
    return [u for u in users.values()
            if u.get("role") == "advisor"
            and u["school"] == school
            and u["department"] == department]

def get_all_advisors() -> list[dict]:
    users = load_users()
    return [u for u in users.values() if u.get("role") == "advisor"]


# ── Token ─────────────────────────────────────────────────────────────────────
def generate_token() -> str:
    return f"{random.randint(0, 9999):04d}"


# ── Active Sessions ───────────────────────────────────────────────────────────
def load_session(school: str, department: str, level: str) -> tuple[dict | None, str | None]:
    path = _session_path(school, department, level)
    data, sha = read_json(path)
    return data, sha

def save_session(school: str, department: str, level: str,
                 session: dict, sha: str | None = None) -> str | None:
    path = _session_path(school, department, level)
    return write_json(
        path, session,
        f"Session update: {session.get('course_code','?')} {department} L{level}",
        sha,
    )

def delete_session(school: str, department: str, level: str) -> bool:
    path = _session_path(school, department, level)
    return delete_file(path, f"End session: {department} L{level}")

def start_session(school: str, department: str, level: str,
                  course_code: str, rep_username: str) -> tuple[dict, str | None]:
    now = futo_now()
    session = {
        "school":              school,
        "department":          department,
        "level":               level,
        "course_code":         course_code.upper().strip(),
        "rep_username":        rep_username,
        "started_at":          now.isoformat(),
        "token":               generate_token(),
        "token_generated_at":  futo_ts(),
        "entries":             [],
        "next_sn":             1,
    }
    sha = save_session(school, department, level, session)
    return session, sha

def refresh_token(session: dict, lifetime: int) -> tuple[dict, bool]:
    age = futo_ts() - session["token_generated_at"]
    if age >= lifetime:
        session["token"]               = generate_token()
        session["token_generated_at"]  = futo_ts()
        return session, True
    return session, False

def token_remaining(session: dict, lifetime: int) -> float:
    age = futo_ts() - session["token_generated_at"]
    return max(0.0, lifetime - age)

def validate_token(session: dict, code: str, lifetime: int) -> bool:
    age = futo_ts() - session["token_generated_at"]
    if age >= lifetime:
        return False
    return session["token"] == code.strip()


# ── Entries ───────────────────────────────────────────────────────────────────
def _name_dup(entries, surname, other_names, exclude_sn=None):
    for e in entries:
        if exclude_sn and e["sn"] == exclude_sn:
            continue
        if (e["surname"].lower()     == surname.strip().lower() and
                e["other_names"].lower() == other_names.strip().lower()):
            return True
    return False

def _matric_dup(entries, matric, exclude_sn=None):
    for e in entries:
        if exclude_sn and e["sn"] == exclude_sn:
            continue
        if e["matric"] == matric.strip():
            return True
    return False

def validate_matric(matric: str) -> tuple[bool, str]:
    m = matric.strip()
    if not m.isdigit():
        return False, "Matric number must contain digits only — no letters or spaces."
    if len(m) != 11:
        return False, f"Matric number must be exactly 11 digits (you entered {len(m)})."
    return True, ""

def add_entry(session: dict, surname: str, other_names: str, matric: str) -> tuple[bool, str]:
    if _name_dup(session["entries"], surname, other_names):
        return False, "A student with this name is already in the attendance."
    if _matric_dup(session["entries"], matric):
        return False, "This matric number is already in the attendance."
    session["entries"].append({
        "sn":          session["next_sn"],
        "surname":     surname.strip().upper(),
        "other_names": other_names.strip().title(),
        "matric":      matric.strip(),
        "time":        futo_now_str(),
    })
    session["next_sn"] += 1
    return True, "Entry recorded."

def edit_entry(session: dict, sn: int, surname: str, other_names: str, matric: str) -> tuple[bool, str]:
    if _name_dup(session["entries"], surname, other_names, exclude_sn=sn):
        return False, "Another entry already has this name."
    if _matric_dup(session["entries"], matric, exclude_sn=sn):
        return False, "Another entry already has this matric number."
    for e in session["entries"]:
        if e["sn"] == sn:
            e["surname"]     = surname.strip().upper()
            e["other_names"] = other_names.strip().title()
            e["matric"]      = matric.strip()
            return True, "Entry updated."
    return False, "Entry not found."

def delete_entry(session: dict, sn: int) -> tuple[bool, str]:
    for i, e in enumerate(session["entries"]):
        if e["sn"] == sn:
            session["entries"].pop(i)
            return True, "Entry removed."
    return False, "Entry not found."


# ── Device map (anti-cheat) ───────────────────────────────────────────────────
def check_and_register_device(school, department, level,
                               course_code, device_id, matric) -> tuple[bool, str]:
    if not device_id:
        return True, ""
    path = _device_map_path(school, department, level, course_code)
    dm, sha = read_json(path)
    if dm is None:
        dm = {}
    existing = dm.get(device_id)
    if existing and existing != matric.strip():
        return False, "This device has already been used to sign attendance for this class."
    dm[device_id] = matric.strip()
    write_json(path, dm, f"Device map: {course_code} {department} L{level}", sha)
    return True, ""


# ── CSV / LAVA ────────────────────────────────────────────────────────────────
def session_to_csv(session: dict) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["S/N", "Surname", "Other Names", "Matric Number", "Time"],
    )
    writer.writeheader()
    for e in session["entries"]:
        writer.writerow({
            "S/N":          e["sn"],
            "Surname":      e["surname"],
            "Other Names":  e["other_names"],
            "Matric Number": e["matric"],
            "Time":         e["time"],
        })
    return output.getvalue()

def get_dept_abbreviation(department: str) -> str:
    """Return the advisor-set abbreviation for a department, or a fallback."""
    settings = load_settings()
    abbrevs  = settings.get("dept_abbreviations", {})
    if department in abbrevs and abbrevs[department].strip():
        return abbrevs[department].strip().upper()
    # Fallback: first 3 letters of each word, max 3 chars total
    words = department.replace("(", "").replace(")", "").split()
    return "".join(w[0] for w in words)[:3].upper()

def set_dept_abbreviation(department: str, abbreviation: str) -> bool:
    """Save the abbreviation for a department to settings."""
    settings = load_settings()
    settings.setdefault("dept_abbreviations", {})
    settings["dept_abbreviations"][department] = abbreviation.strip().upper()
    return save_settings(settings)

def build_csv_filename(session: dict) -> str:
    """New format: SCHOOL+COURSECODE+DEPTABBR+LEVEL+DATE.csv"""
    school_abbr = get_school_abbr(session["school"])
    dept_abbr   = get_dept_abbreviation(session["department"])
    level       = session["level"]
    started     = datetime.fromisoformat(session["started_at"])
    date_str    = started.strftime("%Y-%m-%d")
    course      = session["course_code"]
    return f"{school_abbr}{course}{dept_abbr}{level}_{date_str}.csv"

def push_attendance_to_lava(session: dict) -> tuple[bool, str]:
    """Push CSV to attendances/(date)/filename.csv"""
    started  = datetime.fromisoformat(session["started_at"])
    date_str = started.strftime("%Y-%m-%d")
    filename = build_csv_filename(session)
    lava_path   = f"attendances/{date_str}/{filename}"
    csv_content = session_to_csv(session)
    commit_msg  = (
        f"Attendance: {session['course_code']} | "
        f"{session['department']} | Level {session['level']} | "
        f"{date_str}"
    )
    return push_csv_to_lava(lava_path, csv_content, commit_msg)
