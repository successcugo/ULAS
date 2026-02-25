import streamlit as st
import pandas as pd
import hashlib
import uuid
import datetime
import os

st.set_page_config(page_title="ULAS - FUTO", layout="wide")

# ===============================
# CONFIG
# ===============================

DATA_FILE = "attendance.csv"
ADVISOR_FILE = "advisors.csv"
REP_FILE = "reps.csv"

# ===============================
# UTILITIES
# ===============================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def generate_device_id():
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())
    return st.session_state.device_id

def load_csv(file, columns):
    if not os.path.exists(file):
        pd.DataFrame(columns=columns).to_csv(file, index=False)
    return pd.read_csv(file)

def save_csv(df, file):
    df.to_csv(file, index=False)

# ===============================
# LOAD DATA
# ===============================

advisors = load_csv(ADVISOR_FILE, ["username","password","department"])
reps = load_csv(REP_FILE, ["username","password","department"])
attendance = load_csv(DATA_FILE, ["matric","department","timestamp","device_id"])

# ===============================
# LOGIN SYSTEM
# ===============================

def login_user(user_type):
    st.subheader(f"{user_type} Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        df = advisors if user_type == "Advisor" else reps

        user = df[df["username"] == username]

        if not user.empty:
            row = user.iloc[0]
            if verify_password(password, row["password"]):
                st.session_state.logged_in = True
                st.session_state.user_type = user_type
                st.session_state.username = username
                st.session_state.department = row["department"]
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Incorrect password")
        else:
            st.error("User not found")

# ===============================
# STUDENT ATTENDANCE
# ===============================

def student_attendance():

    st.header("Student Attendance")

    matric = st.text_input("Matric Number")

    if st.button("Mark Attendance"):

        if matric.strip() == "":
            st.error("Enter matric number")
            return

        device_id = generate_device_id()
        timestamp = datetime.datetime.now().isoformat()

        # ANTI CHEAT 1: Duplicate matric same day
        today = datetime.date.today().isoformat()
        existing_today = attendance[
            (attendance["matric"] == matric) &
            (attendance["timestamp"].str.startswith(today))
        ]

        if not existing_today.empty:
            st.error("Attendance already marked today")
            return

        # ANTI CHEAT 2: Multiple entries same device in short time
        last_5_min = datetime.datetime.now() - datetime.timedelta(minutes=5)
        suspicious = attendance[
            (attendance["device_id"] == device_id) &
            (pd.to_datetime(attendance["timestamp"]) > last_5_min)
        ]

        if len(suspicious) >= 3:
            st.error("Too many submissions from this device. Suspicious activity.")
            return

        new_row = pd.DataFrame([{
            "matric": matric,
            "department": st.session_state.department,
            "timestamp": timestamp,
            "device_id": device_id
        }])

        updated = pd.concat([attendance, new_row], ignore_index=True)
        save_csv(updated, DATA_FILE)

        st.success("Attendance marked successfully")

# ===============================
# ADVISOR PANEL
# ===============================

def advisor_panel():

    st.header("Advisor Panel")

    global advisors, reps

    st.subheader("Manage Course Reps")

    dept_reps = reps[reps["department"] == st.session_state.department]

    st.dataframe(dept_reps)

    st.subheader("Edit Rep Login")

    selected = st.selectbox("Select Rep", dept_reps["username"] if not dept_reps.empty else [])

    if selected:

        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")

        if st.button("Update Rep"):

            # Ensure global uniqueness
            if new_username in advisors["username"].values or new_username in reps["username"].values:
                st.error("Username already exists globally")
                return

            reps.loc[reps["username"] == selected, "username"] = new_username
            reps.loc[reps["username"] == new_username, "password"] = hash_password(new_password)

            save_csv(reps, REP_FILE)
            st.success("Rep updated")
            st.rerun()

    st.subheader("Download Attendance")

    dept_attendance = attendance[attendance["department"] == st.session_state.department]
    st.download_button(
        "Download CSV",
        dept_attendance.to_csv(index=False),
        "attendance.csv",
        "text/csv"
    )

# ===============================
# REP PANEL
# ===============================

def rep_panel():
    st.header("Course Rep Panel")
    student_attendance()

# ===============================
# MAIN
# ===============================

def main():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    st.title("🌿 ULAS - Universal Lecture Attendance System")

    if not st.session_state.logged_in:

        role = st.radio("Select Role", ["Advisor", "Course Rep"])

        login_user(role)

    else:

        st.sidebar.write(f"Logged in as: {st.session_state.username}")
        st.sidebar.write(f"Department: {st.session_state.department}")

        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

        if st.session_state.user_type == "Advisor":
            advisor_panel()
        else:
            rep_panel()

if __name__ == "__main__":
    main()
