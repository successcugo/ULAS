# ULAS — Universal Lecture Attendance System
### Federal University of Technology, Owerri

---

## Repos

| Repo | Purpose |
|------|---------|
| `successcugo/ULAS` | This codebase — frontend apps |
| `successcugo/ULASDATA` | All JSON data: users, sessions, settings |
| `successcugo/LAVA` | Final attendance CSVs (Lecture Attendance Viewing Archive) |

---

## Files

```
ULAS/
├── app.py            ← Main app (students + course reps)
├── advisor_app.py    ← Advisor portal (separate deployment)
├── core.py           ← All business logic
├── github_store.py   ← GitHub API layer (reads/writes ULASDATA)
├── futo_data.py      ← All 10 schools, 75+ departments, level counts
├── requirements.txt
└── .streamlit/
    └── secrets.toml  ← Add your secrets here (never commit this)
```

---

## Streamlit Cloud Secrets

Set these in your Streamlit Cloud dashboard under **App secrets**:

```toml
GITHUB_PAT = "your_github_personal_access_token"
DATA_REPO = "ULASDATA"
DATA_OWNER = "successcugo"
LAVA_REPO = "LAVA"
LAVA_OWNER = "successcugo"
```

Your PAT needs **repo** (read + write) access to both `ULASDATA` and `LAVA`.

---

## Deploying on Streamlit Cloud

### App 1 — Main Attendance App
- **Repo:** `successcugo/ULAS`
- **Main file:** `app.py`
- **URL:** e.g. `ulas.streamlit.app`

### App 2 — Advisor Portal
- **Repo:** `successcugo/ULAS`
- **Main file:** `advisor_app.py`
- **URL:** e.g. `ulas-advisor.streamlit.app`

Both apps share the same codebase and secrets — deploy them as two separate Streamlit Cloud apps from the same repo, pointing to different main files.

---

## ULASDATA Repository Structure

```
ULASDATA/
├── data/
│   ├── users.json        ← All user accounts (reps + advisors), hashed passwords
│   └── settings.json     ← TOKEN_LIFETIME and other config
├── sessions/
│   └── *.json            ← One file per active attendance session
└── devices/
    └── *.json            ← Device→matric maps (anti-cheat, never exported)
```

---

## LAVA Repository Structure

```
LAVA/
└── attendances/
    └── SICT/
        └── Computer_Science/
            └── CSC301_ComputerScience_2025-01-15_10-30.csv
```

CSV columns: `S/N, Surname, Other Names, Matric Number, Time`

---

## First-Time Setup

1. **Deploy both apps** on Streamlit Cloud with secrets configured.
2. **Open the Advisor Portal** — since no accounts exist yet, you'll be prompted to create the first advisor account.
3. **Log in as advisor** and go to the **Course Reps** tab to assign usernames and passwords to each level.
4. **Course reps can now log in** on the main app and start managing attendance.

---

## How Attendance Works

### For Students
1. Open main app → "I'm a Student"
2. Select school → department → level
3. If attendance is running, the course code is shown
4. Enter the **4-digit code** from your course rep's screen
5. Enter surname + other names + matric number (11 digits)
6. Done

**Anti-cheat:** A browser cookie (`ulas_device_id`) is stored per device. One device can only sign one matric number per attendance session. This is stored in `ULASDATA/devices/` and never appears in CSVs.

### For Course Reps
1. Open main app → "Course Rep Login"
2. Enter credentials set by your Course Advisor
3. Enter a course code and start attendance
4. A rotating 4-digit code is shown — share it verbally with students
5. Code rotates every `TOKEN_LIFETIME` seconds (default 7s, set by advisor)
6. Manually add/edit/delete entries as needed
7. End attendance → CSV is pushed to LAVA automatically
8. Download local CSV backup at any time

### For Course Advisors
- Manage course rep accounts (create, delete)
- Reset any rep's password
- Change their own password
- Configure TOKEN_LIFETIME

---

## Important Rules
- Matric numbers: exactly **11 digits**, numeric only
- Names: **case-insensitive** for duplicate detection, stored as UPPER (surname) / Title (other names)
- **One active attendance per level per department** at a time
- Timezone: all timestamps in **UTC+1 (FUTO time)**
- **Usernames are unique school-wide** — no two course reps anywhere in FUTO can share a username
