import streamlit as st
import pandas as pd
import requests
import base64
import bcrypt
import io
from datetime import datetime
import hashlib

# ---------------- CONFIG ----------------
st.set_page_config(page_title="ULAS - FUTO", layout="centered")

DATA_OWNER = "successcugo"
DATA_REPO = "ULASDATA"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]

# ---------------- GITHUB FUNCTIONS ----------------
def gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

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
    if r.status_code != 200:
        st.error("Could not fetch file SHA from GitHub.")
        st.stop()
    sha = r.json()["sha"]
    encoded = base64.b64encode(content.encode()).decode()
    data = {"message": message, "content": encoded, "sha": sha}
    requests.put(url, headers=gh_headers(), json=data)

# ---------------- SECURITY FUNCTIONS ----------------
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(input_pw, stored_hash):
    return bcrypt.checkpw(input_pw.encode(), stored_hash.encode())

# ---------------- LOAD DATA ----------------
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

# ---------------- SIDEBAR MENU ----------------
menu = st.sidebar.selectbox("Portal", ["Student Attendance", "Advisor Login", "Course Rep Login"])

# ---------------- STUDENT ATTENDANCE ----------------
if menu == "Student Attendance":
    st.subheader("Student Attendance Portal")

    # Load schools & departments dynamically from advisors.csv
    advisors = load_advisors()
    if advisors.empty:
        st.error("No data found for schools/departments.")
        st.stop()

    schools = sorted(advisors["school"].unique())
    school = st.selectbox("Select School", schools)

    departments = sorted(advisors[advisors["school"] == school]["department"].unique())
    department = st.selectbox("Select Department", departments)

    level = st.selectbox("Select Level", [100,200,300,400,500,600])

    code = st.text_input("Enter 4-digit Attendance Code")

    surname = st.text_input("Surname")
    other_names = st.text_input("Other Names")
    matric_number = st.text_input("Matric Number (11 digits)")

    # Generate a device id cookie
    device_id = hashlib.sha256(st.session_state.get('session_id', str(datetime.now()).encode()).encode() if 'session_id' not in st.session_state else st.session_state['session_id'].encode()).hexdigest()

    if st.button("Submit Attendance"):

        # ---------------- VALIDATION ----------------
        if not surname or not other_names or not matric_number or not code:
            st.error("All fields are required.")
            st.stop()
        if len(matric_number) != 11 or not matric_number.isdigit():
            st.error("Matric number must be exactly 11 digits.")
            st.stop()

        # Prepare attendance file path
        today = datetime.now().strftime("%Y-%m-%d")
        path = f"attendances/{school}/{department}/{level}_{today}.csv"

        existing_data = gh_get_file(path)
        if existing_data:
            df = pd.read_csv(io.StringIO(existing_data))
            # Check duplicates: matric and surname
            if df['matric_number'].astype(str).str.strip().str.lower().isin([matric_number.lower()]).any():
                st.error("Matric number already recorded.")
                st.stop()
            if df['surname'].astype(str).str.strip().str.lower().isin([surname.lower()]).any():
                st.error("Surname already recorded.")
                st.stop()
            # Anti-cheat: check device_id column
            if 'device_id' in df.columns and df['device_id'].astype(str).str.contains(device_id).any():
                st.error("This device has already submitted attendance.")
                st.stop()
        else:
            df = pd.DataFrame(columns=["S/N","surname","other_names","matric_number","time","device_id"])

        # Add new record
        sn = len(df)+1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df.loc[len(df)] = [sn, surname.title(), other_names.title(), matric_number, timestamp, device_id]

        updated_csv = df.to_csv(index=False)
        gh_update_file(path, updated_csv, f"Student attendance: {surname} {other_names}")

        st.success(f"Attendance recorded for {surname.title()} {other_names}.")

# ---------------- ADVISOR LOGIN ----------------
elif menu == "Advisor Login":
    st.subheader("Advisor Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        advisors = load_advisors()
        if "username" not in advisors.columns or "password" not in advisors.columns:
            st.error("advisors.csv is incorrectly structured.")
            st.stop()

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
elif menu == "Course Rep Login":
    st.subheader("Course Rep Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        reps = load_reps()
        if "username" not in reps.columns or "password" not in reps.columns:
            st.error("course_reps.csv is incorrectly structured.")
            st.stop()

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

            if not course or not topic:
                st.error("All fields required.")
                st.stop()

            today = datetime.now().strftime("%Y-%m-%d")
            attendance_line = f"{today},{course},{topic},{st.session_state['user']['department']}\n"

            existing = gh_get_file("attendance.csv")
            if existing:
                updated = existing + attendance_line
            else:
                updated = "date,course,topic,department\n" + attendance_line

            gh_update_file("attendance.csv", updated, "Updated attendance record")
            st.success("Attendance recorded successfully.")

    # ---------------- ADVISOR DASHBOARD ----------------
    if st.session_state["role"] == "advisor":
        advisor_dept = st.session_state["user"]["department"]
        st.subheader("Manage Course Reps")

        reps = load_reps()
        if reps.empty:
            st.info("No reps found.")
        else:
            dept_reps = reps[reps["department"] == advisor_dept]
            if dept_reps.empty:
                st.info("No course reps in your department.")
            else:
                for index, row in dept_reps.iterrows():
                    st.markdown(f"### {row['username']}")

                    new_username = st.text_input("Edit Username",
                        value=row["username"], key=f"user_{index}")
                    new_password = st.text_input("Reset Password (leave blank to keep same)",
                        type="password", key=f"pass_{index}")

                    if st.button("Update", key=f"btn_{index}"):
                        if new_username != row["username"]:
                            if new_username in reps["username"].values:
                                st.error("Username already exists globally.")
                                st.stop()
                        reps.loc[index, "username"] = new_username
                        if new_password:
                            reps.loc[index, "password"] = hash_password(new_password)
                        updated_csv = reps.to_csv(index=False)
                        gh_update_file("course_reps.csv", updated_csv, "Advisor updated rep credentials")
                        st.success("Updated successfully.")
                        st.rerun()

        st.divider()
        st.subheader("View Department Attendance")

        data = gh_get_file("attendance.csv")
        if data:
            df = pd.read_csv(io.StringIO(data))
            df = df[df["department"] == advisor_dept]
            st.dataframe(df)
        else:
            st.info("No attendance records yet.")
