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
from futo_data import get_school_abbr, get_full_structure, save_structure, invalidate_structure_cache
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
    "BEACON_RANGE":   100,          # metres — how close student must be to rep beacon
    "dept_abbreviations": {},       # {"Department Name": "ABC", ...}
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

# ── GPS / Beacon ─────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in metres between two GPS coordinates."""
    import math
    R = 6_371_000  # Earth radius in metres
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def set_beacon(school: str, department: str, level: str,
               lat: float, lon: float, accuracy: float = 0.0) -> tuple[bool, str]:
    """
    Write the rep's GPS coordinates into the active session as the beacon.
    accuracy = GPS accuracy radius in metres at the time of setting.
    Returns (ok, message).
    """
    session, sha = load_session(school, department, level)
    if not session:
        return False, "No active session found."
    session["beacon_lat"]      = lat
    session["beacon_lon"]      = lon
    session["beacon_accuracy"] = accuracy   # stored so verify can factor it in
    session["beacon_set_at"]   = futo_now_str()
    new_sha = save_session(school, department, level, session, sha)
    if not new_sha:
        return False, "Could not save beacon — GitHub write failed."
    return True, f"Beacon set at {lat:.5f}, {lon:.5f}"


# Maximum metres we will ever add to BEACON_RANGE for GPS uncertainty.
_BEACON_ACC_CAP = 12

