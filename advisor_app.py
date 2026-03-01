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

from futo_data import get_schools, get_departments, get_levels, get_full_structure, save_structure, invalidate_structure_cache, get_school_abbr
from core import (
    authenticate_user, authenticate_ict, load_users, create_user,
    update_password, delete_user, get_reps_for_dept, get_advisors_for_dept,
    get_all_advisors, load_settings, save_settings, hash_password,
    verify_password, futo_now_str, get_dept_abbreviation, set_dept_abbreviation,
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

# ── Fixed footer ─────────────────────────────────────────────────────────────
st.markdown('\n<style>\n.ulas-footer {\n    position: fixed;\n    bottom: 0; left: 0; right: 0;\n    text-align: center;\n    padding: 0.45rem 1rem;\n    font-size: 0.78rem;\n    background: rgba(0,0,0,0.45);\n    backdrop-filter: blur(6px);\n    -webkit-backdrop-filter: blur(6px);\n    color: rgba(255,255,255,0.55);\n    letter-spacing: 0.04em;\n    z-index: 9999;\n    border-top: 1px solid rgba(255,255,255,0.07);\n}\n.ulas-footer b { color: rgba(255,255,255,0.8); font-weight: 600; }\n.ulas-footer .dot { color: rgba(255,255,255,0.3); margin: 0 0.3em; }\n/* Push content up so footer never overlaps last element */\nsection.main > div { padding-bottom: 2.8rem !important; }\n</style>\n<div class="ulas-footer">\n    Made with ❤️ by\n    <b>SESET</b><span class="dot">•</span><b>EPE</b><span class="dot">•</span><b>2030/2031</b>\n</div>\n', unsafe_allow_html=True)

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
            if authenticate_ict(
                ict_u, ict_p,
                expected_user=st.secrets.get("ICT_USERNAME", ""),
                expected_pw=st.secrets.get("ICT_PASSWORD", ""),
            ):
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

    ict_tab1, ict_tab2, ict_tab3, ict_tab4 = st.tabs(
        ["👥 All Advisors", "➕ Create Advisor", "🏫 Schools & Depts", "⚙️ Settings"]
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

    # ── ICT TAB 3 — Schools & Departments ───────────────────────────────────────
    with ict_tab3:
        st.markdown("### 🏫 Schools & Departments")
        st.caption(
            "Changes take effect immediately across all ULAS apps. "
            "Deleting a school or department does **not** remove existing user accounts or session data."
        )

        invalidate_structure_cache()
        struct    = get_full_structure()
        schools_d = struct.get("schools", {})
        abbrevs   = struct.get("abbreviations", {})

        def _save(s, a):
            return save_structure({"schools": s, "abbreviations": a})

        # ── Add School ────────────────────────────────────────────────────────
        with st.expander("➕ Add New School", expanded=False):
            with st.form("add_school_form"):
                ns_name  = st.text_input("Full school name", placeholder="School of XYZ (SXYZ)")
                ns_abbr  = st.text_input("School abbreviation", placeholder="SXYZ", max_chars=8)
                ns_btn   = st.form_submit_button("Add School", type="primary")
            if ns_btn:
                if not ns_name.strip() or not ns_abbr.strip():
                    st.error("Both name and abbreviation are required.")
                elif ns_name.strip() in schools_d:
                    st.error("A school with that name already exists.")
                else:
                    schools_d[ns_name.strip()] = {}
                    abbrevs[ns_name.strip()]   = ns_abbr.strip().upper()
                    if _save(schools_d, abbrevs):
                        st.success(f"✅ School '{ns_name.strip()}' added.")
                        st.rerun()
                    else:
                        st.error("GitHub write failed.")

        st.divider()

        # ── Per-school management ─────────────────────────────────────────────
        if not schools_d:
            st.info("No schools defined yet. Add one above.")
        else:
            sel_school = st.selectbox(
                "Select school to manage",
                sorted(schools_d.keys()),
                key="ict_sel_school",
            )
            depts = schools_d.get(sel_school, {})
            cur_abbr = abbrevs.get(sel_school, "")

            sc1, sc2 = st.columns([3, 1])
            with sc1:
                st.markdown(f"""<div class="ict-card">
                    <b>{sel_school}</b> &nbsp;·&nbsp;
                    Abbreviation: <b>{cur_abbr}</b> &nbsp;·&nbsp;
                    {len(depts)} department(s)
                </div>""", unsafe_allow_html=True)
            with sc2:
                if st.button("🗑️ Delete School", key="del_school_btn"):
                    st.session_state["confirm_del_school"] = sel_school

            # Delete school confirm
            if st.session_state.get("confirm_del_school") == sel_school:
                st.warning(
                    f"Delete **{sel_school}** and all its departments? "
                    "Existing user accounts will still exist but their school will no longer appear in dropdowns."
                )
                cy, cn = st.columns(2)
                with cy:
                    if st.button("Yes, delete school", type="primary", key="yes_del_school"):
                        del schools_d[sel_school]
                        abbrevs.pop(sel_school, None)
                        _save(schools_d, abbrevs)
                        st.session_state.pop("confirm_del_school", None)
                        st.rerun()
                with cn:
                    if st.button("Cancel", key="no_del_school"):
                        st.session_state.pop("confirm_del_school", None)
                        st.rerun()

            # Edit school abbreviation inline
            with st.expander("✏️ Edit School Abbreviation"):
                with st.form("edit_abbr_form"):
                    new_abbr = st.text_input("Abbreviation", value=cur_abbr, max_chars=8)
                    ea_btn   = st.form_submit_button("Save Abbreviation", type="primary")
                if ea_btn:
                    if new_abbr.strip():
                        abbrevs[sel_school] = new_abbr.strip().upper()
                        if _save(schools_d, abbrevs):
                            st.success(f"Abbreviation updated to {new_abbr.strip().upper()}.")
                            st.rerun()
                        else:
                            st.error("GitHub write failed.")

            st.markdown(f"#### Departments in {abbrevs.get(sel_school, sel_school)}")

            # ── Add Department ────────────────────────────────────────────────
            with st.expander("➕ Add Department to this School"):
                with st.form("add_dept_form"):
                    nd_name   = st.text_input("Department name", placeholder="e.g. Software Engineering")
                    nd_levels = st.number_input("Number of levels", min_value=1, max_value=8, value=4, step=1)
                    nd_btn    = st.form_submit_button("Add Department", type="primary")
                if nd_btn:
                    if not nd_name.strip():
                        st.error("Department name cannot be empty.")
                    elif nd_name.strip() in depts:
                        st.error("That department already exists in this school.")
                    else:
                        schools_d[sel_school][nd_name.strip()] = int(nd_levels)
                        if _save(schools_d, abbrevs):
                            st.success(f"✅ Department '{nd_name.strip()}' added with {nd_levels} levels.")
                            st.rerun()
                        else:
                            st.error("GitHub write failed.")

            # ── List & manage existing departments ────────────────────────────
            if not depts:
                st.info("No departments in this school yet.")
            else:
                for dept_name, num_levels in sorted(depts.items()):
                    dc1, dc2, dc3 = st.columns([5, 2, 1])
                    safe_key = dept_name.replace(" ", "_").replace("(", "").replace(")", "")

                    with dc1:
                        st.markdown(f"""<div class="rep-card">
                            <b>{dept_name}</b>
                            &nbsp;·&nbsp;
                            <span style="opacity:0.65">{num_levels} levels
                            ({", ".join(str((i+1)*100) for i in range(int(num_levels)))})</span>
                        </div>""", unsafe_allow_html=True)

                    with dc2:
                        # Inline level editor
                        if st.button("✏️ Edit Levels", key=f"edit_lvl_{safe_key}"):
                            st.session_state[f"editing_{safe_key}"] = True

                    with dc3:
                        if st.button("🗑️", key=f"del_dept_{safe_key}", help=f"Delete {dept_name}"):
                            st.session_state[f"confirm_del_dept_{safe_key}"] = True

                    # Delete department confirm
                    if st.session_state.get(f"confirm_del_dept_{safe_key}"):
                        st.warning(f"Delete department **{dept_name}**?")
                        yy, nn = st.columns(2)
                        with yy:
                            if st.button("Yes, delete", type="primary", key=f"yes_del_dept_{safe_key}"):
                                del schools_d[sel_school][dept_name]
                                _save(schools_d, abbrevs)
                                st.session_state.pop(f"confirm_del_dept_{safe_key}", None)
                                st.rerun()
                        with nn:
                            if st.button("Cancel", key=f"no_del_dept_{safe_key}"):
                                st.session_state.pop(f"confirm_del_dept_{safe_key}", None)
                                st.rerun()

                    # Level editor
                    if st.session_state.get(f"editing_{safe_key}"):
                        with st.form(f"edit_levels_form_{safe_key}"):
                            new_levels = st.number_input(
                                f"Number of levels for {dept_name}",
                                min_value=1, max_value=8,
                                value=int(num_levels), step=1,
                            )
                            sl_save = st.form_submit_button("💾 Save Levels", type="primary")
                            sl_cancel = st.form_submit_button("Cancel")
                        if sl_save:
                            schools_d[sel_school][dept_name] = int(new_levels)
                            if _save(schools_d, abbrevs):
                                st.success(f"Levels updated to {new_levels}.")
                                st.session_state.pop(f"editing_{safe_key}", None)
                                st.rerun()
                            else:
                                st.error("GitHub write failed.")
                        if sl_cancel:
                            st.session_state.pop(f"editing_{safe_key}", None)
                            st.rerun()

    # ── ICT TAB 4 — Settings ──────────────────────────────────────────────────
    with ict_tab4:
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

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["👥 Course Reps", "🔑 Passwords", "🏷️ Abbreviation", "📊 GPA Calculator", "📈 Dept Stats", "🔧 My Account"])

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

    # ── TAB 3 — Department Abbreviation ──────────────────────────────────────
    with tab3:
        st.markdown(f"### Department Abbreviation — {department}")
        st.markdown(
            "Set a **3-letter abbreviation** for your department. "
            "This is used in attendance file names pushed to LAVA, "
            "e.g. `SEETCSC**EEE**300_2026-01-15.csv`."
        )

        current_abbr = get_dept_abbreviation(department)
        st.markdown(f"""<div class="info-card">
            <b>Current abbreviation:</b> &nbsp;
            <span style="font-size:1.4rem;font-weight:900;letter-spacing:2px">{current_abbr}</span>
            &nbsp;&nbsp;<span style="opacity:0.6;font-size:0.85rem">(used in all future file names)</span>
        </div>""", unsafe_allow_html=True)

        with st.form("abbr_form"):
            new_abbr = st.text_input(
                "New Abbreviation (3 letters)",
                value=current_abbr,
                max_chars=3,
                placeholder="e.g. EEE",
            )
            abbr_btn = st.form_submit_button("💾 Save Abbreviation", type="primary")

        if abbr_btn:
            cleaned = new_abbr.strip().upper()
            if not cleaned:
                st.error("Abbreviation cannot be empty.")
            elif not cleaned.isalpha():
                st.error("Abbreviation must contain letters only.")
            elif len(cleaned) != 3:
                st.error(f"Abbreviation must be exactly 3 letters (you entered {len(cleaned)}).")
            else:
                ok = set_dept_abbreviation(department, cleaned)
                if ok:
                    invalidate_cache("__settings")
                    st.success(f"✅ Abbreviation for **{department}** set to **{cleaned}**.")
                    st.caption("All attendance files pushed from now on will use this abbreviation.")
                else:
                    st.error("Failed to save — GitHub write error.")

        st.divider()
        st.markdown("#### Example filename with this abbreviation")
        example = f"SEET · CSC301 · {current_abbr} · Level 300 · 2026-01-15"
        st.markdown(f"`SEETCSC301{current_abbr}300_2026-01-15.csv`")
        st.caption(f"Format: SCHOOL + COURSECODE + ABBR + LEVEL + _ + DATE .csv")

    # ── TAB 4 — GPA Calculator ───────────────────────────────────────────────
    with tab4:
        st.markdown("### 📊 GPA Calculator")
        st.markdown(
            "Enter each course with its unit load and grade. "
            "GPA = Total Weighted Points ÷ Total Units."
        )

        # FUTO grade → point mapping
        GRADE_POINTS = {"A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0, "E": 1.0, "F": 0.0}

        # Grading reference
        with st.expander("📋 FUTO Grading Scale"):
            st.markdown("""
| Grade | Point |
|-------|-------|
| A | 5.0 |
| B | 4.0 |
| C | 3.0 |
| D | 2.0 |
| E | 1.0 |
| F | 0.0 |
""")

        # Keep courses in session state so they persist across reruns
        if "gpa_courses" not in st.session_state:
            st.session_state.gpa_courses = [
                {"code": "", "units": 1, "grade": "A"}
            ]

        st.markdown("#### Course Entries")

        # Render each course row
        to_delete = None
        for i, course in enumerate(st.session_state.gpa_courses):
            c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
            with c1:
                st.session_state.gpa_courses[i]["code"] = st.text_input(
                    "Course Code", value=course["code"],
                    key=f"gpa_code_{i}", placeholder="e.g. CSC301",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with c2:
                st.session_state.gpa_courses[i]["units"] = st.number_input(
                    "Units", min_value=1, max_value=6, step=1,
                    value=course["units"], key=f"gpa_units_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with c3:
                st.session_state.gpa_courses[i]["grade"] = st.selectbox(
                    "Grade", list(GRADE_POINTS.keys()),
                    index=list(GRADE_POINTS.keys()).index(course["grade"]),
                    key=f"gpa_grade_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with c4:
                st.markdown("<br>" if i == 0 else "", unsafe_allow_html=True)
                if len(st.session_state.gpa_courses) > 1:
                    if st.button("✕", key=f"gpa_del_{i}", help="Remove this course"):
                        to_delete = i

        if to_delete is not None:
            st.session_state.gpa_courses.pop(to_delete)
            st.rerun()

        col_add, col_clear = st.columns([1, 1])
        with col_add:
            if st.button("➕ Add Course", use_container_width=True):
                st.session_state.gpa_courses.append({"code": "", "units": 1, "grade": "A"})
                st.rerun()
        with col_clear:
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.gpa_courses = [{"code": "", "units": 1, "grade": "A"}]
                st.rerun()

        st.divider()

        # ── Calculation ───────────────────────────────────────────────────────
        courses = st.session_state.gpa_courses
        valid   = [c for c in courses if str(c["code"]).strip()]

        if not valid:
            st.info("Add at least one course with a course code to calculate GPA.")
        else:
            total_units    = sum(c["units"] for c in valid)
            total_weighted = sum(c["units"] * GRADE_POINTS[c["grade"]] for c in valid)
            gpa            = total_weighted / total_units if total_units > 0 else 0.0

            # Colour based on GPA range
            if gpa >= 4.5:
                gpa_colour, standing = "#27ae60", "First Class"
            elif gpa >= 3.5:
                gpa_colour, standing = "#2980b9", "Second Class Upper"
            elif gpa >= 2.4:
                gpa_colour, standing = "#f39c12", "Second Class Lower"
            elif gpa >= 1.5:
                gpa_colour, standing = "#e67e22", "Third Class"
            else:
                gpa_colour, standing = "#c0392b", "Pass / Fail"

            st.markdown(f"""
            <div style="
                background: rgba(0,0,0,0.05);
                border: 2px solid {gpa_colour};
                border-radius: 14px;
                padding: 1.5rem;
                text-align: center;
                margin: 1rem 0;
                color: inherit;
            ">
                <div style="font-size:3rem;font-weight:900;color:{gpa_colour};line-height:1">
                    {gpa:.2f}
                </div>
                <div style="font-size:1rem;font-weight:700;color:{gpa_colour};margin-top:0.3rem">
                    {standing}
                </div>
                <div style="font-size:0.8rem;opacity:0.65;margin-top:0.5rem">
                    {total_weighted:.1f} weighted points ÷ {total_units} units
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Breakdown table
            st.markdown("#### Breakdown")
            import pandas as pd
            rows = []
            for c in valid:
                wp = c["units"] * GRADE_POINTS[c["grade"]]
                rows.append({
                    "Course Code":     c["code"].upper(),
                    "Units":           c["units"],
                    "Grade":           c["grade"],
                    "Grade Point":     GRADE_POINTS[c["grade"]],
                    "Weighted Points": f"{GRADE_POINTS[c['grade']]} × {c['units']} = {wp:.0f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            wp_parts = " + ".join(
                str(int(c["units"] * GRADE_POINTS[c["grade"]])) for c in valid
            )
            st.markdown(
                f"**Total Weighted Points** = {wp_parts} = **{total_weighted:.0f}**\n\n"
                f"**Total Units** = {total_units}\n\n"
                f"**GPA** = {total_weighted:.0f} ÷ {total_units} = **{gpa:.2f}**"
            )

    # ── TAB 5 — Department Statistics ────────────────────────────────────────
    with tab5:
        import requests as _req
        import pandas as _pd
        from io import BytesIO as _BytesIO
        from datetime import date as _date, timedelta as _td
        import plotly.express as _px

        st.markdown(f"### 📈 Department Statistics — {department}")
        st.caption(
            "Reads attendance archives from LAVA. "
            "Identifies records by your department abbreviation + selected level."
        )

        # ── LAVA connection ───────────────────────────────────────────────────
        try:
            _lava_token = st.secrets["GITHUB_PAT"]
            _lava_repo  = f"{st.secrets['LAVA_OWNER']}/{st.secrets['LAVA_REPO']}"
            _lava_hdrs  = {
                "Authorization": f"token {_lava_token}",
                "Accept": "application/vnd.github.v3+json",
            }
        except Exception:
            st.error("LAVA secrets not configured. Add LAVA_OWNER and LAVA_REPO to secrets.")
            st.stop()

        @st.cache_data(ttl=120, show_spinner=False)
        def _gh_list_stats(path):
            url = f"https://api.github.com/repos/{_lava_repo}/contents/{path}"
            r   = _req.get(url, headers=_lava_hdrs, timeout=10)
            if r.status_code != 200:
                return []
            d = r.json()
            return d if isinstance(d, list) else []

        @st.cache_data(ttl=300, show_spinner=False)
        def _fetch_csv_stats(download_url):
            return _req.get(download_url, headers=_lava_hdrs, timeout=10).content

        # ── Filters ───────────────────────────────────────────────────────────
        dept_abbr       = get_dept_abbreviation(department)
        school_abbr_val = get_school_abbr(school)
        levels          = get_levels(department, school)

        fc1, fc2, fc3 = st.columns([1, 1, 1])
        with fc1:
            sel_level = st.selectbox("Level", levels, key="stats_level")
        with fc2:
            today     = _date.today()
            date_from = st.date_input(
                "From date",
                value=today.replace(day=1),   # start of current month
                key="stats_from",
            )
        with fc3:
            date_to = st.date_input(
                "To date",
                value=today,
                key="stats_to",
            )

        if date_from > date_to:
            st.error("'From' date must be before 'To' date.")
            st.stop()

        file_prefix = f"{school_abbr_val}{dept_abbr}{sel_level}"

        if st.button("🔍 Load Statistics", type="primary", key="stats_load"):
            # Clear previous results when filters change
            for k in ["stats_master", "stats_matched_files"]:
                st.session_state.pop(k, None)
            st.session_state["stats_loaded"]   = True
            st.session_state["stats_prefix"]   = file_prefix
            st.session_state["stats_date_from"] = str(date_from)
            st.session_state["stats_date_to"]   = str(date_to)

        if not st.session_state.get("stats_loaded"):
            st.info("Set a level and date range above then click **Load Statistics**.")
            st.stop()

        # Generate all YYYY-MM-DD strings in the range
        def _date_range_strs(d_from, d_to):
            out, cur = [], d_from
            while cur <= d_to:
                out.append(str(cur))
                cur += _td(days=1)
            return out

        # ── Collect matching CSVs ──────────────────────────────────────────────
        if "stats_master" not in st.session_state:
            with st.spinner("Scanning LAVA archives..."):
                all_date_folders = {
                    f["name"] for f in _gh_list_stats("attendances")
                    if f.get("type") == "dir"
                }

            target_dates = [
                d for d in _date_range_strs(date_from, date_to)
                if d in all_date_folders
            ]

            if not target_dates:
                st.warning(f"No attendance folders found between {date_from} and {date_to}.")
                st.stop()

            matched_files = []
            progress = st.progress(0, text="Scanning folders...")
            for i, folder in enumerate(sorted(target_dates)):
                progress.progress((i + 1) / len(target_dates), text=f"Scanning {folder}…")
                for f in _gh_list_stats(f"attendances/{folder}"):
                    name = f.get("name", "")
                    if name.endswith(".csv") and name.startswith(file_prefix + "_"):
                        try:
                            parts       = name.replace(".csv", "").split("_")
                            course_code = parts[1]
                            file_date   = parts[2]
                        except IndexError:
                            course_code = "UNKNOWN"
                            file_date   = folder
                        matched_files.append({
                            "name":         name,
                            "download_url": f["download_url"],
                            "date":         file_date,
                            "course_code":  course_code,
                        })
            progress.empty()

            if not matched_files:
                st.warning(
                    f"No records found for **{file_prefix}** between "
                    f"{date_from} and {date_to}. "
                    f"(Looking for files starting with `{file_prefix}_`)"
                )
                st.stop()

            # Load all CSVs into master DataFrame
            all_rows = []
            prog2 = st.progress(0, text="Loading records...")
            for i, mf in enumerate(matched_files):
                prog2.progress((i + 1) / len(matched_files), text=f"Loading {mf['name']}…")
                try:
                    raw = _fetch_csv_stats(mf["download_url"])
                    df  = _pd.read_csv(_BytesIO(raw))
                    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
                    # Matric number is the only identity field
                    mat_col = next(
                        (c for c in df.columns if "matric" in c),
                        None
                    )
                    if mat_col is None:
                        continue
                    if mat_col != "matric_number":
                        df = df.rename(columns={mat_col: "matric_number"})
                    df["course_code"] = mf["course_code"]
                    df["date"]        = mf["date"]
                    all_rows.append(df)
                except Exception:
                    continue
            prog2.empty()

            if not all_rows:
                st.error("Could not parse any attendance records. Check CSV column format.")
                st.stop()

            master = _pd.concat(all_rows, ignore_index=True)
            master["matric_number"] = master["matric_number"].astype(str).str.strip()

            # Build display name: surname + other_names if available, else matric
            if "surname" in master.columns and "other_names" in master.columns:
                master["full_name"] = (
                    master["surname"].fillna("").str.strip().str.upper()
                    + " "
                    + master["other_names"].fillna("").str.strip().str.title()
                ).str.strip()
            else:
                master["full_name"] = master["matric_number"]

            st.session_state["stats_master"]        = master
            st.session_state["stats_matched_files"] = matched_files

        master        = st.session_state["stats_master"]
        matched_files = st.session_state["stats_matched_files"]
        course_list   = sorted(master["course_code"].unique())

        # ── Info banner ────────────────────────────────────────────────────────
        st.markdown(f"""<div class="info-card">
            <b>Level:</b> {sel_level} &nbsp;|&nbsp;
            <b>Dept:</b> {dept_abbr} &nbsp;|&nbsp;
            <b>Period:</b> {date_from} → {date_to} &nbsp;|&nbsp;
            <b>Records:</b> {len(matched_files)} files &nbsp;|&nbsp;
            <b>Entries:</b> {len(master)}
        </div>""", unsafe_allow_html=True)

        # ── Overview stats ─────────────────────────────────────────────────────
        st.markdown("### Overview")
        ov1, ov2, ov3 = st.columns(3)
        for col, num, lbl in [
            (ov1, master["matric_number"].nunique(), "Unique Students"),
            (ov2, master["course_code"].nunique(),   "Courses"),
            (ov3, len(master),                       "Total Entries"),
        ]:
            col.markdown(
                f'<div class="stat-box"><div class="num">{num}</div>'
                f'<div class="lbl">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Course summary table ───────────────────────────────────────────────
        st.markdown("### Attendance per Course")
        course_summary = (
            master.groupby("course_code")
            .agg(sessions=("date", "nunique"), total_entries=("matric_number", "count"))
            .reset_index()
            .rename(columns={
                "course_code":   "Course Code",
                "sessions":      "Sessions Held",
                "total_entries": "Total Entries",
            })
            .sort_values("Course Code")
        )
        st.dataframe(course_summary, use_container_width=True, hide_index=True)

        st.divider()

        # ── Student drill-down ─────────────────────────────────────────────────
        st.markdown("### 👤 Student Drill-Down")

        name_map = (
            master.dropna(subset=["matric_number"])
            .drop_duplicates(subset=["matric_number"])
            .set_index("matric_number")["full_name"]
            .to_dict()
        )

        student_opts = {
            f"{mat}  —  {name_map.get(mat, '')}": mat
            for mat in sorted(name_map.keys())
        }

        sel_label  = st.selectbox("Select student", list(student_opts.keys()), key="stats_student")
        sel_matric = student_opts[sel_label]
        sel_name   = name_map.get(sel_matric, sel_matric)

        student_rows     = master[master["matric_number"] == sel_matric]
        total_attended   = len(student_rows)
        courses_attended = student_rows["course_code"].nunique()

        st.markdown(f"""<div class="info-card">
            <b>{sel_name}</b> &nbsp;|&nbsp;
            Matric: <b>{sel_matric}</b> &nbsp;|&nbsp;
            Total entries: <b>{total_attended}</b> &nbsp;|&nbsp;
            Courses attended: <b>{courses_attended}</b>
        </div>""", unsafe_allow_html=True)

        # ── Switchable chart ───────────────────────────────────────────────────
        chart_view = st.radio(
            "Chart view",
            ["By Course Code", "By Date"],
            horizontal=True,
            key="stats_chart_view",
        )

        CHART_LAYOUT = dict(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e8e4dc",
            coloraxis_showscale=False,
            yaxis=dict(tickformat="d", gridcolor="rgba(255,255,255,0.07)", dtick=1),
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            title_font_size=14,
            margin=dict(t=50, b=20, l=20, r=20),
        )

        if chart_view == "By Course Code":
            # One bar per course — height = times this student attended that course
            sc = (
                student_rows.groupby("course_code")
                .size()
                .reset_index(name="times_attended")
            )
            all_courses_df = _pd.DataFrame({"course_code": course_list})
            sc = all_courses_df.merge(sc, on="course_code", how="left").fillna(0)
            sc["times_attended"] = sc["times_attended"].astype(int)

            fig = _px.bar(
                sc,
                x="course_code", y="times_attended",
                text="times_attended",
                labels={"course_code": "Course Code", "times_attended": "Times Attended"},
                title=f"{sel_name} ({sel_matric}) — Attendance by Course",
                color="times_attended",
                color_continuous_scale=[[0, "#c0392b22"], [1, "#c0392b"]],
            )
            fig.update_traces(textposition="outside", marker_line_width=0)
            fig.update_layout(**CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        else:  # By Date
            # One bar per date — height = number of classes this student attended on that date
            sd = (
                student_rows.groupby("date")
                .size()
                .reset_index(name="classes_attended")
                .sort_values("date")
            )
            fig = _px.bar(
                sd,
                x="date", y="classes_attended",
                text="classes_attended",
                labels={"date": "Date", "classes_attended": "Classes Attended"},
                title=f"{sel_name} ({sel_matric}) — Attendance by Date",
                color="classes_attended",
                color_continuous_scale=[[0, "#2980b922"], [1, "#2980b9"]],
            )
            fig.update_traces(textposition="outside", marker_line_width=0)
            fig.update_layout(**CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        # Per-student breakdown table
        st.markdown("#### Attendance Log")
        breakdown = (
            student_rows[["course_code", "date"]]
            .sort_values(["date", "course_code"])
            .rename(columns={"course_code": "Course Code", "date": "Date"})
            .reset_index(drop=True)
        )
        breakdown.index += 1
        st.dataframe(breakdown, use_container_width=True)

        # ── Full matrix ────────────────────────────────────────────────────────
        st.divider()
        st.markdown("### 📋 Full Attendance Matrix")
        st.caption(
            "Rows = students · Columns = course codes · "
            "Values = times attended · Sorted by total descending."
        )

        pivot = (
            master.groupby(["matric_number", "course_code"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        pivot.insert(1, "Name", pivot["matric_number"].map(name_map))
        pivot = pivot.rename(columns={"matric_number": "Matric No."})
        course_cols = [c for c in pivot.columns if c not in ("Matric No.", "Name")]
        pivot["Total"] = pivot[course_cols].sum(axis=1)
        pivot = pivot.sort_values("Total", ascending=False).reset_index(drop=True)
        pivot.index += 1

        st.dataframe(pivot, use_container_width=True)

        st.download_button(
            "📥 Download Matrix (CSV)",
            pivot.to_csv(index=False).encode(),
            file_name=f"stats_{dept_abbr}{sel_level}_{date_from}_to_{date_to}.csv",
            mime="text/csv",
        )

    # ── TAB 6 — My Account ────────────────────────────────────────────────────
    with tab6:
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
