import streamlit as st
import pandas as pd
import datetime
import requests
import pytz
import numpy as np

# Dummy credentials
USERNAME = "admin"
PASSWORD = "1234"

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.title("🔐 Login to Smart Pillbox Dashboard")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state.logged_in = True
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

if not st.session_state.logged_in:
    login()
    st.stop()  # Prevent the rest of the app from rendering

# CONFIG
st.set_page_config(page_title="Smart Pillbox", page_icon="💊", layout="centered")

# --- THINKSPEAK CONFIG ---
CHANNEL_ID = "2912929"
READ_API_KEY = "1NNFKY2F2EUYM6VR"
field_map = {
    "Monday": "field1",
    "Tuesday": "field2",
    "Wednesday": "field3",
    "Thursday": "field4",
    "Friday": "field5",
    "Saturday": "field6",
    "Sunday": "field7",
}
alarm_field = "field8"  # Repurposed as alarm status (1 = ON, 0 = OFF)

# --- TIMEZONE CONFIG ---
IST = pytz.timezone("Asia/Kolkata")

# --- SIDEBAR INFO ---
with st.sidebar:
    st.title("💡 About Project")
    st.markdown("""
    **Smart Pillbox Monitoring System**  
    Built with **ESP8266, HC-SR04, RTC, OLED**, and **ThingSpeak**, this project:

    - Alerts users with a buzzer at medicine times
    - Logs when a pill is taken using ultrasonic detection
    - Displays real-time & historical pill logs
    - Shows alarm status & pill delay

    **Built by:** Shaurya, Pranalee, Preet, Muskan, Kanishka, Shubham  
    💊 Stay Healthy. Stay On Track.
    """)

    st.markdown("---")
    st.markdown("🔄 Click to manually refresh:")
    if st.button("Refresh Now"):
        st.rerun()

# --- HELPER FUNCTIONS ---
def get_field_number(day_name):
    return int(field_map[day_name][-1])

def convert_to_ist(utc_string):
    dt_utc = datetime.datetime.strptime(utc_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return dt_utc.astimezone(IST)

def fetch_data_for_day(field_num):
    url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/fields/{field_num}.json?api_key={READ_API_KEY}&results=100"
    response = requests.get(url)
    if response.status_code == 200:
        feeds = response.json().get("feeds", [])
        times = [convert_to_ist(feed["created_at"]) for feed in feeds]
        values = [int(feed.get(f"field{field_num}") or 0) for feed in feeds]

        df = pd.DataFrame({"Time": times, "Pill Taken": values})
        df["Status"] = df["Pill Taken"].apply(lambda x: "Yes" if x > 0 else "No")
        return df
    else:
        return pd.DataFrame()  # Return empty DataFrame if fetch fails

def get_y_axis_ticks(max_value):
    """Returns an appropriate Y-axis step size based on max value."""
    if max_value <= 10:
        return 1  # Small increments for small values
    elif max_value <= 100:
        return 5  # Increments of 5 for values <= 100
    elif max_value <= 500:
        return 10  # Increments of 10 for values <= 500
    elif max_value <= 1000:
        return 25  # Increments of 25 for values <= 1000
    else:
        return 50  # Increments of 50 for larger values

# --- MAIN DASHBOARD ---
st.title("💊 Smart Pillbox Monitoring Dashboard")

# Default: today's date
today = datetime.datetime.now(IST).strftime("%A")

# Date picker for selecting specific day
date_picker = st.date_input("📅 Select Date", datetime.datetime.now(IST))

# Determine the day of the week for the selected date
selected_day = date_picker.strftime("%A")
field_num = get_field_number(selected_day)

# Set the graph title dynamically based on the selected date
if date_picker == datetime.datetime.now(IST).date():
    graph_title = f"📈 Pill Intake Today ({today})"
else:
    graph_title = f"📈 Pill Intake on {selected_day}, {date_picker.strftime('%Y-%m-%d')}"

# --- FETCH DATA FOR SELECTED DAY ---
df = fetch_data_for_day(field_num)

# Limit the graph to the past 7 days
if not df.empty:
    # Filter the data for the past 7 days
    now = datetime.datetime.now(IST)
    last_seven_days = now - datetime.timedelta(days=7)
    df = df[df["Time"] >= last_seven_days]

    # Display the bar chart for the selected day (number of pills taken each day)
    st.subheader(graph_title)

    # Ensure integer values on Y-Axis and avoid decimals
    df["Pill Taken"] = df["Pill Taken"].astype(int)

    # Determine the maximum value in the 'Pill Taken' column for scaling Y-axis
    max_value = df["Pill Taken"].max()

    # Get an appropriate step size for the Y-axis ticks
    step_size = get_y_axis_ticks(max_value)

    # --- BAR CHART: Number of Pills Taken Each Day ---
    st.bar_chart(df.set_index("Time")["Pill Taken"])

    # --- DAILY SUMMARY ---
    total = df["Pill Taken"].sum()
    last_taken = df[df["Pill Taken"] == 1]
    last_time = last_taken["Time"].max() if not last_taken.empty else None

    if last_time:
        delta = now - last_time
        hours_ago = round(delta.total_seconds() / 3600, 2)
    else:
        hours_ago = "Not Taken Today"

    st.markdown("### 📊 Daily Summary")
    st.write(f"🟢 Total pills taken: **{total}**")
    st.write(f"⏱️ Last pill taken: **{last_time.strftime('%I:%M %p')}**" if last_time else "❌ No pill taken")
    st.write(f"⏳ Time since last pill: **{hours_ago} hours**" if isinstance(hours_ago, float) else f"❌ {hours_ago}")

    # --- CSV EXPORT ---
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Export Data to CSV", csv, file_name=f"{selected_day}_pill_log.csv", mime="text/csv")
else:
    st.warning("⚠️ No data available for the selected date.")

# --- ALARM STATUS ---
alarm_url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/fields/8.json?api_key={READ_API_KEY}&results=1"
alarm_res = requests.get(alarm_url)
if alarm_res.status_code == 200:
    latest_alarm = alarm_res.json().get("feeds", [{}])[0].get("field8")
    alarm_status = "🟢 ON" if latest_alarm == "1" else "🔴 OFF"
    st.markdown(f"### 🔔 Alarm Status: {alarm_status}")
else:
    st.warning("⚠️ Could not fetch alarm status.")

# --- WEEKLY PILL INTAKE SUMMARY ---
st.subheader("📊 Weekly Pill Intake Summary")

# Get the date range for the last 7 days
now = datetime.datetime.now(IST)
start_date = now - datetime.timedelta(days=6)
end_date = now
start_date_str = start_date.strftime("%d %b %Y")
end_date_str = end_date.strftime("%d %b %Y")

# Display the date range below the title
st.markdown(f"**Showing data from {start_date_str} to {end_date_str}**")

weekly_data = {}

for day, field in field_map.items():
    url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/fields/{field[-1]}.json?api_key={READ_API_KEY}&results=100"
    res = requests.get(url)

    values = []
    if res.status_code == 200:
        for feed in res.json().get("feeds", []):
            val = feed.get(field)
            if val is not None and val.isdigit():
                values.append(int(val))
        weekly_data[day] = sum(values)
    else:
        weekly_data[day] = 0

weekly_df = pd.DataFrame({
    "Day": list(weekly_data.keys()),
    "Pills Taken": list(weekly_data.values())
})

# Display weekly bar chart with the Y-axis starting from 0 and ensuring integer values on Y-Axis
st.bar_chart(weekly_df.set_index("Day"), use_container_width=True)
