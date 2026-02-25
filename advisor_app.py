"""
advisor_app.py — ULAS Course Advisor Portal

Access levels:
  ICT (master)  — Can create/delete advisor accounts for any dept.
                  Can change any advisor's password.
                  Credentials set in Streamlit secrets as ICT_USERNAME / ICT_PASSWORD.
  Advisor       — Can manage reps in their own department only.
                  Can change passwords of reps AND co-advisors in their own dept.
                  Cannot create or delete advisor accounts.
"""
from __future__ import annotations

import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from futo_data import get_schools, get_departments, get_levels
from core import (
    authenticate_user, authenticate_ict, load_users, create_user,
    update_password, delete_user, get_reps_for_dept, get_advisors_for_dept,
    get_all_advisors, load_settings, save_settings, hash_password,
    verify_password, futo_now_str,
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
.hero-ict {
    background: linear-gradient(135deg, #5c0099 0%, #9b30ff 100%);
    border-radius: 16px; padding: 2rem; text-align: center;
    color: white; margin-bottom: 2rem;
    box-shadow: 0 4px 20px rgba(92,0,153,0.3);
}
.hero-ict h1 { font-size: 2rem; font-weight: 900; margin: 0; }
.hero-ict .sub { opacity: 0.85; margin-top: 0.3rem; font-size: 0.9rem; }
.info-card {
    background: rgba(26, 86, 219, 0.08);
    border-left: 4px solid #1a56db;
    border-radius: 0 8px 8px 0;
    padding: 0.7rem 1rem; margin: 0.5rem 0; color: inherit;
}
.info-card b { color: #1a56db; }
.ict-card {
    background: rgba(155, 48, 255, 0.08);
    border-left: 4px solid #9b30ff;
    border-radius: 0 8px 8px 0;
    padding: 0.7rem 1rem; margin: 0.5rem 0; color: inherit;
}
.ict-card b { color: #9b30ff; }
.rep-card {
    background: rgba(26, 86, 219, 0.05);
    border: 1px solid rgba(26, 86, 219, 0.2);
    border-radius: 10px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
    color: inherit;
}
.adv-card {
    background: rgba(155, 48, 255, 0.05);
    border: 1px solid rgba(155, 48, 255, 0.2);
    border-radius: 10px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
    color: inherit;
}
.badge-rep {
    background: rgba(26, 86, 219, 0.15); color: #1a56db;
    border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 700;
}
.badge-adv {
    background: rgba(155, 48, 255, 0.15); color: #9b30ff;
    border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 700;
}
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


# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {
    "portal_role": None,   # 'ict' | 'advisor'
    "adv_user": None,      # advisor user dict (if role == 'advisor')
    # Cascading dropdowns
    "adv_na_school": None, "adv_na_dept": None,
    "bs_school": None,     "bs_dept": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def do_logout():
    st.session_state.portal_role  = None
    st.session_state.adv_user     = None
    st.session_state.adv_na_school = None
    st.session_state.adv_na_dept   = None
    invalidate_cache("__users")
    invalidate_cache("__settings")


# ── Cascading dropdown helpers ─────────────────────────────────────────────────
def _on_na_school():
    st.session_state.adv_na_school = st.session_state._adv_na_school_w
    st.session_state.adv_na_dept   = None

def _on_na_dept():
    st.session_state.adv_na_dept = st.session_state._adv_na_dept_w

def _on_bs_school():
    st.session_state.bs_school = st.session_state._bs_school_w
    st.session_state.bs_dept   = None

def _on_bs_dept():
    st.session_state.bs_dept = st.session_state._bs_dept_w


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIN SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.portal_role is None:
    st.markdown("## Login")
    st.markdown("Log in as a **Course Advisor** or as **ICT** (master admin).")

    login_tab, ict_tab = st.tabs(["🧑‍🏫 Course Advisor Login", "🔐 ICT Master Login"])

    with login_tab:
        with st.form("adv_login"):
            uname   = st.text_input("Advisor Username")
            pwd     = st.text_input("Password", type="password")
            log_btn = st.form_submit_button("Login as Advisor", type="primary")
        if log_btn:
            with st.spinner("Authenticating..."):
                user = authenticate_user(uname, pwd, role="advisor")
            if user:
                st.session_state.portal_role = "advisor"
                st.session_state.adv_user    = user
                st.rerun()
            else:
                st.error("Invalid advisor credentials.")

    with ict_tab:
        with st.form("ict_login"):
            ict_u   = st.text_input("ICT Username")
            ict_p   = st.text_input("ICT Password", type="password")
            ict_btn = st.form_submit_button("Login as ICT", type="primary")
        if ict_btn:
            if authenticate_ict(ict_u, ict_p):
                st.session_state.portal_role = "ict"
                st.rerun()
            else:
                st.error("Invalid ICT credentials.")

    # Bootstrap: if no advisors yet, only show ICT login and a note
    if not get_all_advisors():
        st.info("ℹ️ No advisor accounts exist yet. Log in as ICT to create the first advisor.")

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
#  ICT MASTER DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.portal_role == "ict":

    st.markdown("""
    <div class="hero-ict">
        <h1>🔐 ICT Master Console</h1>
        <div class="sub">Full administrative access — handle with care</div>
    </div>
    """, unsafe_allow_html=True)

    hc, lc = st.columns([5, 1])
    with hc:
        st.markdown('<div class="ict-card"><b>Logged in as:</b> ICT Master</div>',
                    unsafe_allow_html=True)
    with lc:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Logout", key="ict_logout"):
            do_logout()
            st.rerun()

    ict_tab1, ict_tab2, ict_tab3 = st.tabs(
        ["👥 All Advisors", "➕ Create Advisor", "⚙️ Settings"]
    )

    # ── ICT TAB 1 — View & manage all advisors ────────────────────────────────
    with ict_tab1:
        st.markdown("### All Advisor Accounts")
        invalidate_cache("__users")
        advisors = get_all_advisors()
        if not advisors:
            st.info("No advisor accounts exist yet. Create one in the next tab.")
        else:
            for adv in sorted(advisors, key=lambda a: (a["school"], a["department"], a["username"])):
                ac, pc, dc = st.columns([5, 2, 1])
                with ac:
                    st.markdown(f"""
                    <div class="adv-card">
                        <span class="badge-adv">Advisor</span>
                        &nbsp;&nbsp;<b>{adv['username']}</b>
                        &nbsp;·&nbsp; {adv['department']}
                        <span style="font-size:0.8rem;opacity:0.6">
                            &nbsp;·&nbsp; {adv['school'][:30]}
                        </span>
                    </div>""", unsafe_allow_html=True)
                with pc:
                    if st.button("🔑 Reset PW", key=f"ict_pw_{adv['username']}"):
                        st.session_state[f"ict_reset_{adv['username']}"] = True
                with dc:
                    if st.button("🗑️", key=f"ict_del_{adv['username']}", help=f"Delete {adv['username']}"):
                        st.session_state[f"ict_delconfirm_{adv['username']}"] = True

                # Inline password reset
                if st.session_state.get(f"ict_reset_{adv['username']}"):
                    with st.form(f"ict_pw_form_{adv['username']}"):
                        np  = st.text_input("New Password", type="password", key=f"np_{adv['username']}")
                        np2 = st.text_input("Confirm",     type="password", key=f"np2_{adv['username']}")
                        ok_btn  = st.form_submit_button("Set Password", type="primary")
                        can_btn = st.form_submit_button("Cancel")
                    if ok_btn:
                        if np != np2:
                            st.error("Passwords do not match.")
                        elif len(np) < 6:
                            st.error("Minimum 6 characters.")
                        else:
                            update_password(adv["username"], np)
                            invalidate_cache("__users")
                            st.success(f"Password updated for {adv['username']}.")
                            st.session_state.pop(f"ict_reset_{adv['username']}", None)
                            st.rerun()
                    if can_btn:
                        st.session_state.pop(f"ict_reset_{adv['username']}", None)
                        st.rerun()

                # Inline delete confirm
                if st.session_state.get(f"ict_delconfirm_{adv['username']}"):
                    st.warning(f"Delete advisor **{adv['username']}** ({adv['department']})? This cannot be undone.")
                    y, n = st.columns(2)
                    with y:
                        if st.button("Yes, delete", type="primary", key=f"ict_delyes_{adv['username']}"):
                            delete_user(adv["username"])
                            invalidate_cache("__users")
                            st.session_state.pop(f"ict_delconfirm_{adv['username']}", None)
                            st.rerun()
                    with n:
                        if st.button("Cancel", key=f"ict_delno_{adv['username']}"):
                            st.session_state.pop(f"ict_delconfirm_{adv['username']}", None)
                            st.rerun()

    # ── ICT TAB 2 — Create advisor ────────────────────────────────────────────
    with ict_tab2:
        st.markdown("### Create New Advisor Account")
        st.info("Only ICT can create advisor accounts. Advisors are then responsible for their own departments.")

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

        with st.form("ict_create_adv"):
            na_uname = st.text_input("Advisor Username")
            na_pwd   = st.text_input("Password", type="password")
            na_pwd2  = st.text_input("Confirm Password", type="password")
            na_btn   = st.form_submit_button("Create Advisor", type="primary")

        if na_btn:
            s = st.session_state.adv_na_school
            d = st.session_state.adv_na_dept
            if not s or not d:
                st.error("Please select school and department above.")
            elif not na_uname.strip() or not na_pwd.strip():
                st.error("All fields required.")
            elif na_pwd != na_pwd2:
                st.error("Passwords do not match.")
            elif len(na_pwd) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                ok, msg = create_user(na_uname.strip(), na_pwd, "advisor", s, d, None, "ICT")
                if ok:
                    invalidate_cache("__users")
                    st.success(f"✅ Advisor '{na_uname}' created for {d}.")
                    st.session_state.adv_na_school = None
                    st.session_state.adv_na_dept   = None
                else:
                    st.error(msg)

    # ── ICT TAB 3 — Settings ──────────────────────────────────────────────────
    with ict_tab3:
        st.markdown("### System Settings")
        settings = load_settings()
        with st.form("ict_settings"):
            tl    = st.number_input(
                "TOKEN_LIFETIME (seconds)",
                min_value=3, max_value=300, step=1,
                value=int(settings.get("TOKEN_LIFETIME", 7)),
                help="How often the 4-digit attendance code rotates",
            )
            s_btn = st.form_submit_button("💾 Save", type="primary")
        if s_btn:
            settings["TOKEN_LIFETIME"] = int(tl)
            if save_settings(settings):
                invalidate_cache("__settings")
                st.success(f"Saved. TOKEN_LIFETIME = {tl}s")
            else:
                st.error("GitHub write failed.")

        st.divider()
        st.markdown(f"""
| Setting | Value |
|---------|-------|
| TOKEN_LIFETIME | **{settings.get('TOKEN_LIFETIME',7)} seconds** |
| Data Repository | **successcugo/ULASDATA** |
| LAVA Repository | **successcugo/LAVA** |
""")
        st.caption("GitHub credentials are in Streamlit Cloud secrets.")

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
#  ADVISOR DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.portal_role == "advisor":

    adv        = st.session_state.adv_user
    school     = adv["school"]
    department = adv["department"]

    hc, lc = st.columns([5, 1])
    with hc:
        st.markdown(f"""<div class="info-card">
            <b>Advisor:</b> {adv['username']} &nbsp;·&nbsp;
            <b>Dept:</b> {department} &nbsp;·&nbsp;
            <b>School:</b> {school[:35]}
        </div>""", unsafe_allow_html=True)
    with lc:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Logout", key="adv_logout"):
            do_logout()
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["👥 Course Reps", "🔑 Passwords", "🔧 My Account"])

    # ── TAB 1 — Course Reps ───────────────────────────────────────────────────
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
                        <span class="badge-rep">Level {rep['level']}L</span>
                        &nbsp;&nbsp;<b>{rep['username']}</b>
                        &nbsp;·&nbsp;
                        <span style="font-size:0.85rem;opacity:0.65">
                            Created {rep.get('created_at','')[:10]}
                            by {rep.get('created_by','—')}
                        </span>
                    </div>""", unsafe_allow_html=True)
                with dc:
                    if st.button("🗑️", key=f"del_rep_{rep['username']}", help=f"Remove {rep['username']}"):
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

    # ── TAB 2 — Passwords ─────────────────────────────────────────────────────
    with tab2:
        invalidate_cache("__users")
        reps     = get_reps_for_dept(school, department)
        co_advs  = get_advisors_for_dept(school, department)
        # Co-advisors = all advisors in same dept except self
        co_advs  = [a for a in co_advs if a["username"] != adv["username"]]

        # ── Reset a rep's password ────────────────────────────────────────────
        st.markdown("### Change a Course Rep's Password")
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

        # ── Reset a co-advisor's password ─────────────────────────────────────
        st.divider()
        st.markdown("### Change a Co-Advisor's Password")
        st.caption("You can reset passwords for other advisors in your department.")
        if not co_advs:
            st.info("No other advisors in your department.")
        else:
            co_opts   = {a["username"]: a["username"] for a in co_advs}
            co_sel    = st.selectbox("Select Co-Advisor", list(co_opts.keys()), key="co_pw_sel")
            with st.form("co_adv_pw"):
                co_new  = st.text_input("New Password", type="password")
                co_new2 = st.text_input("Confirm New Password", type="password")
                co_btn  = st.form_submit_button("Update Co-Advisor Password", type="primary")
            if co_btn:
                if not co_new.strip():
                    st.error("Password cannot be empty.")
                elif co_new != co_new2:
                    st.error("Passwords do not match.")
                elif len(co_new) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    update_password(co_sel, co_new)
                    invalidate_cache("__users")
                    st.success(f"Password updated for {co_sel}.")

        # ── Change own password ────────────────────────────────────────────────
        st.divider()
        st.markdown("### Change My Password")
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
                st.success("Password updated.")

    # ── TAB 3 — My Account ────────────────────────────────────────────────────
    with tab3:
        st.markdown("### My Account")
        st.markdown(f"""<div class="info-card">
            <b>Username:</b> {adv['username']}<br>
            <b>School:</b> {adv.get('school','—')}<br>
            <b>Department:</b> {adv.get('department','—')}<br>
            <b>Account created:</b> {adv.get('created_at','—')}<br>
            <b>Created by:</b> {adv.get('created_by','—')}
        </div>""", unsafe_allow_html=True)

        st.divider()
        st.markdown("### Co-Advisors in My Department")
        invalidate_cache("__users")
        co_advs = get_advisors_for_dept(school, department)
        if len(co_advs) <= 1:
            st.info("You are the only advisor for this department.")
        else:
            for a in co_advs:
                if a["username"] != adv["username"]:
                    st.markdown(f"""<div class="adv-card">
                        <span class="badge-adv">Advisor</span>
                        &nbsp;&nbsp;<b>{a['username']}</b>
                        &nbsp;·&nbsp; Created {a.get('created_at','')[:10]}
                    </div>""", unsafe_allow_html=True)

        st.divider()
        st.caption(
            "To create or delete advisor accounts, or to manage settings, "
            "contact ICT administration."
        )
