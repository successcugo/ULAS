"""
advisor_app.py — ULAS Course Advisor Portal
Manage course reps, passwords, and system settings.
Run: streamlit run advisor_app.py --server.port 8502
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from futo_data import get_schools, get_departments, get_levels
from core import (
    authenticate_user, load_users, save_users, create_user, update_password,
    delete_user, get_reps_for_dept, get_advisors_for_dept,
    load_settings, save_settings, hash_password, verify_password, futo_now_str,
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
.hero .sub { opacity: 0.85; margin-top: 0.3rem; font-size:0.9rem; }
.card {
    background: #f8f9ff; border: 1px solid #dde;
    border-radius: 10px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
    display: flex; align-items: center; justify-content: space-between;
}
.badge {
    background: #1a56db22; color: #003087;
    border-radius: 20px; padding: 3px 12px;
    font-size: 0.8rem; font-weight: 700;
}
.info-card {
    background: #f0f4ff; border-left: 4px solid #003087;
    border-radius: 0 8px 8px 0; padding: 0.7rem 1rem; margin: 0.5rem 0;
}
div[data-testid="stForm"] {
    border: 1.5px solid #e0e0e0; border-radius: 12px;
    padding: 1.2rem 1.2rem 0.5rem; background: #fafafa;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🧑‍🏫 ULAS Advisor Portal</h1>
    <div class="sub">Course Advisor Management Console — FUTO</div>
</div>
""", unsafe_allow_html=True)


# ── Bootstrap: no advisors yet ────────────────────────────────────────────────
def get_all_advisors() -> list[dict]:
    users = load_users()
    return [u for u in users.values() if u.get("role") == "advisor"]

if not get_all_advisors():
    st.warning("⚠️ No advisor accounts exist yet. Create the first one to get started.")
    with st.form("bootstrap"):
        st.markdown("#### Create First Advisor Account")
        b_school = st.selectbox("School", get_schools())
        b_dept = st.selectbox("Department", get_departments(b_school) if b_school else [])
        b_uname = st.text_input("Advisor Username")
        b_pwd = st.text_input("Password", type="password")
        b_pwd2 = st.text_input("Confirm Password", type="password")
        b_btn = st.form_submit_button("Create Account", type="primary")
    if b_btn:
        if not b_uname.strip() or not b_pwd.strip():
            st.error("Username and password are required.")
        elif b_pwd != b_pwd2:
            st.error("Passwords do not match.")
        elif len(b_pwd) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            ok, msg = create_user(b_uname.strip(), b_pwd, "advisor", b_school, b_dept, None, "system")
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
        uname = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login", type="primary")
    if login_btn:
        with st.spinner("Authenticating..."):
            user = authenticate_user(uname, pwd, role="advisor")
        if user:
            st.session_state.adv_user = user
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()

# ── Advisor is logged in ──────────────────────────────────────────────────────
adv = st.session_state.adv_user
school = adv["school"]
department = adv["department"]

hcol, lcol = st.columns([5, 1])
with hcol:
    st.markdown(f"""
    <div class="info-card">
        <b>Advisor:</b> {adv['username']} &nbsp;·&nbsp;
        <b>Dept:</b> {department} &nbsp;·&nbsp;
        <b>School:</b> {school}
    </div>
    """, unsafe_allow_html=True)
