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
    # Kill timer auto-push
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

        # ── Rep tabs: Sessions | Start ────────────────────────────────────────────
        rep_tab_lec, rep_tab_prac = st.tabs(["📖 Lecture Attendance", "🔬 Practical Attendance"])

        def _render_tab(att_type, tab_sfx):
            """Render a fully self-contained attendance tab for one type."""
            _sess_key = f"rep_sess_{tab_sfx}"
            _sha_key  = f"rep_sha_{tab_sfx}"
            _loaded_key = f"rep_loaded_{tab_sfx}"

            # ── Load session from GitHub if not yet loaded this run ───────────────
            if not st.session_state.get(_loaded_key):
                with st.spinner(f"Loading {att_type.title()} session..."):
                    _s, _sh = load_session(rep["school"], rep["department"],
                                           rep["level"], att_type=att_type)
                st.session_state[_sess_key]   = _s
                st.session_state[_sha_key]    = _sh
                st.session_state[_loaded_key] = True

            session = st.session_state.get(_sess_key)
            sha     = st.session_state.get(_sha_key)

            # ── No active session — start form ────────────────────────────────────
            if not session:
                _time_ok, _time_msg = is_school_time()
                if not _time_ok:
                    st.markdown(f"""<div class="info-card" style="text-align:center;padding:1.5rem">
                        <div style="font-size:2rem">🕐</div>
                        <b>Outside School Hours</b><br>
                        <span style="opacity:0.75">{_time_msg}</span>
                    </div>""", unsafe_allow_html=True)
                    return

                _sem_check = load_active_semester()
                if not _sem_check:
                    st.warning("🔒 No active semester. ICT must start a semester first.")
                    return

                st.markdown(f"### ▶ Start {att_type.title()} Attendance")
                with st.form(f"start_{tab_sfx}"):
                    course_code = st.text_input("Course Code", placeholder="e.g. CSC301",
                                                key=f"cc_{tab_sfx}")
                    start_btn   = st.form_submit_button("▶ Start", type="primary")

                if start_btn:
                    if not course_code.strip():
                        st.error("Please enter a course code.")
                    else:
                        with st.spinner("Starting..."):
                            _new_s, _new_sha = start_session(
                                rep["school"], rep["department"], rep["level"],
                                course_code, rep["username"], att_type=att_type,
                            )
                        st.session_state[_sess_key]   = _new_s
                        st.session_state[_sha_key]    = _new_sha
                        st.session_state[_loaded_key] = True
                        st.session_state[f"rep_kill_triggered_{tab_sfx}"] = False
                        st.rerun()

                # ── Session history for this type ─────────────────────────────────
                st.divider()
                st.markdown("### 📋 Session History")
                with st.spinner("Loading..."):
                    _hist = load_session_history(rep["username"])
                if _hist:
                    import pandas as _pd2
                    _hdf = _pd2.DataFrame([h for h in _hist
                                           if h.get("att_type","LECTURE") == att_type])
                    if not _hdf.empty:
                        _hdf.columns = [c.replace("_"," ").title() for c in _hdf.columns]
                        st.dataframe(_hdf, use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No past {att_type.title()} sessions yet.")
                else:
                    st.info("No past sessions yet.")
                return

            # ── Active session ────────────────────────────────────────────────────
            _tok_lifetime = load_settings().get("TOKEN_LIFETIME", 7)
            # Token rotation: flag needed, rerun handled after tab rendering below
            session, refreshed = refresh_token(session, _tok_lifetime)
            if refreshed:
                sha = save_session(rep["school"], rep["department"], rep["level"],
                                   session, sha, att_type=att_type)
                st.session_state[_sess_key] = session
                st.session_state[_sha_key]  = sha

            _att_action  = session.get("action", "flag")
            _att_lifetime = int(session.get("lifetime_minutes", 60))
            _att_expired  = is_att_expired(session)

            # ── Kill: auto-push when timer hits zero ──────────────────────────────
            _kill_key = f"rep_kill_triggered_{tab_sfx}"
            if not st.session_state.get(_kill_key):
                st.session_state[_kill_key] = False
            if _att_expired and _att_action == "kill" and not st.session_state[_kill_key]:
                st.session_state[_kill_key] = True
                with st.spinner("⏱ Time's up! Auto-submitting..."):
                    _ok_k, _msg_k = push_attendance_to_lava(session)
                    if _ok_k:
                        delete_session(rep["school"], rep["department"],
                                       rep["level"], att_type=att_type)
                        st.session_state[_sess_key]   = None
                        st.session_state[_sha_key]    = None
                        st.session_state[_loaded_key] = False
                        st.session_state[_kill_key]   = False
                st.success(f"✅ Auto-submitted to LAVA. {_msg_k}")
                st.rerun()

            # ── Token + JS countdown ──────────────────────────────────────────────
            _tok_val    = session["token"]
            _started_at = session["started_at"]
            _act_label  = "Flag late entries" if _att_action == "flag" else "Auto-submit when done"
            _n_entries  = len(session["entries"])
            _started_disp = _started_at[11:16]
            _course     = session["course_code"]

            _tok_gen_raw = session.get("token_generated_at", futo_ts())

            st.markdown(f"### 🟢 Active — {_course}")
            # ── Token display ─────────────────────────────────────────────────────
            st.markdown(f"""
<div class="token-display">
    <div class="code">{_tok_val}</div>
    <div class="label">Attendance Code</div>
</div>""", unsafe_allow_html=True)

            # ── Countdown display — pure Python, updated on each rerun ────────────
            import math as _math
            _now_ts   = futo_ts()
            _tok_age  = _now_ts - (_tok_gen_raw if isinstance(_tok_gen_raw, (int, float))
                                   else _now_ts)
            _tok_left = max(0, int(_tok_lifetime) - int(_tok_age % int(_tok_lifetime)))
            st.caption(f"⏱ Code refreshes in **{_tok_left}s**")

            _att_elapsed_m = att_elapsed_minutes(session)
            _att_left_m    = _att_lifetime - _att_elapsed_m
            if _att_left_m <= 0:
                if _att_action == "flag":
                    st.warning("⏰ Attendance window closed — new entries are marked Late.")
            else:
                _mins = int(_att_left_m)
                _secs = int((_att_left_m - _mins) * 60)
                _pct  = max(0.0, _att_left_m / _att_lifetime)
                st.markdown(
                    f"<div style='font-size:0.85rem;opacity:0.8;margin-bottom:0.3rem'>"
                    f"⏳ {_mins}m {_secs:02d}s remaining — "
                    f"{'Flag late entries' if _att_action == 'flag' else 'Auto-submit when done'}"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.progress(_pct)

            st.caption(f"Started {_started_disp} · {_n_entries} entries")
            st.divider()

            # ── Manual add entry ──────────────────────────────────────────────────
            with st.expander("➕ Manually Add Entry"):
                with st.form(f"manual_add_{tab_sfx}"):
                    ma_sur = st.text_input("Surname",       key=f"ma_sur_{tab_sfx}")
                    ma_oth = st.text_input("Other Names",   key=f"ma_oth_{tab_sfx}")
                    ma_mat = st.text_input("Matric Number (11 digits)", max_chars=11,
                                           key=f"ma_mat_{tab_sfx}")
                    ma_btn = st.form_submit_button("Add Entry")
                if ma_btn:
                    if not all([ma_sur.strip(), ma_oth.strip(), ma_mat.strip()]):
                        st.error("All fields are required.")
                    else:
                        ok_m, m_msg = validate_matric(ma_mat)
                        if not ok_m:
                            st.error(m_msg)
                        else:
                            ok_a, a_msg = add_entry(session, ma_sur, ma_oth, ma_mat)
                            if ok_a:
                                sha = save_session(rep["school"], rep["department"],
                                                   rep["level"], session, sha,
                                                   att_type=att_type)
                                st.session_state[_sess_key] = session
                                st.session_state[_sha_key]  = sha
                                st.success(f"✅ {a_msg}")
                                st.rerun()
                            else:
                                st.error(a_msg)

            # ── Entry table ───────────────────────────────────────────────────────
            if session["entries"]:
                import pandas as _pd3
                _edf = _pd3.DataFrame(session["entries"])
                _col_map = {"sn":"S/N","surname":"Surname","other_names":"Other Names",
                            "matric":"Matric","time":"Time","late":"Late","concurrent":"Concurrent"}
                _edf = _edf.rename(columns=_col_map)
                _show_cols = [c for c in ["S/N","Surname","Other Names","Matric","Time","Late","Concurrent"]
                              if c in _edf.columns]
                st.dataframe(_edf[_show_cols], use_container_width=True, hide_index=True)
            else:
                st.caption("No entries yet.")

            # ── Edit / Delete entries ─────────────────────────────────────────────
            if session["entries"]:
                with st.expander("✏️ Edit / Delete an Entry"):
                    _entry_opts = {f"{e['sn']}. {e['surname']} {e['other_names']} — {e['matric']}": e["sn"]
                                   for e in session["entries"]}
                    _sel_e = st.selectbox("Select entry", list(_entry_opts.keys()),
                                          key=f"edit_sel_{tab_sfx}")
                    _sel_sn = _entry_opts[_sel_e]
                    _ec1, _ec2 = st.columns(2)
                    with _ec1:
                        if st.button("🗑️ Delete Entry", key=f"del_{tab_sfx}",
                                     use_container_width=True):
                            ok_d, d_msg = delete_entry(session, _sel_sn)
                            if ok_d:
                                sha = save_session(rep["school"], rep["department"],
                                                   rep["level"], session, sha,
                                                   att_type=att_type)
                                st.session_state[_sess_key] = session
                                st.session_state[_sha_key]  = sha
                                st.success(d_msg)
                                st.rerun()
                            else:
                                st.error(d_msg)

            # ── End session ───────────────────────────────────────────────────────
            st.divider()
            _end_key = f"show_end_{tab_sfx}"
            if not st.session_state.get(_end_key):
                st.session_state[_end_key] = False

            if not st.session_state[_end_key]:
                if st.button(f"🔴 End & Push {att_type.title()} Attendance",
                             key=f"end_btn_{tab_sfx}", type="primary",
                             use_container_width=True):
                    st.session_state[_end_key] = True
                    st.rerun()
            else:
                st.warning(f"Push **{len(session['entries'])} entries** to LAVA and end this session?")
                _cc1, _cc2 = st.columns(2)
                with _cc1:
                    if st.button("✅ Confirm Push", key=f"conf_{tab_sfx}",
                                 type="primary", use_container_width=True):
                        with st.spinner("Pushing to LAVA..."):
                            _ok_p, _msg_p = push_attendance_to_lava(session)
                        if _ok_p:
                            delete_session(rep["school"], rep["department"],
                                           rep["level"], att_type=att_type)
                            st.session_state[_sess_key]   = None
                            st.session_state[_sha_key]    = None
                            st.session_state[_loaded_key] = False
                            st.session_state[_end_key]    = False
                            st.success("✅ Pushed to LAVA!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"Push failed: {_msg_p}")
                with _cc2:
                    if st.button("Cancel", key=f"cancel_{tab_sfx}",
                                 use_container_width=True):
                        st.session_state[_end_key] = False
                        st.rerun()

            # ── CSV backup download ───────────────────────────────────────────────
            st.download_button(
                "⬇️ Download CSV Backup",
                session_to_csv(session),
                file_name=build_csv_filename(session),
                mime="text/csv", use_container_width=True,
                key=f"csv_{tab_sfx}",
            )

        with rep_tab_lec:
            try:
                _render_tab("LECTURE", "L")
            except Exception as _tab_err:
                if type(_tab_err).__name__ in ("StopException", "RerunException"):
                    raise
                st.error(f"Something went wrong in Lecture tab. Please refresh.")

        with rep_tab_prac:
            try:
                _render_tab("PRACTICAL", "P")
            except Exception as _tab_err:
                if type(_tab_err).__name__ in ("StopException", "RerunException"):
                    raise
                st.error(f"Something went wrong in Practical tab. Please refresh.")

        # ── Top-level token rotation rerun (safe — outside tabs) ─────────────────
        _tok_lifetime_top = load_settings().get("TOKEN_LIFETIME", 7)
        _now_top = futo_ts()
        _rerun_due = False
        for _sfx_check in ("L", "P"):
            _sess_check = st.session_state.get(f"rep_sess_{_sfx_check}")
            if _sess_check:
                _tok_gen_check = _sess_check.get("token_generated_at", _now_top)
                if isinstance(_tok_gen_check, (int, float)):
                    _age = _now_top - float(_tok_gen_check)
                    if _age >= int(_tok_lifetime_top):
                        _rerun_due = True
                        break
        if _rerun_due:
            import time as _time_top
            _time_top.sleep(1)
            st.rerun()


except Exception as _err:
    if type(_err).__name__ in ("StopException", "RerunException"):
        raise
    _show_error(_err)

