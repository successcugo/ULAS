"""
advisor_app.py — ULAS Course Advisor Portal
"""

import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from futo_data import get_schools, get_departments, get_levels
from core import (
    authenticate_user, load_users, create_user, update_password,
    delete_user, get_reps_for_dept, load_settings, save_settings,
    hash_password, verify_password, futo_now_str,
)
from github_store import invalidate_cache

st.set_page_config(
    page_title="ULAS Advisor Portal",
    page_icon="🧑‍🏫",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.hero {
    background: linear-gradient(135deg, #003087 0%, #1a56db 100%);
    border-radius: 16px; padding: 2rem; text-align: center;
    color: white; margin-bottom: 2rem;
    box-shadow: 0 4px 20px rgba(0,48,135,0.3);
}
.hero h1 { font-size: 2rem; font-weight: 900; margin: 0; }
.hero .sub { opacity: 0.85; margin-top: 0.3rem; font-size: 0.9rem; }
/* Theme-safe card — transparent bg */
.info-card {
    background: rgba(26, 86, 219, 0.08);
    border-left: 4px solid #1a56db;
    border-radius: 0 8px 8px 0;
    padding: 0.7rem 1rem; margin: 0.5rem 0; color: inherit;
}
.info-card b { color: #1a56db; }
.rep-card {
    background: rgba(26, 86, 219, 0.05);
    border: 1px solid rgba(26, 86, 219, 0.2);
    border-radius: 10px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
    color: inherit;
}
.badge {
    background: rgba(26, 86, 219, 0.15); color: #1a56db;
    border-radius: 20px; padding: 3px 12px;
    font-size: 0.8rem; font-weight: 700;
}
/* Form: border only, no background */
div[data-testid="stForm"] {
    border: 1.5px solid rgba(128,128,128,0.3);
    border-radius: 12px; padding: 1.2rem 1.2rem 0.5rem;
}
.stButton > button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🧑‍🏫 ULAS Advisor Portal</h1>
    <div class="sub">Course Advisor Management Console — FUTO</div>
</div>
""", unsafe_allow_html=True)


# ── Cascading dropdown state + callbacks for "Add Advisor" form ───────────────
for k, v in {"adv_na_school": None, "adv_na_dept": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def _on_na_school():
    st.session_state.adv_na_school = st.session_state._adv_na_school_w
    st.session_state.adv_na_dept   = None

def _on_na_dept():
    st.session_state.adv_na_dept = st.session_state._adv_na_dept_w


# ── Bootstrap ─────────────────────────────────────────────────────────────────
def get_all_advisors():
    return [u for u in load_users().values() if u.get("role") == "advisor"]

if not get_all_advisors():
    st.warning("⚠️ No advisor accounts exist yet. Create the first one to get started.")

    # Cascading selects for bootstrap (outside form so they react)
    for k, v in {"bs_school": None, "bs_dept": None}.items():
        if k not in st.session_state:
            st.session_state[k] = v

    def _bs_school():
        st.session_state.bs_school = st.session_state._bs_school_w
        st.session_state.bs_dept   = None
    def _bs_dept():
        st.session_state.bs_dept = st.session_state._bs_dept_w

    schools   = get_schools()
    bs_s_opts = ["— select —"] + schools
    st.selectbox("School", bs_s_opts,
                 index=bs_s_opts.index(st.session_state.bs_school) if st.session_state.bs_school in bs_s_opts else 0,
                 key="_bs_school_w", on_change=_bs_school)

    bs_depts  = get_departments(st.session_state.bs_school) if st.session_state.bs_school else []
    bs_d_opts = ["— select —"] + bs_depts
    st.selectbox("Department", bs_d_opts,
                 index=bs_d_opts.index(st.session_state.bs_dept) if st.session_state.bs_dept in bs_d_opts else 0,
                 key="_bs_dept_w", on_change=_bs_dept,
                 disabled=not st.session_state.bs_school)

    with st.form("bootstrap"):
        b_uname = st.text_input("Advisor Username")
        b_pwd   = st.text_input("Password", type="password")
        b_pwd2  = st.text_input("Confirm Password", type="password")
        b_btn   = st.form_submit_button("Create Account", type="primary")

    if b_btn:
        if not st.session_state.bs_school or not st.session_state.bs_dept:
            st.error("Please select school and department above.")
        elif not b_uname.strip() or not b_pwd.strip():
            st.error("Username and password are required.")
        elif b_pwd != b_pwd2:
            st.error("Passwords do not match.")
        elif len(b_pwd) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            ok, msg = create_user(b_uname.strip(), b_pwd, "advisor",
                                  st.session_state.bs_school,
                                  st.session_state.bs_dept, None, "system")
            if ok:
                invalidate_cache("__users")
                st.success("Advisor account created! Please log in.")
                st.rerun()
            else:
                st.error(msg)
    st.stop()


# ── Login ─────────────────────────────────────────────────────────────────────
if "adv_user" not in st.session_state:
    st.session_state.adv_user = None

if st.session_state.adv_user is None:
    st.markdown("## Login")
    with st.form("adv_login"):
        uname   = st.text_input("Username")
        pwd     = st.text_input("Password", type="password")
        log_btn = st.form_submit_button("Login", type="primary")
    if log_btn:
        with st.spinner("Authenticating..."):
            user = authenticate_user(uname, pwd, role="advisor")
        if user:
            st.session_state.adv_user = user
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()


# ── Logged-in advisor ─────────────────────────────────────────────────────────
adv        = st.session_state.adv_user
school     = adv["school"]
department = adv["department"]

hc, lc = st.columns([5, 1])
with hc:
    st.markdown(f"""<div class="info-card">
        <b>Advisor:</b> {adv['username']} &nbsp;·&nbsp;
        <b>Dept:</b> {department} &nbsp;·&nbsp;
        <b>School:</b> {school}
    </div>""", unsafe_allow_html=True)
with lc:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Logout"):
        st.session_state.adv_user = None
        invalidate_cache("__users")
        invalidate_cache("__settings")
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["👥 Course Reps", "🔑 Passwords", "⚙️ Settings", "🔧 My Account"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Course Reps
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(f"### Course Reps — {department}")
    invalidate_cache("__users")
    reps     = get_reps_for_dept(school, department)
    levels   = get_levels(department, school)
    occupied = {r["level"] for r in reps}

    if reps:
        for rep in sorted(reps, key=lambda r: r["level"]):
            rc, dc = st.columns([6, 1])
            with rc:
                st.markdown(f"""
                <div class="rep-card">
                    <span class="badge">Level {rep['level']}L</span>
                    &nbsp;&nbsp;<b>{rep['username']}</b>
                    &nbsp;·&nbsp;
                    <span style="font-size:0.85rem;opacity:0.7">
                        Created {rep.get('created_at','')[:10]} by {rep.get('created_by','—')}
                    </span>
                </div>""", unsafe_allow_html=True)
            with dc:
                if st.button("🗑️", key=f"del_{rep['username']}", help=f"Remove {rep['username']}"):
                    delete_user(rep["username"])
                    invalidate_cache("__users")
                    st.success(f"Removed {rep['username']}")
                    st.rerun()
    else:
        st.info("No course reps assigned yet for this department.")

    st.divider()
    available = [l for l in levels if l not in occupied]
    if not available:
        st.success(f"All {len(levels)} levels have a course rep assigned.")
    else:
        st.markdown("### ➕ Assign New Course Rep")
        with st.form("assign_rep"):
            level = st.selectbox("Level", available)
            nu    = st.text_input("Username (must be unique across all of FUTO)")
            np    = st.text_input("Password", type="password")
            np2   = st.text_input("Confirm Password", type="password")
            a_btn = st.form_submit_button("Assign Rep", type="primary")
        if a_btn:
            if not nu.strip() or not np.strip():
                st.error("All fields are required.")
            elif np != np2:
                st.error("Passwords do not match.")
            elif len(np) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                ok, msg = create_user(nu.strip(), np, "rep", school, department, level, adv["username"])
                if ok:
                    invalidate_cache("__users")
                    st.success(f"✅ Rep '{nu}' assigned to Level {level}L!")
                    st.rerun()
                else:
                    st.error(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Passwords
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Change a Course Rep's Password")
    invalidate_cache("__users")
    reps = get_reps_for_dept(school, department)
    if not reps:
        st.info("No course reps in this department.")
    else:
        rep_opts  = {f"{r['username']} (Level {r['level']}L)": r["username"]
                     for r in sorted(reps, key=lambda r: r["level"])}
        sel_lbl   = st.selectbox("Select Rep", list(rep_opts.keys()), key="pw_sel")
        sel_uname = rep_opts[sel_lbl]
        with st.form("rep_pw"):
            new_p  = st.text_input("New Password", type="password")
            new_p2 = st.text_input("Confirm New Password", type="password")
            pw_btn = st.form_submit_button("Update Password", type="primary")
        if pw_btn:
            if not new_p.strip():
                st.error("Password cannot be empty.")
            elif new_p != new_p2:
                st.error("Passwords do not match.")
            elif len(new_p) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                update_password(sel_uname, new_p)
                invalidate_cache("__users")
                st.success(f"Password updated for {sel_uname}.")

    st.divider()
    st.markdown("### Change My Advisor Password")
    with st.form("adv_pw"):
        old_p  = st.text_input("Current Password", type="password")
        my_new = st.text_input("New Password", type="password")
        my_n2  = st.text_input("Confirm New Password", type="password")
        ap_btn = st.form_submit_button("Change My Password", type="primary")
    if ap_btn:
        if not verify_password(old_p, adv["password_hash"]):
            st.error("Current password is incorrect.")
        elif my_new != my_n2:
            st.error("Passwords do not match.")
        elif len(my_new) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            update_password(adv["username"], my_new)
            st.session_state.adv_user["password_hash"] = hash_password(my_new)
            invalidate_cache("__users")
            st.success("Password updated. Takes effect on your next login.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Settings
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### System Settings")
    settings = load_settings()

    with st.form("settings_form"):
        tl  = st.number_input(
            "TOKEN_LIFETIME (seconds)",
            min_value=3, max_value=300, step=1,
            value=int(settings.get("TOKEN_LIFETIME", 7)),
            help="How often the 4-digit code rotates for all departments",
        )
        s_btn = st.form_submit_button("💾 Save Settings", type="primary")

    if s_btn:
        settings["TOKEN_LIFETIME"] = int(tl)
        ok = save_settings(settings)
        if ok:
            invalidate_cache("__settings")
            st.success(f"Saved! TOKEN_LIFETIME is now {tl} seconds.")
        else:
            st.error("Failed to save — GitHub write error.")

    st.divider()
    st.markdown("#### Active Configuration")
    st.markdown(f"""
| Setting | Value |
|---------|-------|
| TOKEN_LIFETIME | **{settings.get('TOKEN_LIFETIME', 7)} seconds** |
| Data Repository | **successcugo/ULASDATA** |
| LAVA Repository | **successcugo/LAVA** |
""")
    st.caption("GitHub credentials are configured in Streamlit Cloud secrets.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — My Account / Add Advisor
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### My Account")
    st.markdown(f"""<div class="info-card">
        <b>Username:</b> {adv['username']}<br>
        <b>School:</b> {adv.get('school','—')}<br>
        <b>Department:</b> {adv.get('department','—')}<br>
        <b>Account created:</b> {adv.get('created_at','—')}
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### Add Advisor for Another Department")
    st.info("Provision advisor accounts for other departments or schools.")

    # Cascading selects OUTSIDE form so they react immediately
    schools   = get_schools()
    na_s_opts = ["— select school —"] + schools
    cur_nas   = st.session_state.adv_na_school
    st.selectbox(
        "School", na_s_opts,
        index=na_s_opts.index(cur_nas) if cur_nas in na_s_opts else 0,
        key="_adv_na_school_w", on_change=_on_na_school,
    )

    na_depts  = get_departments(st.session_state.adv_na_school) if st.session_state.adv_na_school else []
    na_d_opts = ["— select department —"] + na_depts
    cur_nad   = st.session_state.adv_na_dept
    st.selectbox(
        "Department", na_d_opts,
        index=na_d_opts.index(cur_nad) if cur_nad in na_d_opts else 0,
        key="_adv_na_dept_w", on_change=_on_na_dept,
        disabled=not st.session_state.adv_na_school,
    )

    with st.form("new_adv_form"):
        na_uname = st.text_input("New Advisor Username")
        na_pwd   = st.text_input("Password", type="password")
        na_pwd2  = st.text_input("Confirm Password", type="password")
        na_btn   = st.form_submit_button("Create Advisor Account", type="primary")

    if na_btn:
        s = st.session_state.adv_na_school
        d = st.session_state.adv_na_dept
        if not s or not d:
            st.error("Please select school and department above the form.")
        elif not na_uname.strip() or not na_pwd.strip():
            st.error("All fields required.")
        elif na_pwd != na_pwd2:
            st.error("Passwords do not match.")
        elif len(na_pwd) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            ok, msg = create_user(na_uname.strip(), na_pwd, "advisor", s, d, None, adv["username"])
            if ok:
                invalidate_cache("__users")
                st.success(f"Advisor '{na_uname}' created for {d}.")
            else:
                st.error(msg)
