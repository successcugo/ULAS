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
    start_session, refresh_token, token_remaining, validate_token,
    add_entry, edit_entry, delete_entry, validate_matric,
    delete_session, push_attendance_to_lava, session_to_csv,
    build_csv_filename, check_and_register_device,
    futo_now, futo_now_str, load_active_semester,
    is_school_time, att_remaining_minutes, is_att_expired,
    add_entry_v2, flag_concurrent_in_other_session,
    session_to_csv_v2, build_csv_filename_v2,
)
from streamlit_cookies_manager import EncryptedCookieManager

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
.token-display {
    background: #0d1117; border: 2px solid #00e676;
    border-radius: 14px; padding: 1.5rem 1rem;
    text-align: center; margin: 0.8rem 0;
}
.token-display .code {
    font-size: 3.5rem; font-weight: 900; letter-spacing: 0.6rem;
    color: #00e676; font-family: monospace; line-height: 1;
}
.token-display .label {
    font-size: 0.75rem; color: #8b949e; margin-top: 0.4rem;
    text-transform: uppercase; letter-spacing: 1px;
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
    # Student state
    "stu_stage": "select",
    "stu_school": None, "stu_dept": None, "stu_level": None,
    "stu_session": None,
    "show_delete_confirm": None,
    "pending_end": False,
    "show_end_summary": False,
    "takeover_confirmed": False,
    # Cascading dropdown values
    "dd_school": None, "dd_dept": None, "dd_level": None,
    # Attendance type selection
    "stu_att_type": None,       # "LECTURE" or "PRACTICAL"
    "rep_att_type": "LECTURE",  # currently managing type
    # Kill timer auto-push
    "rep_kill_triggered": False,
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
                s, d, l = (st.session_state.dd_school,
                            st.session_state.dd_dept,
                            st.session_state.dd_level)
                if not all([s, d, l]):
                    st.error("Please select your school, department and level.")
                else:
                    with st.spinner("Checking for active attendance..."):
                        lec_sess,  _ = load_session(s, d, l, att_type="LECTURE")
                        prac_sess, _ = load_session(s, d, l, att_type="PRACTICAL")
                    active_types = []
                    if lec_sess:  active_types.append("LECTURE")
                    if prac_sess: active_types.append("PRACTICAL")

                    if not active_types:
                        st.warning("No attendance is currently running for your level.")
                    elif len(active_types) == 1:
                        _the_sess = lec_sess if active_types[0] == "LECTURE" else prac_sess
                        st.session_state.stu_school   = s
                        st.session_state.stu_dept     = d
                        st.session_state.stu_level    = l
                        st.session_state.stu_session  = _the_sess
                        st.session_state.stu_att_type = active_types[0]
                        st.session_state.stu_stage    = "code"
                        st.rerun()
                    else:
                        st.session_state.stu_school = s
                        st.session_state.stu_dept   = d
                        st.session_state.stu_level  = l
                        st.session_state.stu_stage  = "pick_type"
                        st.rerun()

        # ── STAGE: pick_type — both LECTURE and PRACTICAL active ────────────────
        elif st.session_state.stu_stage == "pick_type":
            st.markdown("### Which attendance would you like to sign?")
            st.markdown("Both a **Lecture** and a **Practical** attendance are currently running for your level.")
            _pc1, _pc2 = st.columns(2)
            with _pc1:
                if st.button("📖 Lecture Attendance", use_container_width=True, type="primary"):
                    with st.spinner("Loading..."):
                        _sess, _ = load_session(
                            st.session_state.stu_school,
                            st.session_state.stu_dept,
                            st.session_state.stu_level,
                            att_type="LECTURE"
                        )
                    if _sess:
                        st.session_state.stu_session  = _sess
                        st.session_state.stu_att_type = "LECTURE"
                        st.session_state.stu_stage    = "code"
                        st.rerun()
                    else:
                        st.error("Lecture attendance has ended. Please refresh.")
            with _pc2:
                if st.button("🔬 Practical Attendance", use_container_width=True):
                    with st.spinner("Loading..."):
                        _sess, _ = load_session(
                            st.session_state.stu_school,
                            st.session_state.stu_dept,
                            st.session_state.stu_level,
                            att_type="PRACTICAL"
                        )
                    if _sess:
                        st.session_state.stu_session  = _sess
                        st.session_state.stu_att_type = "PRACTICAL"
                        st.session_state.stu_stage    = "code"
                        st.rerun()
                    else:
                        st.error("Practical attendance has ended. Please refresh.")

                # ── STAGE: code ───────────────────────────────────────────────────────────
        elif st.session_state.stu_stage == "code":
            sess     = st.session_state.stu_session
            lifetime = load_settings().get("TOKEN_LIFETIME", 7)

            st.markdown(f"""<div class="info-card">
                <b>Course:</b> {sess['course_code']} &nbsp;|&nbsp;
                <b>Department:</b> {sess['department']} &nbsp;|&nbsp;
                <b>Level:</b> {sess['level']}L
            </div>""", unsafe_allow_html=True)
            st.markdown("Enter the **4-digit code** currently shown on your course rep's screen.")

            with st.form("code_form"):
                code   = st.text_input("Attendance Code", max_chars=4, placeholder="e.g. 4823")
                verify = st.form_submit_button("Verify →", type="primary")

            if verify:
                with st.spinner("Verifying..."):
                    fresh, _ = load_session(
                        st.session_state.stu_school,
                        st.session_state.stu_dept,
                        st.session_state.stu_level,
                    )
                if not fresh:
                    st.error("The attendance has ended. Please contact your course rep.")
                    st.session_state.stu_stage = "select"
                elif validate_token(fresh, code, lifetime):
                    st.session_state.stu_session = fresh
                    st.session_state.stu_stage   = "entry"
                    st.rerun()
                else:
                    st.error("❌ Invalid or expired code. Ask your rep for the current code and try again.")

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
                                _att_type = st.session_state.get("stu_att_type","LECTURE")
                                ok, msg, _is_late, _is_conc = add_entry_v2(
                                    current, surname, other_names, matric,
                                    st.session_state.stu_school,
                                    st.session_state.stu_dept,
                                    st.session_state.stu_level,
                                )
                                if ok:
                                    # If concurrent, flag the other session too
                                    if _is_conc:
                                        flag_concurrent_in_other_session(
                                            st.session_state.stu_school,
                                            st.session_state.stu_dept,
                                            st.session_state.stu_level,
                                            matric, _att_type,
                                        )
                                    # Write cookie before rerun
                                    try:
                                        _cookies[_ck_key] = matric.strip()
                                        _cookies.save()
                                    except Exception:
                                        pass
                                    st.session_state[f"_signed_{_ck_key}"] = True
                                    new_sha = save_session(
                                        st.session_state.stu_school, st.session_state.stu_dept,
                                        st.session_state.stu_level, current, sha,
                                        att_type=_att_type,
                                    )
                                    st.session_state.stu_session    = current
                                    st.session_state.stu_stage      = "done"
                                    st.session_state.stu_is_late    = _is_late
                                    st.session_state.stu_is_conc    = _is_conc
                                    st.rerun()
                                else:
                                    st.error(msg)

        # ── STAGE: done ───────────────────────────────────────────────────────────
        elif st.session_state.stu_stage == "done":
            sess = st.session_state.stu_session
            last = sess["entries"][-1] if sess["entries"] else {}
            _att_label = st.session_state.get("stu_att_type", "LECTURE").title()
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
                <b>Type:</b> {_att_label} &nbsp;|&nbsp;
                <b>Dept:</b> {sess['department']} &nbsp;|&nbsp;
                <b>Level:</b> {sess['level']}L
            </div>""", unsafe_allow_html=True)

            # ── Late warning ──────────────────────────────────────────────────────
            if st.session_state.get("stu_is_late"):
                st.warning("⏰ **You have been marked as late.** Your entry was recorded after the attendance window closed. This will be visible to your advisor.")

            # ── Concurrent signing warning ────────────────────────────────────────
            if st.session_state.get("stu_is_conc"):
                st.error(
                    "🔀 **Concurrent Attendance Detected.**\n\n"
                    "You have been flagged for signing both a Lecture and a Practical "
                    "attendance at the same time. This flag has been recorded and your "
                    "advisor has been notified through the attendance export.\n\n"
                    "If this was a mistake, please speak to your advisor as soon as "
                    "possible to have your record reviewed."
                )

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
            # Load whichever type was last active (try both, prefer LECTURE)
            with st.spinner("Loading session..."):
                _lec_s, _lec_sha  = load_session(rep["school"], rep["department"],
                                                  rep["level"], att_type="LECTURE")
                _prac_s, _prac_sha = load_session(rep["school"], rep["department"],
                                                   rep["level"], att_type="PRACTICAL")
            # Use whichever is active; prefer most recently started
            if _lec_s and _prac_s:
                session = _lec_s; sha = _lec_sha
                st.session_state.rep_att_type = "LECTURE"
            elif _lec_s:
                session = _lec_s; sha = _lec_sha
                st.session_state.rep_att_type = "LECTURE"
            elif _prac_s:
                session = _prac_s; sha = _prac_sha
                st.session_state.rep_att_type = "PRACTICAL"
            else:
                session = None; sha = None
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
            # School day/time gate for rep too
            _rep_time_ok, _rep_time_msg = is_school_time()
            if not _rep_time_ok:
                st.markdown(f"""<div class="info-card" style="text-align:center;padding:1.5rem">
                    <div style="font-size:2rem">🕐</div>
                    <b>Outside School Hours</b><br>
                    <span style="opacity:0.75">{_rep_time_msg}</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("### ▶ Start New Attendance")

                # Check which types are already running
                _lec_running  = bool(load_session(rep["school"], rep["department"], rep["level"], att_type="LECTURE")[0])
                _prac_running = bool(load_session(rep["school"], rep["department"], rep["level"], att_type="PRACTICAL")[0])

                if _lec_running and _prac_running:
                    st.info("Both a Lecture and Practical attendance are already running. End one before starting another of the same type.")
                else:
                    with st.form("start_att"):
                        course_code = st.text_input("Course Code", placeholder="e.g. CSC301")
                        # Only show types not already running
                        _avail_types = []
                        if not _lec_running:  _avail_types.append("LECTURE")
                        if not _prac_running: _avail_types.append("PRACTICAL")
                        att_type_sel = st.radio(
                            "Attendance Type", _avail_types,
                            horizontal=True,
                            help="LECTURE and PRACTICAL can run concurrently but not two of the same type."
                        )
                        start_btn = st.form_submit_button("▶ Start Attendance", type="primary")

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
                                    att_type=att_type_sel,
                                )
                            st.session_state.rep_session     = session
                            st.session_state.rep_session_sha = sha
                            st.session_state.rep_att_type    = att_type_sel
                            st.session_state.rep_kill_triggered = False
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

        # ── Token refresh ─────────────────────────────────────────────────────────
        _tok_lifetime = load_settings().get("TOKEN_LIFETIME", 7)
        session, refreshed = refresh_token(session, _tok_lifetime)
        if refreshed:
            _att_t = session.get("att_type", "LECTURE")
            sha = save_session(rep["school"], rep["department"], rep["level"],
                               session, sha, att_type=_att_t)
            st.session_state.rep_session     = session
            st.session_state.rep_session_sha = sha

        _tok_remaining = token_remaining(session, _tok_lifetime)
        _att_type_disp = session.get("att_type", "LECTURE")
        _att_remaining = att_remaining_minutes(session)
        _att_lifetime  = session.get("lifetime_minutes", 60)
        _att_action    = session.get("action", "flag")
        _att_expired   = _att_remaining <= 0

        # ── Kill: auto-push when timer expires ────────────────────────────────────
        if _att_expired and _att_action == "kill" and not st.session_state.rep_kill_triggered:
            st.session_state.rep_kill_triggered = True
            with st.spinner("⏱ Time's up! Auto-submitting attendance…"):
                _ok_k, _msg_k = push_attendance_to_lava(session)
                if _ok_k:
                    delete_session(rep["school"], rep["department"], rep["level"],
                                   att_type=_att_type_disp)
                    st.session_state.rep_session        = None
                    st.session_state.rep_session_sha    = None
                    st.session_state.rep_session_loaded = True
                    st.session_state.rep_kill_triggered = False
            st.success(f"✅ Attendance automatically submitted and saved to LAVA. ({_msg_k})")
            st.stop()

        # ── Session header ────────────────────────────────────────────────────────
        _type_icon = "📖" if _att_type_disp == "LECTURE" else "🔬"
        st.markdown(f"### 🟢 Active — {session['course_code']} &nbsp; {_type_icon} {_att_type_disp.title()}")

        # ── Token display ─────────────────────────────────────────────────────────
        st.markdown(f"""
        <div class="token-display">
            <div class="code">{session['token']}</div>
            <div class="label">Attendance Code — share this with students verbally</div>
        </div>""", unsafe_allow_html=True)
        st.progress(max(0.0, _tok_remaining / _tok_lifetime))
        st.caption(f"⏱ Code refreshes in **{_tok_remaining:.0f}s**")

        # ── Attendance lifetime countdown ─────────────────────────────────────────
        if _att_expired:
            if _att_action == "flag":
                st.warning(
                    f"⏰ Attendance window has closed ({_att_lifetime} min). "
                    f"The session is still open — all new entries are now marked **Late**."
                )
            # kill case handled above by auto-push
        else:
            _mins_left = int(_att_remaining)
            _secs_left = int((_att_remaining - _mins_left) * 60)
            _pct       = max(0.0, _att_remaining / _att_lifetime)
            _bar_color = "#27ae60" if _pct > 0.5 else "#f39c12" if _pct > 0.2 else "#e74c3c"
            st.markdown(
                f"<div style='font-size:0.88rem;opacity:0.8;margin-bottom:0.3rem'>"
                f"⏳ Attendance window: <b>{_mins_left}m {_secs_left:02d}s</b> remaining "
                f"({'Flag late entries' if _att_action=='flag' else '⚡ Auto-submit when done'})"
                f"</div>",
                unsafe_allow_html=True
            )
            st.progress(_pct)

        st.caption(f"Started {session['started_at'][11:16]} · {len(session['entries'])} entries")

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
                        delete_session(rep["school"], rep["department"], rep["level"],
                                          att_type=session.get("att_type","LECTURE"))
                        st.session_state.rep_session        = None
                        st.session_state.rep_session_sha    = None
                        st.session_state.rep_session_loaded = True
                        st.session_state.takeover_confirmed = False
                        st.session_state.rep_kill_triggered = False
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

        # ── Countdown tick ───────────────────────────────────────────────────────────
        time.sleep(1)
        st.rerun()

except Exception as _err:
    if type(_err).__name__ in ("StopException", "RerunException"):
        raise
    _show_error(_err)

