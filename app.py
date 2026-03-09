"""
app.py — ULAS Main App
Students sign attendance. Course reps manage attendance sessions.
"""
from __future__ import annotations

import streamlit as st
import time
import pandas as pd

from futo_data import get_schools, get_departments, get_levels
from core import (
    load_session_history,
    authenticate_user, load_settings, save_session, load_session,
    start_session, add_entry, edit_entry, delete_entry, validate_matric,
    delete_session, push_attendance_to_lava, session_to_csv,
    build_csv_filename, check_and_register_device,
    futo_now, futo_now_str, load_active_semester,
    set_beacon, verify_beacon, gps_accuracy_tier,
)
from streamlit_cookies_manager import EncryptedCookieManager
from streamlit_js_eval import get_geolocation

st.set_page_config(
    page_title="ULAS — FUTO Attendance",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.hero {
    background: linear-gradient(135deg, #006400 0%, #1a8c1a 60%, #2eb82e 100%);
    border-radius: 16px; padding: 2rem 2rem 1.5rem;
    text-align: center; color: white; margin-bottom: 2rem;
    box-shadow: 0 4px 20px rgba(0,100,0,0.3);
}
.hero h1 { font-size: 2rem; font-weight: 900; margin: 0; }
.hero .sub { font-size: 0.9rem; opacity: 0.85; margin-top: 0.3rem; }
.hero .badge {
    display: inline-block; background: rgba(255,255,255,0.2);
    border-radius: 20px; padding: 3px 14px; font-size: 0.8rem; margin-top: 0.6rem;
}
.beacon-idle {
    background: rgba(30,30,60,0.12);
    border: 2px dashed rgba(100,100,200,0.4);
    border-radius: 14px; padding: 1.5rem 1rem;
    text-align: center; margin: 0.8rem 0;
}
.beacon-active {
    background: linear-gradient(135deg, #0a4d0a 0%, #16a34a 100%);
    border-radius: 14px; padding: 1.5rem 1rem;
    text-align: center; margin: 0.8rem 0;
    box-shadow: 0 4px 16px rgba(22,163,74,0.35); color: white;
}
.beacon-active .blip { font-size: 2.5rem; display:inline-block;
    animation: blip 1.6s ease-in-out infinite; }
@keyframes blip {
    0%,100% { transform: scale(1); opacity: 1; }
    50%      { transform: scale(1.2); opacity: 0.7; }
}
.info-card {
    background: rgba(46, 184, 46, 0.08);
    border-left: 4px solid #2eb82e;
    border-radius: 0 8px 8px 0;
    padding: 0.8rem 1rem; margin: 0.6rem 0;
    font-size: 0.9rem; color: inherit;
}
.info-card b { color: #2eb82e; }
.success-box {
    background: rgba(0, 179, 0, 0.1);
    border: 1.5px solid #00b300; border-radius: 12px;
    padding: 1.5rem; text-align: center; color: inherit;
}
.success-box .tick { font-size: 2.5rem; }
.success-box h3 { color: #2eb82e; margin: 0.5rem 0 0.2rem; }
div[data-testid="stForm"] {
    border: 1.5px solid rgba(128,128,128,0.3);
    border-radius: 12px; padding: 1.2rem 1.2rem 0.5rem;
}
.stButton > button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Fixed footer ─────────────────────────────────────────────────────────────
st.markdown('\n<style>\n.ulas-footer {\n    position: fixed;\n    bottom: 0; left: 0; right: 0;\n    text-align: center;\n    padding: 0.45rem 1rem;\n    font-size: 0.78rem;\n    background: rgba(0,0,0,0.45);\n    backdrop-filter: blur(6px);\n    -webkit-backdrop-filter: blur(6px);\n    color: rgba(255,255,255,0.55);\n    letter-spacing: 0.04em;\n    z-index: 9999;\n    border-top: 1px solid rgba(255,255,255,0.07);\n}\n.ulas-footer b { color: rgba(255,255,255,0.8); font-weight: 600; }\n.ulas-footer .dot { color: rgba(255,255,255,0.3); margin: 0 0.3em; }\n/* Push content up so footer never overlaps last element */\nsection.main > div { padding-bottom: 2.8rem !important; }\n</style>\n<div class="ulas-footer">\n    Made with ❤️ by\n    <b>SESET</b><span class="dot">•</span><b>EPE</b><span class="dot">•</span><b>2030/2031</b>\n</div>\n', unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🎓 ULAS</h1>
    <div class="sub">Universal Lecture Attendance System</div>
    <div class="badge">Federal University of Technology, Owerri</div>
</div>
""", unsafe_allow_html=True)

# ── Cookie manager (double-entry prevention) ─────────────────────────────────
_cookies = EncryptedCookieManager(
    prefix="ulas_",
    password=st.secrets.get("COOKIE_SECRET", "ulas-demo-secret-changeme"),
)
if not _cookies.ready():
    st.spinner("Loading...")
    st.stop()

# ── Session state defaults ────────────────────────────────────────────────────
DEFAULTS = {
    "mode": None,
    # Rep state — persists session across reruns, never cleared by DEFAULTS loop
    "rep_user": None,
    "rep_session": None,       # the active session dict (kept in memory)
    "rep_session_sha": None,
    "rep_session_loaded": False,  # True once we've done the initial GitHub fetch
    "rep_beacon_scanning": False, # True while waiting for geolocation API response
    # Student state
    "stu_stage": "select",    # select | locate | entry | done
    "stu_school": None, "stu_dept": None, "stu_level": None,
    "stu_session": None,
    "stu_lat": None, "stu_lon": None,  # verified student GPS coords
    "show_delete_confirm": None,
    "pending_end": False,
    "show_end_summary": False,
    "takeover_confirmed": False,
    # Cascading dropdown values
    "dd_school": None, "dd_dept": None, "dd_level": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Cascading dropdown callbacks ──────────────────────────────────────────────
def _on_school():
    st.session_state.dd_school = st.session_state._dd_school_w
    st.session_state.dd_dept   = None
    st.session_state.dd_level  = None

def _on_dept():
    st.session_state.dd_dept  = st.session_state._dd_dept_w
    st.session_state.dd_level = None

def _on_level():
    st.session_state.dd_level = st.session_state._dd_level_w



# ── Branded error screen ─────────────────────────────────────────────────────
def _show_error(exc: Exception):
    st.markdown("""
    <div style="
        max-width:520px; margin:4rem auto; padding:2.5rem 2rem;
        background:rgba(0,100,0,0.08); border:1.5px solid rgba(0,100,0,0.25);
        border-radius:16px; text-align:center;
    ">
        <div style="font-size:3rem; margin-bottom:0.5rem;">⚠️</div>
        <h2 style="color:#006400; margin:0 0 0.5rem;">Something went wrong</h2>
        <p style="opacity:0.7; font-size:0.92rem; margin:0 0 1.5rem;">
            An unexpected error occurred. Please try refreshing the page.<br>
            If the problem persists, contact your course rep or ICT.
        </p>
        <button onclick="window.location.reload()"
            style="background:#006400; color:white; border:none; border-radius:8px;
                   padding:0.6rem 1.8rem; font-size:1rem; cursor:pointer; font-weight:600;">
            🔄 Refresh Page
        </button>
    </div>
    """, unsafe_allow_html=True)

# ── Main app body ─────────────────────────────────────────────────────────────
try:
    # ═══════════════════════════════════════════════════════════════════════════════
    #  HOME
    # ═══════════════════════════════════════════════════════════════════════════════
    if st.session_state.mode is None:
        st.markdown("### How are you using ULAS today?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👤  Student\n\nSign attendance", use_container_width=True):
                st.session_state.mode = "student"
                st.rerun()
        with c2:
            if st.button("🔐  Course Rep\n\nManage attendance", use_container_width=True):
                st.session_state.mode = "rep"
                st.rerun()
        st.stop()


    # ═══════════════════════════════════════════════════════════════════════════════
    #  STUDENT FLOW
    # ═══════════════════════════════════════════════════════════════════════════════
    if st.session_state.mode == "student":

        if st.button("← Home"):
            for k, v in DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()

        st.markdown("## 📋 Sign Attendance")

        # ── Semester gate ──────────────────────────────────────────────────────────
        _sem = load_active_semester()
        if not _sem:
            st.markdown("""<div class="info-card" style="text-align:center;padding:2rem">
                <div style="font-size:2rem">🔒</div>
                <b style="font-size:1.1rem">No Active Semester</b><br>
                <span style="opacity:0.75">Attendance sign-in is not available right now.<br>
                Please check back when your department notifies you of the new semester.</span>
            </div>""", unsafe_allow_html=True)
            st.stop()

        # ── STAGE: select ──────────────────────────────────────────────────────────
        if st.session_state.stu_stage == "select":
            schools    = get_schools()
            cur_school = st.session_state.dd_school
            s_opts     = ["— select school —"] + schools
            st.selectbox(
                "Your School", s_opts,
                index=s_opts.index(cur_school) if cur_school in s_opts else 0,
                key="_dd_school_w", on_change=_on_school,
            )

            cur_school = st.session_state.dd_school
            depts      = get_departments(cur_school) if cur_school else []
            cur_dept   = st.session_state.dd_dept if st.session_state.dd_dept in depts else None
            d_opts     = ["— select department —"] + depts
            st.selectbox(
                "Your Department", d_opts,
                index=d_opts.index(cur_dept) if cur_dept in d_opts else 0,
                key="_dd_dept_w", on_change=_on_dept,
                disabled=not cur_school,
            )

            cur_dept  = st.session_state.dd_dept
            levels    = get_levels(cur_dept, cur_school) if cur_dept and cur_school else []
            cur_level = st.session_state.dd_level if st.session_state.dd_level in levels else None
            l_opts    = ["— select level —"] + levels
            st.selectbox(
                "Your Level", l_opts,
                index=l_opts.index(cur_level) if cur_level in l_opts else 0,
                key="_dd_level_w", on_change=_on_level,
                disabled=not cur_dept,
            )

            if st.button("Check for Attendance →", type="primary"):
                s, d, l = st.session_state.dd_school, st.session_state.dd_dept, st.session_state.dd_level
                if not all([s, d, l]):
                    st.error("Please select your school, department and level.")
                else:
                    with st.spinner("Checking for active attendance..."):
                        session, _ = load_session(s, d, l)
                    if not session:
                        st.warning("No attendance is currently running for your level. Check with your course rep.")
                    else:
                        st.session_state.stu_school  = s
                        st.session_state.stu_dept    = d
                        st.session_state.stu_level   = l
                        st.session_state.stu_session = session
                        st.session_state.stu_stage   = "locate"
                        st.rerun()

        # ── STAGE: locate — GPS beacon scan ──────────────────────────────────────
        elif st.session_state.stu_stage == "locate":
            sess = st.session_state.stu_session
            st.markdown(f"""<div class="info-card">
                <b>Course:</b> {sess['course_code']} &nbsp;|&nbsp;
                <b>Department:</b> {sess['department']} &nbsp;|&nbsp;
                <b>Level:</b> {sess['level']}L
            </div>""", unsafe_allow_html=True)

            # Re-fetch to check beacon status
            with st.spinner("Checking beacon..."):
                fresh, _ = load_session(
                    st.session_state.stu_school,
                    st.session_state.stu_dept,
                    st.session_state.stu_level,
                )
            if not fresh:
                st.error("Attendance has ended. Please contact your course rep.")
                st.session_state.stu_stage = "select"
                st.rerun()

            if not fresh.get("beacon_lat") or not fresh.get("beacon_lon"):
                st.markdown("""<div class="beacon-idle">
                    <div style="font-size:2rem">📡</div>
                    <b>Beacon not active yet</b><br>
                    <span style="opacity:0.7;font-size:0.88rem">
                        Your course rep has not activated the beacon yet.<br>
                        Wait for them to tap <b>Activate Beacon</b>, then tap Refresh.
                    </span>
                </div>""", unsafe_allow_html=True)
                if st.button("🔄 Refresh"):
                    st.session_state.stu_session = fresh
                    st.rerun()
                st.stop()

            _rng = load_settings().get("BEACON_RANGE", 100)
            st.markdown(f"""
            <div style="text-align:center;padding:1.2rem 0 0.5rem">
                <div style="font-size:2.5rem">📍</div>
                <b style="font-size:1.1rem">Location Verification</b><br>
                <span style="opacity:0.7;font-size:0.9rem">
                    Tap <b>Scan My Location</b>. You must be within
                    <b>{_rng}m</b> of the lecture room.
                </span>
            </div>""", unsafe_allow_html=True)

            loc = get_geolocation("Scan My Location")

            if loc and loc.get("coords"):
                coords = loc["coords"]
                s_lat  = coords.get("latitude")
                s_lon  = coords.get("longitude")
                s_acc  = coords.get("accuracy", 999)

                if s_lat is None or s_lon is None:
                    st.error("Could not read your GPS coordinates. Allow location access and try again.")
                    st.stop()

                tier_label, tier_emoji, _ = gps_accuracy_tier(s_acc)
                st.markdown(
                    f"<div style='text-align:center;font-size:1rem;padding:0.4rem 0'>"
                    f"GPS Signal: {tier_emoji} <b>{tier_label}</b> (±{s_acc:.0f}m)"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                allowed, vmsg = verify_beacon(s_lat, s_lon, fresh, student_accuracy=s_acc)
                if allowed:
                    st.session_state.stu_session = fresh
                    st.session_state.stu_lat     = s_lat
                    st.session_state.stu_lon     = s_lon
                    st.session_state.stu_stage   = "entry"
                    st.rerun()
                else:
                    st.error(f"❌ {vmsg}")
                    st.caption("If you believe this is an error, speak to your course rep.")

                # ── STAGE: entry ──────────────────────────────────────────────
        elif st.session_state.stu_stage == "entry":
            sess = st.session_state.stu_session
            st.markdown(f"""<div class="info-card">
                <b>Course:</b> {sess['course_code']} &nbsp;|&nbsp;
                <b>Dept:</b> {sess['department']} &nbsp;|&nbsp;
                <b>Level:</b> {sess['level']}L
            </div>""", unsafe_allow_html=True)

            # ── Layer 1: cookie-based double-entry check ───────────────────
            _ck_key = f"signed_{sess['course_code']}_{sess.get('started_at', '')[:10]}"
            _already_signed = (
                _cookies.get(_ck_key) or
                st.session_state.get(f"_signed_{_ck_key}")
            )
            if _already_signed:
                st.markdown("""<div class="success-box">
                    <div class="tick">✅</div>
                    <h3>Already Signed In</h3>
                    <p style="margin:0">This device has already recorded attendance for this class today.</p>
                </div>""", unsafe_allow_html=True)
                st.stop()

            st.markdown("Fill in your details. **Surname first, exactly as on your student ID.**")

            with st.form("entry_form"):
                surname     = st.text_input("Surname (Family Name)", placeholder="e.g. OKAFOR")
                other_names = st.text_input("Other Names", placeholder="e.g. Chukwuemeka John")
                matric      = st.text_input("Matric Number (11 digits)", placeholder="20200123456", max_chars=11)
                submit      = st.form_submit_button("✅ Sign Attendance", type="primary")

            if submit:
                errs = []
                if not surname.strip():     errs.append("Surname cannot be empty.")
                if not other_names.strip(): errs.append("Other names cannot be empty.")
                ok_m, mm = validate_matric(matric)
                if not ok_m:                errs.append(mm)

                if errs:
                    for e in errs: st.error(e)
                else:
                    # Layer 1 re-check before writing
                    if _cookies.get(_ck_key) or st.session_state.get(f"_signed_{_ck_key}"):
                        st.error("This device has already signed attendance for this class.")
                    else:
                        with st.spinner("Submitting..."):
                            current, sha = load_session(
                                st.session_state.stu_school,
                                st.session_state.stu_dept,
                                st.session_state.stu_level,
                            )
                        if not current:
                            st.error("Attendance ended before you submitted. Contact your course rep.")
                            st.session_state.stu_stage = "select"
                            st.rerun()
                        else:
                            # Layer 2: stable device ID from cookie manager
                            _dev_id = _cookies.get("device_id") or ""
                            if not _dev_id:
                                import uuid as _uuid
                                _dev_id = "cm_" + str(_uuid.uuid4())[:12]
                                _cookies["device_id"] = _dev_id
                                _cookies.save()
                            allowed, dmsg = check_and_register_device(
                                st.session_state.stu_school, st.session_state.stu_dept,
                                st.session_state.stu_level, current["course_code"],
                                _dev_id, matric,
                            )
                            if not allowed:
                                st.error(dmsg)
                            else:
                                ok, msg = add_entry(current, surname, other_names, matric)
                                if ok:
                                    # Write cookie FIRST, before rerun, wrapped in
                                    # try/except — cookie manager can throw on some
                                    # mobile browsers mid-render cycle.
                                    try:
                                        _cookies[_ck_key] = matric.strip()
                                        _cookies.save()
                                    except Exception:
                                        pass
                                    # Session-state fallback guard (same browser session)
                                    st.session_state[f"_signed_{_ck_key}"] = True

                                    new_sha = save_session(
                                        st.session_state.stu_school, st.session_state.stu_dept,
                                        st.session_state.stu_level, current, sha,
                                    )
                                    # Whether or not save_session succeeded, show done —
                                    # the entry is already in the in-memory dict.
                                    st.session_state.stu_session = current
                                    st.session_state.stu_stage   = "done"
                                    st.rerun()
                                else:
                                    st.error(msg)

        # ── STAGE: done ───────────────────────────────────────────────────────────
        elif st.session_state.stu_stage == "done":
            sess = st.session_state.stu_session
            last = sess["entries"][-1] if sess["entries"] else {}
            st.markdown(f"""
            <div class="success-box">
                <div class="tick">✅</div>
                <h3>Attendance Recorded!</h3>
                <p style="margin:0">
                    <b>{last.get('surname','')} {last.get('other_names','')}</b><br>
                    Matric: {last.get('matric','')} &nbsp;|&nbsp; Time: {last.get('time','')}
                </p>
            </div>
            <div class="info-card" style="margin-top:1rem">
                <b>Course:</b> {sess['course_code']} &nbsp;|&nbsp;
                <b>Dept:</b> {sess['department']} &nbsp;|&nbsp;
                <b>Level:</b> {sess['level']}L
            </div>""", unsafe_allow_html=True)

        st.stop()


    # ═══════════════════════════════════════════════════════════════════════════════
    #  COURSE REP FLOW
    # ═══════════════════════════════════════════════════════════════════════════════
    if st.session_state.mode == "rep":

        # ── Login ─────────────────────────────────────────────────────────────────
        if st.session_state.rep_user is None:
            st.markdown("## 🔐 Course Rep Login")
            if st.button("← Home"):
                st.session_state.mode = None
                st.rerun()

            with st.form("rep_login"):
                uname = st.text_input("Username")
                pwd   = st.text_input("Password", type="password")
                login = st.form_submit_button("Login", type="primary")

            if login:
                with st.spinner("Authenticating..."):
                    user = authenticate_user(uname, pwd, role="rep")
                if user:
                    st.session_state.rep_user           = user
                    st.session_state.rep_session        = None
                    st.session_state.rep_session_sha    = None
                    st.session_state.rep_session_loaded = False
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            st.stop()

        # ── Rep is logged in ───────────────────────────────────────────────────────
        rep      = st.session_state.rep_user
        hc1, hc2 = st.columns([5, 1])
        with hc1:
            st.markdown("## 📊 Rep Dashboard")
            st.markdown(f"""<div class="info-card">
                <b>{rep['username']}</b> &nbsp;·&nbsp;
                {rep['department']} &nbsp;·&nbsp; Level <b>{rep['level']}L</b>
            </div>""", unsafe_allow_html=True)
        with hc2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Logout"):
                for k, v in DEFAULTS.items():
                    st.session_state[k] = v
                st.rerun()

        # ── Session loading strategy ───────────────────────────────────────────────
        # Only fetch from GitHub once per login (when rep_session_loaded is False).
        # After that, rep_session in st.session_state is the source of truth.
        # This prevents the forced-logout race condition caused by re-fetching
        # immediately after start_session writes to GitHub.
        if not st.session_state.rep_session_loaded:
            with st.spinner("Loading session..."):
                session, sha = load_session(rep["school"], rep["department"], rep["level"])
            st.session_state.rep_session        = session
            st.session_state.rep_session_sha    = sha
            st.session_state.rep_session_loaded = True

        session = st.session_state.rep_session
        sha     = st.session_state.rep_session_sha

        # ── Rep-to-Rep Handoff check ──────────────────────────────────────────
        # If session was started by a different rep, show an explicit take-over card
        if (session and
                session.get("rep_username") != rep["username"] and
                not st.session_state.get("takeover_confirmed")):
            other = session.get("rep_username", "another rep")
            st.markdown("### 🔄 Active Session — Different Rep")
            st.markdown(f"""<div class="info-card">
                A session for <b>Level {session['level']}L — {session['course_code']}</b>
                was started by <b>{other}</b> at {session['started_at'][11:16]}.<br>
                <span style="opacity:0.7">
                    You can take over management of this session,
                    or wait for {other} to end it.
                </span>
            </div>""", unsafe_allow_html=True)
            tc1, tc2 = st.columns(2)
            with tc1:
                if st.button("🔄 Take Over Session", type="primary", use_container_width=True):
                    # Record the takeover in the session JSON
                    fs, fs_sha = load_session(rep["school"], rep["department"], rep["level"])
                    if fs:
                        fs["rep_username"] = rep["username"]
                        fs.setdefault("takeover_log", []).append({
                            "taken_by": rep["username"],
                            "from":     other,
                            "at":       futo_now_str(),
                        })
                        new_sha = save_session(rep["school"], rep["department"], rep["level"], fs, fs_sha)
                        st.session_state.rep_session        = fs
                        st.session_state.rep_session_sha    = new_sha
                        st.session_state.takeover_confirmed = True
                        st.success(f"✅ You have taken over the session from {other}.")
                        st.rerun()
            with tc2:
                if st.button("👁️ View Only (no changes)", use_container_width=True):
                    st.session_state.takeover_confirmed = True
                    st.rerun()
            st.stop()

        # ── No active session — start one + show history ─────────────────────────
        if not session:
            st.markdown("### ▶ Start New Attendance")
            with st.form("start_att"):
                course_code = st.text_input("Course Code", placeholder="e.g. CSC301")
                start_btn   = st.form_submit_button("Start Attendance", type="primary")
            if start_btn:
                _sem_rep = load_active_semester()
                if not _sem_rep:
                    st.error("🔒 No active semester. ICT must start a semester before attendance can be taken.")
                elif not course_code.strip():
                    st.error("Please enter a course code.")
                else:
                    with st.spinner("Starting..."):
                        session, sha = start_session(
                            rep["school"], rep["department"], rep["level"],
                            course_code, rep["username"],
                        )
                    st.session_state.rep_session     = session
                    st.session_state.rep_session_sha = sha
                    st.rerun()

            # ── Session History ───────────────────────────────────────────────
            st.divider()
            st.markdown("### 📋 Your Session History")
            with st.spinner("Loading history..."):
                history = load_session_history(rep["username"])
            if not history:
                st.info("No past sessions yet. Your pushed attendances will appear here.")
            else:
                hist_df = pd.DataFrame(history)
                hist_df.columns = [c.replace("_", " ").title() for c in hist_df.columns]
                st.dataframe(hist_df, use_container_width=True, hide_index=True)
                st.caption(f"Showing last {len(history)} session(s). Only successfully pushed sessions are recorded.")
            st.stop()

        # ── Beacon status + activation ────────────────────────────────────────────
        beacon_set = session.get("beacon_lat") is not None

        st.markdown(f"### 🟢 Active — {session['course_code']}")
        st.caption(f"Started {session['started_at'][11:16]} · {len(session['entries'])} entries")

        if beacon_set:
            b_set_at = session.get("beacon_set_at", "")[:16].replace("T", " ")
            st.markdown(f"""<div class="beacon-active">
                <div class="blip">📡</div>
                <b style="font-size:1.05rem">Beacon Active</b><br>
                <span style="opacity:0.85;font-size:0.82rem">
                    Set at {b_set_at} &nbsp;·&nbsp;
                    {session['beacon_lat']:.5f}, {session['beacon_lon']:.5f}
                </span>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="beacon-idle">
                <div style="font-size:2rem">📡</div>
                <b>Beacon not active</b><br>
                <span style="opacity:0.7;font-size:0.85rem">
                    Students cannot verify location until you activate the beacon.<br>
                    Tap the button below while you are inside the lecture room.
                </span>
            </div>""", unsafe_allow_html=True)

        # ── Beacon activation button ───────────────────────────────────────────────
        if not st.session_state.rep_beacon_scanning:
            btn_label = "📡 Update Beacon" if beacon_set else "📡 Activate Beacon"
            if st.button(btn_label, type="primary", use_container_width=True):
                st.session_state.rep_beacon_scanning = True
                st.rerun()
        else:
            st.info("📍 Getting your location — allow location access when prompted…")
            rep_loc = get_geolocation("Get My Location")
            if rep_loc and rep_loc.get("coords"):
                r_lat = rep_loc["coords"].get("latitude")
                r_lon = rep_loc["coords"].get("longitude")
                r_acc = rep_loc["coords"].get("accuracy", 999)
                if r_lat is not None and r_lon is not None:
                    if r_acc > 500:
                        st.warning(
                            f"⚠️ GPS signal is very weak (±{r_acc:.0f}m). "
                            "Beacon set — but consider retapping once signal improves."
                        )
                    with st.spinner("Setting beacon..."):
                        ok, bmsg = set_beacon(
                            rep["school"], rep["department"], rep["level"],
                            r_lat, r_lon, r_acc,
                        )
                        if ok:
                            fresh_b, fresh_b_sha = load_session(
                                rep["school"], rep["department"], rep["level"]
                            )
                            if fresh_b:
                                st.session_state.rep_session     = fresh_b
                                st.session_state.rep_session_sha = fresh_b_sha
                                session = fresh_b
                            st.session_state.rep_beacon_scanning = False
                            st.success(f"✅ Beacon activated! Accuracy: ±{r_acc:.0f}m")
                            st.rerun()
                        else:
                            st.error(f"Could not set beacon: {bmsg}")
                            st.session_state.rep_beacon_scanning = False

                st.divider()

        # ── Manual add ────────────────────────────────────────────────────────────
        with st.expander("➕ Manually Add Entry"):
            with st.form("manual_add"):
                ma_sur = st.text_input("Surname")
                ma_oth = st.text_input("Other Names")
                ma_mat = st.text_input("Matric Number (11 digits)", max_chars=11)
                ma_btn = st.form_submit_button("Add Entry")
            if ma_btn:
                ok_m, m_msg = validate_matric(ma_mat)
                if not ma_sur.strip() or not ma_oth.strip():
                    st.error("Name fields cannot be empty.")
                elif not ok_m:
                    st.error(m_msg)
                else:
                    fresh_s, fresh_sha = load_session(rep["school"], rep["department"], rep["level"])
                    if fresh_s:
                        ok, msg = add_entry(fresh_s, ma_sur, ma_oth, ma_mat)
                        if ok:
                            new_sha = save_session(rep["school"], rep["department"], rep["level"], fresh_s, fresh_sha)
                            st.session_state.rep_session     = fresh_s
                            st.session_state.rep_session_sha = new_sha
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # ── Entry table — re-fetch from GitHub on every rerun to pick up student entries
        fresh_s, fresh_sha = load_session(rep["school"], rep["department"], rep["level"])
        if fresh_s:
            st.session_state.rep_session      = fresh_s
            st.session_state.rep_session_sha  = fresh_sha
            session = fresh_s
            sha     = fresh_sha

        st.markdown(f"#### Attendance List ({len(session['entries'])} entries)")
        if not session["entries"]:
            st.info("No entries yet. Waiting for students to sign in.")
        else:
            df = pd.DataFrame([{
                "S/N":        e["sn"],
                "Surname":    e["surname"],
                "Other Names": e["other_names"],
                "Matric No.": e["matric"],
                "Time":       e["time"],
            } for e in session["entries"]])
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("**Edit or Delete an Entry**")
            opts      = {f"S/N {e['sn']} — {e['surname']} {e['other_names']}": e["sn"] for e in session["entries"]}
            sel_label = st.selectbox("Select entry", list(opts.keys()))
            sel_sn    = opts[sel_label]
            sel_e     = next(e for e in session["entries"] if e["sn"] == sel_sn)

            ec, dc = st.columns([3, 1])
            with ec:
                with st.form("edit_form"):
                    ed_sur = st.text_input("Surname",       value=sel_e["surname"])
                    ed_oth = st.text_input("Other Names",   value=sel_e["other_names"])
                    ed_mat = st.text_input("Matric Number", value=sel_e["matric"], max_chars=11)
                    ed_btn = st.form_submit_button("✏️ Save Edit")
                if ed_btn:
                    ok_m, m_msg = validate_matric(ed_mat)
                    if not ok_m:
                        st.error(m_msg)
                    else:
                        fs, fs_sha = load_session(rep["school"], rep["department"], rep["level"])
                        ok, msg    = edit_entry(fs, sel_sn, ed_sur, ed_oth, ed_mat)
                        if ok:
                            new_sha = save_session(rep["school"], rep["department"], rep["level"], fs, fs_sha)
                            st.session_state.rep_session     = fs
                            st.session_state.rep_session_sha = new_sha
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            with dc:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.session_state.show_delete_confirm == sel_sn:
                    st.warning(f"Delete S/N {sel_sn}?")
                    y, n = st.columns(2)
                    with y:
                        if st.button("Yes", type="primary", key="yes_del"):
                            fs, fs_sha = load_session(rep["school"], rep["department"], rep["level"])
                            ok, _      = delete_entry(fs, sel_sn)
                            if ok:
                                new_sha = save_session(rep["school"], rep["department"], rep["level"], fs, fs_sha)
                                st.session_state.rep_session     = fs
                                st.session_state.rep_session_sha = new_sha
                            st.session_state.show_delete_confirm = None
                            st.rerun()
                    with n:
                        if st.button("No", key="no_del"):
                            st.session_state.show_delete_confirm = None
                            st.rerun()
                else:
                    if st.button("🗑️ Delete", key="del_btn"):
                        st.session_state.show_delete_confirm = sel_sn
                        st.rerun()

        st.divider()

        # ── End attendance ────────────────────────────────────────────────────────
        st.markdown("### ⏹ End Attendance")

        # ── STEP: Execute pending push (set on previous run) ─────────────────────
        if st.session_state.pending_end:
            st.session_state.pending_end      = False
            st.session_state.show_end_summary = False
            with st.spinner("Pushing to LAVA..."):
                final, fsha = load_session(rep["school"], rep["department"], rep["level"])
                if final:
                    ok, pmsg = push_attendance_to_lava(final)
                    if ok:
                        delete_session(rep["school"], rep["department"], rep["level"])
                        st.session_state.rep_session        = None
                        st.session_state.rep_session_sha    = None
                        st.session_state.rep_session_loaded = True
                        st.session_state.takeover_confirmed = False
                        st.session_state.rep_beacon_scanning = False
                        st.success("✅ Attendance pushed to LAVA successfully!")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Push failed — session still open. Download backup below.")
                        st.markdown(pmsg)
                else:
                    st.error("Session not found.")
            st.stop()

        # ── STEP: Show summary before confirming push ─────────────────────────────
        if st.session_state.show_end_summary:
            entries     = session["entries"]
            manual_flag = [e for e in entries if e.get("manual")]
            times       = [e["time"] for e in entries if e.get("time")]
            first_entry = min(times) if times else "—"
            last_entry  = max(times) if times else "—"
            duration_m  = ""
            try:
                from datetime import datetime as _dt
                t0 = _dt.fromisoformat(session["started_at"])
                t1 = futo_now()
                mins = int((t1 - t0).total_seconds() // 60)
                duration_m = f"{mins} min"
            except Exception:
                pass

            st.markdown(f"""<div class="info-card">
                <b>📋 Attendance Summary</b><br><br>
                <b>Course Code:</b> {session['course_code']} &nbsp;·&nbsp;
                <b>Level:</b> {session['level']}L<br>
                <b>Started:</b> {session['started_at'][11:16]}
                {f"&nbsp;·&nbsp; <b>Duration:</b> {duration_m}" if duration_m else ""}<br>
                <b>Total Entries:</b> {len(entries)}<br>
                <b>First Entry:</b> {first_entry} &nbsp;·&nbsp;
                <b>Last Entry:</b> {last_entry}<br>
                {f"<b>Manual Entries:</b> {len(manual_flag)} flagged" if manual_flag else
                 "<span style='opacity:0.65'>No manual entries</span>"}
            </div>""", unsafe_allow_html=True)

            if not entries:
                st.error("⚠️ No entries recorded. Are you sure you want to push an empty attendance?")

            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                if st.button("✅ Confirm & Push to LAVA", type="primary", use_container_width=True):
                    st.session_state.pending_end = True
                    st.rerun()
            with sc2:
                if st.button("✏️ Back to Editing", use_container_width=True):
                    st.session_state.show_end_summary = False
                    st.rerun()
            with sc3:
                st.download_button(
                    "⬇️ CSV Backup",
                    session_to_csv(session),
                    file_name=build_csv_filename(session),
                    mime="text/csv", use_container_width=True,
                )
            st.stop()

        # ── STEP: Initial end button ──────────────────────────────────────────────
        st.caption(f"Currently **{len(session['entries'])} entries** — review summary before pushing.")
        e1, e2 = st.columns(2)
        with e1:
            if st.button("⏹ End Attendance", type="primary", use_container_width=True):
                st.session_state.show_end_summary = True
                st.rerun()
        with e2:
            st.download_button(
                "⬇️ Download CSV Backup",
                session_to_csv(session),
                file_name=build_csv_filename(session),
                mime="text/csv", use_container_width=True,
            )

        # GPS beacon replaces rotating token — no countdown needed.

except Exception as _err:
    if type(_err).__name__ in ("StopException", "RerunException"):
        raise
    _show_error(_err)

