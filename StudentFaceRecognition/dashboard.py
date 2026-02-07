import streamlit as st
import pandas as pd
import os
import glob
from PIL import Image
from datetime import datetime

# --- Page Configuration ---
# This sets up the title, icon, and layout of your web app.
st.set_page_config(
    page_title="Attendance System Dashboard",
    page_icon="👤",
    layout="wide"
)

# --- File Paths ---
LOG_DIR = "."  # This tells the script to look for CSV files in the current folder.
CAPTURED_FACES_DIR = "captured_faces"

# --- Helper Functions (The "Workers" behind the scenes) ---

@st.cache_data
def load_all_logs():
    """
    This function finds all 'face_log_*.csv' files, combines them into one
    big dataset, and prepares them for analysis. Caching makes it faster.
    """
    csv_files = glob.glob(os.path.join(LOG_DIR, "face_log_*.csv"))
    if not csv_files:
        return pd.DataFrame()
    
    df_list = []
    for file in csv_files:
        try:
            df_list.append(pd.read_csv(file))
        except pd.errors.EmptyDataError:
            # This safely skips any empty log files.
            continue

    if not df_list:
        return pd.DataFrame()
        
    full_df = pd.concat(df_list, ignore_index=True)
    # Convert 'Date' and 'Time' columns into a single 'Timestamp' for easy sorting
    full_df['Timestamp'] = pd.to_datetime(full_df['Date'] + ' ' + full_df['Time'])
    return full_df

def get_latest_photo(student_name, df):
    """This function finds the most recent verification photo for a student."""
    student_logs = df[(df['Name'] == student_name) & (df['Status'] == 'Login')]
    if not student_logs.empty:
        latest_log = student_logs.sort_values(by='Timestamp', ascending=False).iloc[0]
        date_folder = latest_log['Date']
        time_for_filename = latest_log['Time'].replace(':', '')
        image_filename = f"{student_name}_Login_{time_for_filename}.jpg"
        image_path = os.path.join(CAPTURED_FACES_DIR, date_folder, image_filename)
        return image_path
    return None

# --- Load Data at the start ---
full_log_df = load_all_logs()

# --- Sidebar Navigation ---
# This creates the main navigation menu on the left side of the page.
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Daily Attendance Dashboard", "Student Profile Deep Dive"])
st.sidebar.markdown("---")
st.sidebar.info("This dashboard provides insights from the Face Recognition Attendance System.")


# =================================================================================
# PAGE 1: Daily Attendance Dashboard
# This is the main screen showing today's or a selected day's summary.
# =================================================================================

if page == "Daily Attendance Dashboard":
    st.title("📅 Daily Attendance Dashboard")
    
    if full_log_df.empty:
        st.warning("No attendance data found. Please run the face recognition script to generate data.")
    else:
        # --- Date Selector ---
        unique_dates = sorted(full_log_df['Date'].unique(), reverse=True)
        selected_date = st.selectbox("Select a Date to Analyze", unique_dates)
        st.markdown("---")

        # Filter the data to show only the selected day's records
        daily_df = full_log_df[full_log_df['Date'] == selected_date]

        # --- Key Metrics (The main numbers at the top) ---
        st.header(f"Insights for {selected_date}")
        unique_students = daily_df['Name'].nunique()
        
        # Calculate how long each student was present
        durations = []
        for name in daily_df['Name'].unique():
            student_logs = daily_df[daily_df['Name'] == name].sort_values(by='Timestamp')
            login_time = student_logs[student_logs['Status'] == 'Login']['Timestamp'].min()
            logout_time = student_logs[student_logs['Status'] == 'Logout']['Timestamp'].max()
            if pd.notna(login_time) and pd.notna(logout_time):
                duration = logout_time - login_time
                durations.append(duration.total_seconds() / 3600) # Duration in hours
        
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Display the metrics in three columns
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Students Present", f"{unique_students} 👤")
        col2.metric("Total Login/Logout Events", f"{len(daily_df)} 🔄")
        col3.metric("Avg. Time Spent (Hours)", f"{avg_duration:.2f} 🕒")

        st.markdown("---")

        # --- Visualizations (Charts and Graphs) ---
        st.header("Attendance Timeline (Logins per Hour)")
        
        if not daily_df.empty and 'Login' in daily_df['Status'].values:
            logins_df = daily_df[daily_df['Status'] == 'Login'].copy()
            logins_df['Hour'] = logins_df['Timestamp'].dt.hour
            logins_per_hour = logins_df.groupby('Hour').size().reindex(range(24), fill_value=0)
            st.bar_chart(logins_per_hour)
        else:
            st.write("No login data to display for this day.")

        # --- Raw Data Table ---
        st.header("Detailed Log for the Day")
        st.dataframe(daily_df[['Name', 'Time', 'Status']].sort_values(by='Time'))


# =================================================================================
# PAGE 2: Student Profile Deep Dive
# This page shows the complete history for a single, selected student.
# =================================================================================

elif page == "Student Profile Deep Dive":
    st.title("🧑‍🎓 Student Profile Deep Dive")

    if full_log_df.empty:
        st.warning("No attendance data found.")
    else:
        student_names = sorted(full_log_df['Name'].unique())
        selected_student = st.selectbox("Select a Student", student_names)
        st.markdown("---")

        if selected_student:
            student_df = full_log_df[full_log_df['Name'] == selected_student].sort_values(by='Timestamp', ascending=False)
            
            # --- Student Metrics and Photo ---
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.header(selected_student)
                latest_photo_path = get_latest_photo(selected_student, full_log_df)
                if latest_photo_path and os.path.exists(latest_photo_path):
                    image = Image.open(latest_photo_path)
                    st.image(image, caption="Most Recent Login Photo", use_column_width=True)
                else:
                    st.write("No photo available.")

            with col2:
                total_days_present = student_df['Date'].nunique()
                st.metric("Total Days Present", f"{total_days_present} days")
                
                # Calculate the student's average arrival time
                login_times = student_df[student_df['Status'] == 'Login']['Timestamp'].dt.time
                if not login_times.empty:
                    avg_arrival_seconds = sum(t.hour * 3600 + t.minute * 60 + t.second for t in login_times) / len(login_times)
                    avg_arrival_time = f"{int(avg_arrival_seconds // 3600):02d}:{int((avg_arrival_seconds % 3600) // 60):02d}"
                    st.metric("Average Arrival Time", avg_arrival_time)
                else:
                    st.metric("Average Arrival Time", "N/A")
            
            st.markdown("---")
            
            # --- Full History Table ---
            st.header("Complete Attendance History")
            st.dataframe(student_df[['Date', 'Time', 'Status']])
            