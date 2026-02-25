import streamlit as st
import pandas as pd
import requests
import base64
import bcrypt
import io
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="ULAS - FUTO", layout="centered")

DATA_OWNER = "successcugo"
DATA_REPO = "ULASDATA"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]

# ---------------- GITHUB FUNCTIONS ----------------

def gh_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def gh_get_file(path):
    url = f"https://api.github.com/repos/{DATA_OWNER}/{DATA_REPO}/contents/{path}"
    r = requests.get(url, headers=gh_headers())
    if r.status_code == 200:
        content = r.json()["content"]
        decoded = base64.b64decode(content).decode("utf-8")
        return decoded
    return None

def gh_update_file(path, content, message):
    url = f"https://api.github.com/repos/{DATA_OWNER}/{DATA_REPO}/contents/{path}"
    r = requests.get(url, headers=gh_headers())
    sha = r.json()["sha"]

    encoded = base64.b64encode(content.encode()).decode()

    data = {
        "message": message,
        "content": encoded,
        "sha": sha
    }

    requests.put(url, headers=gh_headers(), json=data)

# ---------------- LOAD USERS ----------------

def load_advisors():
    data = gh_get_file("advisors.csv")
    if data:
        return pd.read_csv(io.StringIO(data))
    return pd.DataFrame()

def load_reps():
    data = gh_get_file("course_reps.csv")
    if data:
        return pd.read_csv(io.StringIO(data))
    return pd.DataFrame()

# ---------------- AUTH ----------------

def verify_password(input_pw, stored_hash):
    return bcrypt.checkpw(input_pw.encode(), stored_hash.encode())

# ---------------- UI ----------------

st.title("🌿 ULAS - Universal Lecture Attendance System (FUTO)")

menu = st.sidebar.selectbox("Portal", ["Advisor Login", "Course Rep Login"])

# ---------------- ADVISOR LOGIN ----------------

if menu == "Advisor Login":

    st.subheader("Advisor Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        advisors = load_advisors()

        if username in advisors["username"].values:

            row = advisors[advisors["username"] == username].iloc[0]

            if verify_password(password, row["password"]):
                st.session_state["role"] = "advisor"
                st.session_state["user"] = row
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Incorrect password")

        else:
            st.error("User not found")

# ---------------- COURSE REP LOGIN ----------------

if menu == "Course Rep Login":

    st.subheader("Course Rep Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        reps = load_reps()

        if username in reps["username"].values:

            row = reps[reps["username"] == username].iloc[0]

            if verify_password(password, row["password"]):
                st.session_state["role"] = "rep"
                st.session_state["user"] = row
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Incorrect password")

        else:
            st.error("User not found")

# ---------------- DASHBOARD ----------------

if "role" in st.session_state:

    st.sidebar.success(f"Logged in as {st.session_state['role']}")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    st.header("Dashboard")

    # ---------------- COURSE REP DASHBOARD ----------------

    if st.session_state["role"] == "rep":

        st.subheader("Mark Attendance")

        course = st.text_input("Course Code")
        topic = st.text_input("Lecture Topic")

        if st.button("Submit Attendance"):

            today = datetime.now().strftime("%Y-%m-%d")

            attendance_data = f"{today},{course},{topic},{st.session_state['user']['department']}\n"

            existing = gh_get_file("attendance.csv")

            if existing:
                updated = existing + attendance_data
            else:
                updated = "date,course,topic,department\n" + attendance_data

            gh_update_file("attendance.csv", updated, "Updated attendance")

            st.success("Attendance recorded successfully")

    # ---------------- ADVISOR DASHBOARD ----------------

    if st.session_state["role"] == "advisor":

        st.subheader("View Attendance")

        data = gh_get_file("attendance.csv")

        if data:
            df = pd.read_csv(io.StringIO(data))
            st.dataframe(df)
        else:
            st.info("No attendance records yet.")
