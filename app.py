"""
app.py — ULAS Main App
Students sign attendance. Course reps manage attendance sessions.
"""

import streamlit as st
import time
import pandas as pd

from futo_data import get_schools, get_departments, get_levels
from core import (
    authenticate_user, load_settings, save_session, load_session,
    start_session, refresh_token, token_remaining, validate_token,
    add_entry, edit_entry, delete_entry, validate_matric,
    delete_session, push_attendance_to_lava, session_to_csv,
    build_csv_filename, check_and_register_device,
)

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

st.markdown("""
<div class="hero">
    <h1>🎓 ULAS</h1>
    <div class="sub">Universal Lecture Attendance System</div>
    <div class="badge">Federal University of Technology, Owerri</div>
</div>
""", unsafe_allow_html=True)

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

    # ── STAGE: select ─────────────────────────────────────────────────────────
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
                    st.session_state.stu_stage   = "code"
                    st.rerun()

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

    # ── STAGE: entry ──────────────────────────────────────────────────────────
    elif st.session_state.stu_stage == "entry":
        sess = st.session_state.stu_session
        st.markdown(f"""<div class="info-card">
            <b>Course:</b> {sess['course_code']} &nbsp;|&nbsp;
            <b>Dept:</b> {sess['department']} &nbsp;|&nbsp;
            <b>Level:</b> {sess['level']}L
        </div>""", unsafe_allow_html=True)
        st.markdown("Fill in your details. **Surname first, exactly as on your student ID.**")

        st.markdown("""
        <script>
        (function(){
            function gc(n){var v=document.cookie.match('(^|;) ?'+n+'=([^;]*)(;|$)');return v?v[2]:null;}
            function sc(n,v,d){var e=new Date();e.setTime(e.getTime()+24*60*60*1000*d);
                document.cookie=n+'='+v+';expires='+e.toUTCString()+';path=/;SameSite=Lax';}
            var id=gc('ulas_device_id');
            if(!id){id='dev_'+Math.random().toString(36).substring(2,10)+'_'+Date.now();sc('ulas_device_id',id,365);}
            function inj(){
                var inp=window.parent.document.querySelectorAll('input[aria-label="device_id"]');
                if(inp.length){
                    var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                    s.call(inp[0],id);inp[0].dispatchEvent(new Event('input',{bubbles:true}));
                } else {setTimeout(inj,200);}
            }
            inj();
        })();
        </script>""", unsafe_allow_html=True)

        with st.form("entry_form"):
            surname     = st.text_input("Surname (Family Name)", placeholder="e.g. OKAFOR")
            other_names = st.text_input("Other Names", placeholder="e.g. Chukwuemeka John")
            matric      = st.text_input("Matric Number (11 digits)", placeholder="20200123456", max_chars=11)
            device_id   = st.text_input("device_id", label_visibility="collapsed", key="device_id_input")
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
                dev_id = st.session_state.get("device_id_input", "").strip()
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

                allowed, dmsg = check_and_register_device(
                    st.session_state.stu_school, st.session_state.stu_dept,
                    st.session_state.stu_level, current["course_code"], dev_id, matric,
                )
                if not allowed:
                    st.error(dmsg)
                else:
                    ok, msg = add_entry(current, surname, other_names, matric)
                    if ok:
                        new_sha = save_session(
                            st.session_state.stu_school, st.session_state.stu_dept,
                            st.session_state.stu_level, current, sha,
                        )
                        if new_sha:
                            st.session_state.stu_session = current
                            st.session_state.stu_stage   = "done"
                            st.rerun()
                        else:
                            st.error("Could not save your entry — please try again.")
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
    lifetime = load_settings().get("TOKEN_LIFETIME", 7)

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

    # ── No active session — start one ─────────────────────────────────────────
    if not session:
        st.markdown("### ▶ Start New Attendance")
        with st.form("start_att"):
            course_code = st.text_input("Course Code", placeholder="e.g. CSC301")
            start_btn   = st.form_submit_button("Start Attendance", type="primary")
        if start_btn:
            if not course_code.strip():
                st.error("Please enter a course code.")
            else:
                with st.spinner("Starting..."):
                    session, sha = start_session(
                        rep["school"], rep["department"], rep["level"],
                        course_code, rep["username"],
                    )
                # Store in session_state immediately — no re-fetch needed
                st.session_state.rep_session     = session
                st.session_state.rep_session_sha = sha
                st.rerun()
        st.stop()

    # ── Active session — refresh token if due ─────────────────────────────────
    session, refreshed = refresh_token(session, lifetime)
    if refreshed:
        sha = save_session(rep["school"], rep["department"], rep["level"], session, sha)
        st.session_state.rep_session     = session
        st.session_state.rep_session_sha = sha

    remaining = token_remaining(session, lifetime)

    # ── Token display ──────────────────────────────────────────────────────────
    st.markdown(f"### 🟢 Active — {session['course_code']}")
    st.markdown(f"""
    <div class="token-display">
        <div class="code">{session['token']}</div>
        <div class="label">Attendance Code — share this with students verbally</div>
    </div>""", unsafe_allow_html=True)

    # Live countdown using st.empty + time.sleep loop
    # This renders a real ticking bar without a page reload
    countdown_bar  = st.empty()
    countdown_text = st.empty()

    # Draw current state immediately
    countdown_bar.progress(remaining / lifetime)
    countdown_text.caption(
        f"⏱ Code refreshes in **{remaining:.0f}s** — "
        f"rotates every {lifetime}s · "
        f"Started {session['started_at'][11:16]} · "
        f"{len(session['entries'])} entries"
    )

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
                # Re-fetch fresh copy to avoid SHA conflicts from student writes
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

    # ── Entry table ───────────────────────────────────────────────────────────
    # Always show latest entries by re-fetching (students may have added since last render)
    fresh_s, fresh_sha = load_session(rep["school"], rep["department"], rep["level"])
    if fresh_s:
        st.session_state.rep_session     = fresh_s
        st.session_state.rep_session_sha = fresh_sha
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
    st.warning(f"Closes the session and pushes to **LAVA**. Currently **{len(session['entries'])} entries**.")

    e1, e2 = st.columns(2)
    with e1:
        if st.button("End & Push to LAVA", type="primary", use_container_width=True):
            final, fsha = load_session(rep["school"], rep["department"], rep["level"])
            if final:
                with st.spinner("Pushing to LAVA..."):
                    ok, pmsg = push_attendance_to_lava(final)
                if ok:
                    delete_session(rep["school"], rep["department"], rep["level"])
                    st.session_state.rep_session        = None
                    st.session_state.rep_session_sha    = None
                    st.session_state.rep_session_loaded = True  # stay loaded, just empty
                    st.success(f"✅ Done! {pmsg}")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"Push failed: {pmsg}\n\nSession still open — download backup below.")
            else:
                st.error("Session not found.")
    with e2:
        st.download_button(
            "⬇️ Download CSV Backup",
            session_to_csv(session),
            file_name=build_csv_filename(session),
            mime="text/csv", use_container_width=True,
        )

    # ── Live countdown tick ────────────────────────────────────────────────────
    # Sleep 1 second then rerun so the bar and timer actually tick visibly.
    # Placed at the very end so all widgets above render first before the sleep.
    time.sleep(1)
    st.rerun()