def verify_beacon(student_lat: float, student_lon: float,
                  session: dict, student_accuracy: float = 0.0) -> tuple[bool, str]:
    """
    Check whether a student is within BEACON_RANGE of the rep beacon.

    Tolerance padding rules (prevents campus-wide false passes):
      - We add at most _BEACON_ACC_CAP metres of padding total.
      - If either device reports accuracy worse than BEACON_RANGE we add no
        padding at all — the reading is too coarse to be useful for cheating
        detection, so we hold the hard line.
      - Otherwise we add min(beacon_acc, student_acc, _BEACON_ACC_CAP).

    Returns (allowed, message).
    """
    b_lat = session.get("beacon_lat")
    b_lon = session.get("beacon_lon")
    if b_lat is None or b_lon is None:
        return False, "Beacon not set yet. Ask your course rep to activate the beacon first."

    dist_m     = haversine_m(student_lat, student_lon, float(b_lat), float(b_lon))
    rng        = load_settings().get("BEACON_RANGE", 100)
    beacon_acc = float(session.get("beacon_accuracy") or 0)

    # Only apply padding when both readings are reasonably precise
    if beacon_acc <= rng and student_accuracy <= rng:
        padding = min(beacon_acc, student_accuracy, _BEACON_ACC_CAP)
    else:
        padding = 0

    effective = rng + padding

    if dist_m <= effective:
        return True, f"Location verified ({dist_m:.0f}m from beacon)"
    return False, (
        f"You are too far from the lecture venue ({dist_m:.0f}m away, "
        f"maximum allowed is {rng}m). "
        f"Make sure you are physically present in the lecture room."
    )


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
        "beacon_lat":          None,
        "beacon_lon":          None,
        "beacon_set_at":       None,
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
        fieldnames=["S/N", "Surname", "Other Names", "Matric Number", "Time", "Session Started"],
    )
    writer.writeheader()
    for e in session["entries"]:
        writer.writerow({
            "S/N":          e["sn"],
            "Surname":      e["surname"],
            "Other Names":  e["other_names"],
            "Matric Number": e["matric"],
            "Time":         e["time"],
            "Session Started": datetime.fromisoformat(session["started_at"]).strftime("%H:%M:%S"),
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
    """Format: {SCHOOLABBR}{DEPTABBR}{LEVEL}_{SESSION}+{SEMESTER}_{COURSE}_{DATE}.csv
    e.g. ESETCPE300_2025-2026+FirstSemester_CPE301_2026-02-26.csv
    Session slashes replaced with hyphens; spaces stripped from semester name.
    """
    school_abbr  = get_school_abbr(session["school"])
    dept_abbr    = get_dept_abbreviation(session["department"])
    level        = session["level"]
    started      = datetime.fromisoformat(session["started_at"])
    date_str     = started.strftime("%Y-%m-%d")
    course       = session["course_code"]
    sem          = load_active_semester() or {}
    sem_session  = sem.get("session", "UnknownSession").replace("/", "-")
    sem_name     = sem.get("name", "UnknownSemester").replace(" ", "")
    return f"{school_abbr}{dept_abbr}{level}_{sem_session}+{sem_name}_{course}_{date_str}.csv"

# ── Rep Session History ───────────────────────────────────────────────────────
def _history_path(username: str) -> str:
    return f"history/{username}.json"

def append_session_history(session: dict) -> None:
    """Append a completed session summary to the rep's history log."""
    path = _history_path(session["rep_username"])
    existing, sha = read_json(path)
    records = existing if isinstance(existing, list) else []
    records.append({
        "course_code": session["course_code"],
        "level":       session["level"],
        "date":        datetime.fromisoformat(session["started_at"]).strftime("%Y-%m-%d"),
        "started_at":  session["started_at"][11:16],
        "entries":     len(session["entries"]),
        "pushed_at":   futo_now().strftime("%Y-%m-%d %H:%M"),
    })
    # Keep last 50 sessions only
    records = records[-50:]
    write_json(path, records, f"History: {session['course_code']} pushed", sha)

def load_session_history(username: str) -> list:
    """Return the rep's session history list, newest first."""
    path = _history_path(username)
    data, _ = read_json(path)
    if isinstance(data, list):
        return list(reversed(data))
    return []


def push_attendance_to_lava(session: dict) -> tuple[bool, str]:
    """Push CSV to attendances/{session}/{semester}/{date}/filename.csv"""
    sem      = load_active_semester() or {}
    started  = datetime.fromisoformat(session["started_at"])
    date_str = started.strftime("%Y-%m-%d")
    filename = build_csv_filename(session)

    # Safe path segments — no slashes or spaces
    sem_session  = sem.get("session", "UnknownSession").replace("/", "-")
    sem_name     = sem.get("name",    "UnknownSemester").replace(" ", "")
    lava_path    = f"attendances/{sem_session}/{sem_name}/{date_str}/{filename}"
    csv_content  = session_to_csv(session)
    commit_msg   = (
        f"Attendance: {session['course_code']} | "
        f"{session['department']} | Level {session['level']} | "
        f"{sem_session} {sem_name} | {date_str}"
    )
    ok, msg = push_csv_to_lava(lava_path, csv_content, commit_msg)
    if ok:
        try:
            append_session_history(session)
        except Exception:
            pass
    return ok, msg


# ── Semester management ───────────────────────────────────────────────────────
SEMESTER_ACTIVE_PATH  = "semesters/active.json"
SEMESTER_HISTORY_PATH = "semesters/history.json"

def load_active_semester() -> dict | None:
    """Return the active semester dict or None if no semester is running."""
    data, _ = read_json(SEMESTER_ACTIVE_PATH)
    return data if data else None

def start_semester(name: str, session: str, started_by: str) -> tuple[bool, str]:
    """
    Start a new semester. name = 'First Semester' | 'Second Semester'.
    session = '2025/2026'. Returns (ok, message).
    """
    existing = load_active_semester()
    if existing:
        return False, (
            f"A semester is already active: "
            f"{existing['name']} {existing['session']}. "
            f"End it before starting a new one."
        )
    sem = {
        "name":         name.strip(),
        "session":      session.strip(),
        "label":        f"{name.strip()} {session.strip()}",
        "started_at":   futo_now_str(),
        "started_by":   started_by,
    }
    new_sha = write_json(SEMESTER_ACTIVE_PATH, sem, f"Start semester: {sem['label']}")
    if not new_sha:
        return False, "GitHub write failed."
    invalidate_cache("__active_semester")
    # Create LAVA directory scaffold immediately so the folder exists in LAVA
    sem_session = session.strip().replace("/", "-")
    sem_name    = name.strip().replace(" ", "")
    lava_keep   = f"attendances/{sem_session}/{sem_name}/.gitkeep"
    # GitHub requires non-empty file content
    keep_content = (
        f"# ULAS — {sem['label']}\n"
        f"# Session: {session.strip()}\n"
        f"# Created: {sem['started_at']}\n"
        f"# Attendance records for this semester will appear in this folder.\n"
    )
    scaffold_ok, scaffold_msg = push_csv_to_lava(lava_keep, keep_content, f"Init: {sem['label']}")
    if not scaffold_ok:
        # Semester record already saved — return success but warn about folder
        return True, (
            f"Semester started: {sem['label']} "
            f"(warning: could not create LAVA folder — {scaffold_msg})"
        )
    return True, f"Semester started: {sem['label']}"

def end_semester(ended_by: str) -> tuple[bool, str]:
    """End the current active semester and archive it."""
    sem, sha = read_json(SEMESTER_ACTIVE_PATH)
    if not sem:
        return False, "No active semester to end."
    sem["ended_at"]  = futo_now_str()
    sem["ended_by"]  = ended_by
    # Archive to history
    hist, h_sha = read_json(SEMESTER_HISTORY_PATH)
    history = hist if isinstance(hist, list) else []
    history.append(sem)
    write_json(SEMESTER_HISTORY_PATH, history,
               f"Archive semester: {sem.get('label','')}", h_sha)
    # Delete active file
    ok = delete_file(SEMESTER_ACTIVE_PATH, f"End semester: {sem.get('label','')}")
    if not ok:
        return False, "GitHub write failed."
    invalidate_cache("__active_semester")
    return True, f"Semester ended: {sem.get('label','')}"

def load_semester_history() -> list:
    data, _ = read_json(SEMESTER_HISTORY_PATH)
    return list(reversed(data)) if isinstance(data, list) else []


# ── LAVA path helpers ────────────────────────────────────────────────────────
def lava_sem_path(sem_record: dict) -> str:
    """Return the LAVA path prefix for a given semester record."""
    sem_session = sem_record.get("session", "").replace("/", "-")
    sem_name    = sem_record.get("name",    "").replace(" ", "")
    return f"attendances/{sem_session}/{sem_name}"

def get_available_sessions() -> list[str]:
    """
    Return sorted list of unique academic sessions from semester history + active.
    e.g. ['2024-2025', '2025-2026']
    """
    sems = load_semester_history()
    active = load_active_semester()
    if active:
        sems = [active] + sems
    seen = []
    for s in sems:
        v = s.get("session", "").replace("/", "-")
        if v and v not in seen:
            seen.append(v)
    return sorted(seen)

def get_semesters_for_session(session_str: str) -> list[dict]:
    """
    Return semester records (active + history) that belong to a given session.
    session_str is already slash-free e.g. '2025-2026'.
    """
    sems = load_semester_history()
    active = load_active_semester()
    if active:
        sems = [active] + sems
    return [s for s in sems if s.get("session", "").replace("/", "-") == session_str]


# ── GPA / CGPA ────────────────────────────────────────────────────────────────
def _gpa_path(matric: str) -> str:
    return f"gpa/{matric.strip()}.json"

def load_student_gpa(matric: str) -> list:
    """Return list of semester GPA records for a student, oldest first."""
    data, _ = read_json(_gpa_path(matric))
    return data if isinstance(data, list) else []

def assign_semester_gpa(
    matric: str,
    gpa_value: float,
    advisor_username: str,
    advisor_dept: str,
) -> tuple[bool, str]:
    """
    Assign a GPA for the current active semester to a student.
    Overwrites if the same semester label already exists (advisor correction).
    """
    sem = load_active_semester()
    if not sem:
        return False, "No active semester. ICT must start a semester first."

    label = sem["label"]
    records = load_student_gpa(matric)
    existing_sha = read_json(_gpa_path(matric))[1]

    # Overwrite existing record for this semester if present
    for r in records:
        if r.get("semester") == label:
            r["gpa"]          = round(float(gpa_value), 2)
            r["assigned_by"]  = advisor_username
            r["assigned_at"]  = futo_now_str()
            r["dept"]         = advisor_dept
            new_sha = write_json(
                _gpa_path(matric), records,
                f"GPA update: {matric} {label}", existing_sha
            )
            return (True, f"GPA updated for {matric} — {label}") if new_sha \
                   else (False, "GitHub write failed.")

    # New record
    records.append({
        "semester":    label,
        "session":     sem["session"],
        "gpa":         round(float(gpa_value), 2),
        "assigned_by": advisor_username,
        "assigned_at": futo_now_str(),
        "dept":        advisor_dept,
    })
    new_sha = write_json(
        _gpa_path(matric), records,
        f"GPA assign: {matric} {label}", existing_sha
    )
    return (True, f"GPA recorded for {matric} — {label}") if new_sha \
           else (False, "GitHub write failed.")

def compute_cgpa(records: list) -> float:
    """Average of all semester GPAs."""
    if not records:
        return 0.0
    return round(sum(r["gpa"] for r in records) / len(records), 2)

def get_dept_matric_numbers(school: str, department: str) -> list[str]:
    """
    Scan LAVA CSVs for matric numbers belonging to this dept.
    Returns a sorted deduplicated list.
    """
    import base64
    from github_store import _gh_get, _lava_repo

    matric_set: set[str] = set()
    school_abbr = get_school_abbr(school)
    dept_abbr   = get_dept_abbreviation(department)
    prefix      = f"{school_abbr}{dept_abbr}"

    try:
        repo         = _lava_repo()
        folders_raw  = _gh_get(repo, "attendances")
        if not folders_raw or not isinstance(folders_raw, list):
            return []
        for folder in folders_raw:
            if folder.get("type") != "dir":
                continue
            files = _gh_get(repo, f"attendances/{folder['name']}")
            if not files:
                continue
            for f in files:
                fname = f.get("name", "")
                if not fname.endswith(".csv") or not fname.startswith(prefix):
                    continue
                raw = _gh_get(repo, f"attendances/{folder['name']}/{fname}")
                if not raw:
                    continue
                content = base64.b64decode(raw["content"]).decode()
                for line in content.splitlines()[1:]:
                    parts = line.split(",")
                    if len(parts) >= 4:
                        matric_set.add(parts[3].strip())
    except Exception:
        pass
    return sorted(matric_set)
