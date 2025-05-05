import streamlit as st
import pandas as pd
import datetime
import requests
import pytz
import numpy as np
import altair as alt  # Required for ordered weekly chart

# CONFIG
st.set_page_config(page_title="Smart Pillbox", page_icon="💊", layout="centered")

# --- LOGIN CONFIG ---
USERNAME = "user"
PASSWORD = "1234"

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

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    login()
    st.stop()

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
alarm_field = "field8"

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
    if st.button("🔓 Logout"):
        st.session_state.logged_in = False
        st.rerun()

    if st.button("🔄 Refresh Now"):
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
      values = [int(feed.get(f"field{field_num}") or 0) for feed in feeds]:
        df = pd.DataFrame({"Time": times, "Pill Taken": values})
        df["Status"] = df["Pill Taken"].apply(lambda x: "Yes" if x > 0 else "No")
        return df
    return pd.DataFrame()

def get_y_axis_ticks(max_value):
    if max_value <= 10:
        return 1
    elif max_value <= 100:
        return 5
    elif max_value <= 500:
        return 10
    elif max_value <= 1000:
        return 25
    else:
        return 50

# --- MAIN DASHBOARD ---
st.title("💊 Smart Pillbox Monitoring Dashboard")

today = datetime.datetime.now(IST).strftime("%A")
date_picker = st.date_input("📅 Select Date", datetime.datetime.now(IST))
selected_day = date_picker.strftime("%A")
field_num = get_field_number(selected_day)

if date_picker == datetime.datetime.now(IST).date():
    graph_title = f"📈 Pill Intake Today ({today})"
else:
    graph_title = f"📈 Pill Intake on {selected_day}, {date_picker.strftime('%Y-%m-%d')}"

df = fetch_data_for_day(field_num)

if not df.empty:
    now = datetime.datetime.now(IST)
    last_seven_days = now - datetime.timedelta(days=7)
    df = df[df["Time"] >= last_seven_days]

    st.subheader(graph_title)

    df["Pill Taken"] = df["Pill Taken"].astype(int)
    max_value = df["Pill Taken"].max()
    step_size = get_y_axis_ticks(max_value)

    st.bar_chart(df.set_index("Time")["Pill Taken"])

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

now = datetime.datetime.now(IST)
start_date = now - datetime.timedelta(days=6)
end_date = now
start_date_str = start_date.strftime("%d %b %Y")
end_date_str = end_date.strftime("%d %b %Y")

st.markdown(f"**Showing data from {start_date_str} to {end_date_str}**")

ordered_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekly_data = {}

for day in ordered_days:
    field = field_map[day]
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
    "Day": ordered_days,
    "Pills Taken": [weekly_data[day] for day in ordered_days]
})

bar_chart = alt.Chart(weekly_df).mark_bar().encode(
    x=alt.X("Day", sort=ordered_days, title="Day of Week"),
    y=alt.Y("Pills Taken", title="Total Pills Taken"),
    color=alt.value("#4CAF50")
).properties(
    width=600,
    height=400,
    title="Weekly Pill Intake"
)

st.altair_chart(bar_chart, use_container_width=True)