with lcol:
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
    invalidate_cache("__users")  # always fresh here
    reps = get_reps_for_dept(school, department)
    levels = get_levels(department, school)
    occupied = {r["level"] for r in reps}

    if reps:
        for rep in sorted(reps, key=lambda r: r["level"]):
            rcol, dcol = st.columns([6, 1])
            with rcol:
                st.markdown(f"""
                <div class="card">
                    <div>
                        <span class="badge">Level {rep['level']}L</span>
                        &nbsp;&nbsp;<b>{rep['username']}</b>
                        &nbsp;·&nbsp;<span style="color:#666;font-size:0.85rem">
                        Created {rep.get('created_at','')[:10]} by {rep.get('created_by','—')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with dcol:
                if st.button("🗑️", key=f"del_rep_{rep['username']}", help=f"Remove {rep['username']}"):
                    delete_user(rep["username"])
                    invalidate_cache("__users")
                    st.success(f"Removed {rep['username']}")
                    st.rerun()
    else:
        st.info("No course reps assigned yet.")

    st.divider()
    available = [l for l in levels if l not in occupied]
    if not available:
        st.success(f"All {len(levels)} levels have a course rep assigned.")
    else:
        st.markdown("### ➕ Assign New Course Rep")
        with st.form("assign_rep"):
            level = st.selectbox("Level", available)
            nu = st.text_input("Username (must be unique across entire FUTO)")
            np = st.text_input("Password", type="password")
            np2 = st.text_input("Confirm Password", type="password")
            assign_btn = st.form_submit_button("Assign Rep", type="primary")
        if assign_btn:
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
# TAB 2 — Password Management
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Change a Course Rep's Password")
    invalidate_cache("__users")
    reps = get_reps_for_dept(school, department)
    if not reps:
        st.info("No course reps in this department.")
    else:
        rep_opts = {f"{r['username']} (Level {r['level']}L)": r["username"] for r in sorted(reps, key=lambda r: r["level"])}
        sel_label = st.selectbox("Select Rep", list(rep_opts.keys()), key="pw_sel")
        sel_uname = rep_opts[sel_label]
        with st.form("rep_pw_form"):
            new_p = st.text_input("New Password", type="password")
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
    with st.form("adv_pw_form"):
        old_p = st.text_input("Current Password", type="password")
        my_new = st.text_input("New Password", type="password")
        my_new2 = st.text_input("Confirm New Password", type="password")
        adv_pw_btn = st.form_submit_button("Change My Password", type="primary")
    if adv_pw_btn:
        if not verify_password(old_p, adv["password_hash"]):
            st.error("Current password is incorrect.")
        elif my_new != my_new2:
            st.error("New passwords do not match.")
        elif len(my_new) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            update_password(adv["username"], my_new)
            st.session_state.adv_user["password_hash"] = hash_password(my_new)
            invalidate_cache("__users")
            st.success("Your password has been updated. It takes effect on your next login.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Settings
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### System Settings")
    settings = load_settings()

    with st.form("settings_form"):
        tl = st.number_input(
            "TOKEN_LIFETIME (seconds)",
            min_value=3, max_value=300, step=1,
            value=int(settings.get("TOKEN_LIFETIME", 7)),
            help="How often the 4-digit attendance code rotates for all departments",
        )
        save_settings_btn = st.form_submit_button("💾 Save Settings", type="primary")

    if save_settings_btn:
        settings["TOKEN_LIFETIME"] = int(tl)
        ok = save_settings(settings)
        if ok:
            invalidate_cache("__settings")
            st.success(f"Saved! TOKEN_LIFETIME is now {tl} seconds.")
        else:
            st.error("Failed to save settings.")

    st.divider()
    st.markdown("#### Active Configuration")
    st.markdown(f"""
    | Setting | Value |
    |---------|-------|
    | TOKEN_LIFETIME | **{settings.get('TOKEN_LIFETIME', 7)} seconds** |
    | Data Repository | **successcugo/ULASDATA** |
    | LAVA Repository | **successcugo/LAVA** |
    """)
    st.caption("GitHub connection details are configured via Streamlit secrets — contact your system admin to change them.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — My Account / Add Advisor
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### My Account")
    st.markdown(f"""
    <div class="info-card">
        <b>Username:</b> {adv['username']}<br>
        <b>School:</b> {adv.get('school','—')}<br>
        <b>Department:</b> {adv.get('department','—')}<br>
        <b>Account created:</b> {adv.get('created_at','—')}
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("### Add Advisor for Another Department")
    st.info("Use this to provision advisor accounts for other departments or schools.")
    with st.form("new_adv_form"):
        na_school = st.selectbox("School", get_schools(), key="na_school")
        na_dept_list = get_departments(na_school)
        na_dept = st.selectbox("Department", na_dept_list, key="na_dept")
        na_uname = st.text_input("New Advisor Username")
        na_pwd = st.text_input("Password", type="password")
        na_pwd2 = st.text_input("Confirm Password", type="password")
        na_btn = st.form_submit_button("Create Advisor Account", type="primary")
    if na_btn:
        if not na_uname.strip() or not na_pwd.strip():
            st.error("All fields required.")
        elif na_pwd != na_pwd2:
            st.error("Passwords do not match.")
        elif len(na_pwd) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            ok, msg = create_user(na_uname.strip(), na_pwd, "advisor", na_school, na_dept, None, adv["username"])
            if ok:
                invalidate_cache("__users")
                st.success(f"Advisor '{na_uname}' created for {na_dept}.")
            else:
                st.error(msg)
