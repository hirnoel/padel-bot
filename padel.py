import streamlit as st
import streamlit.components.v1 as components
import requests
from datetime import datetime, timedelta

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="WestPadel Bot")

# --- ⬇️ SECRETS ⬇️ ---

MY_EMAIL = st.secrets["MY_EMAIL"]
MY_PASSWORD = st.secrets["MY_PASSWORD"]
MY_USER_ID = st.secrets["MY_USER_ID"]
MY_NAME = st.secrets["MY_NAME"]
MY_PIN = st.secrets["MY_PIN"]


# --- CONFIG ---
COURT_IDS = [1, 2, 3, 4]
COURT_NAMES = ["Páros 1", "Páros 2", "Páros 3", "Egyéni 4"]
URL_BASE = "https://foglalas.westpadel.hu/Customer"

# --- CSS ---
st.markdown("""
<style>
    /* Fix for the "Cut Off" issue - more space at the top */
    .block-container { 
        padding-top: 4rem !important; 
        padding-bottom: 2rem; 
    }
    
    /* Center the date nicely */
    h3 { margin-top: -10px; }

    /* Calendar Wrapper */
    iframe { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- INIT SESSION ---
if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.headers.update({
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://foglalas.westpadel.hu",
        "Referer": "https://foglalas.westpadel.hu/Customer/Reservation",
    })
    st.session_state.is_logged_in = False

# --- AUTO-LOGIN ---
if not st.session_state.is_logged_in:
    try:
        login_payload = { "ddlLangCode": "HU", "LoginName": MY_EMAIL, "Password": MY_PASSWORD }
        st.session_state.session.post(f"{URL_BASE}/User/ValidateLogin", params={"Length": "4"}, data=login_payload)
        r_check = st.session_state.session.get(f"{URL_BASE}/Reservation")
        if MY_NAME in r_check.text:
            st.session_state.is_logged_in = True
    except: pass

# --- DATE HANDLING ---
if 'current_date' not in st.session_state:
    st.session_state.current_date = datetime.now().date()
if 'sidebar_date' not in st.session_state:
    st.session_state.sidebar_date = st.session_state.current_date

def update_date_from_sidebar():
    st.session_state.current_date = st.session_state.sidebar_date

def adjust_date(days):
    new = st.session_state.current_date + timedelta(days=days)
    st.session_state.current_date = new
    st.session_state.sidebar_date = new

# --- HELPER FUNCTIONS ---
def fetch_data_session(date):
    start_str = date.strftime("%Y-%m-%d")
    end_str = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    payload = { "sportsFieldTypeID": 1, "fromDate": start_str, "toDate": end_str }
    try:
        r = st.session_state.session.post(f"{URL_BASE}/Reservation/GetReservations", json=payload)
        return r.json() if r.status_code == 200 else []
    except: return []

def get_day_schedule(bookings, current_date, court_id):
    booked_times = set()
    for item in bookings:
        if item['SportsField_ID'] != court_id: continue
        start = datetime.strptime(item['StartDate'], '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(item['EndDate'], '%Y-%m-%d %H:%M:%S')
        curr = start
        while curr < end:
            if curr.date() == current_date:
                booked_times.add(curr.strftime("%H:%M"))
            curr += timedelta(minutes=30)
    timeline = []
    OPENING_HOUR, CLOSING_HOUR = 8, 23
    curr_dt = datetime.combine(current_date, datetime.strptime(f"{OPENING_HOUR}:00", "%H:%M").time())
    end_dt = datetime.combine(current_date, datetime.strptime(f"{CLOSING_HOUR}:00", "%H:%M").time())
    
    current_status = 'booked' if curr_dt.strftime("%H:%M") in booked_times else 'free'
    current_block_start = curr_dt
    
    while curr_dt < end_dt:
        time_str = curr_dt.strftime("%H:%M")
        status = 'booked' if time_str in booked_times else 'free'
        if status != current_status:
            timeline.append({'start_dt': current_block_start, 'end_dt': curr_dt, 'status': current_status})
            current_status = status
            current_block_start = curr_dt
        curr_dt += timedelta(minutes=30)
    timeline.append({'start_dt': current_block_start, 'end_dt': end_dt, 'status': current_status})
    return timeline

def render_html_calendar(all_courts_data, court_names):
    OPENING_HOUR, CLOSING_HOUR = 8, 23
    PIXELS_PER_HOUR = 48
    HEADER_HEIGHT = 40 # Increased slightly for mobile tap target
    
    css = """<style>
        .calendar-wrapper { display: flex; flex-direction: row; height: 750px; font-family: 'Segoe UI', sans-serif; background-color: white; border: 1px solid #e0e0e0; overflow: auto; -webkit-overflow-scrolling: touch; }
        .time-col { width: 50px; border-right: 1px solid #eee; background-color: #fafafa; position: sticky; left: 0; z-index: 30; }
        .time-label { position: absolute; width: 100%; text-align: right; padding-right: 6px; font-size: 11px; color: #999; transform: translateY(-50%); }
        .court-col { min-width: 110px; flex: 1; position: relative; border-right: 1px solid #f0f0f0; }
        .grid-line { position: absolute; width: 100%; border-top: 1px solid #f5f5f5; z-index: 0; }
        .grid-line-major { border-color: #eee; }
        .event-card { position: absolute; width: 94%; left: 3%; border-radius: 4px; font-size: 11px; font-weight: 600; display: flex; align-items: center; justify-content: center; box-sizing: border-box; z-index: 10; white-space: nowrap; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,0.05); transition: 0.1s; }
        .event-card:hover { z-index: 20; transform: scale(1.02); }
        .free { background-color: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; cursor: pointer; }
        .header { height: 40px; text-align: center; font-weight: bold; font-size: 13px; background: #2776F5; color: white; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid #ddd; position: sticky; top: 0; z-index: 25; }
        .time-header { height: 40px; background: #fafafa; border-bottom: 1px solid #ddd; position: sticky; top: 0; z-index: 35; }
    </style>"""
    
    html = f'{css}<div class="calendar-wrapper"><div class="time-col"><div class="time-header"></div>'
    
    for h in range(OPENING_HOUR, CLOSING_HOUR + 1):
        top = (h - OPENING_HOUR) * PIXELS_PER_HOUR + HEADER_HEIGHT
        html += f'<div class="time-label" style="top: {top}px;">{h}:00</div>'
    html += '</div>'

    for i, court_data in enumerate(all_courts_data):
        html += '<div class="court-col">'
        # Sticky Header inside column
        html += f'<div class="header">{court_names[i]}</div>'
        
        for h in range(CLOSING_HOUR - OPENING_HOUR + 1):
            top = h * PIXELS_PER_HOUR + HEADER_HEIGHT
            html += f'<div class="grid-line grid-line-major" style="top: {top}px;"></div>'
            
        for slot in court_data:
            if slot['status'] == 'booked': continue
            start_min = (slot['start_dt'].hour - OPENING_HOUR) * 60 + slot['start_dt'].minute
            duration_min = (slot['end_dt'] - slot['start_dt']).total_seconds() / 60
            top_px = (start_min / 60) * PIXELS_PER_HOUR + HEADER_HEIGHT
            height_px = (duration_min / 60) * PIXELS_PER_HOUR
            label = "" if height_px < 22 else f"{slot['start_dt'].strftime('%H:%M')}"
            if height_px > 40: label += f" - {slot['end_dt'].strftime('%H:%M')}"
            html += f"""<div class="event-card {slot['status']}" style="top: {top_px}px; height: {height_px - 1}px;">{label}</div>"""
        html += '</div>'
    html += '</div>'
    return html

# --- SIDEBAR ---
with st.sidebar:
    st.title("🎾 WestPadel Bot")
    
    if st.session_state.is_logged_in:
        st.success(f"👤 {MY_NAME}")
        st.divider()
        b_date = st.date_input("Date", key="sidebar_date", on_change=update_date_from_sidebar)
        b_court = st.selectbox("Select Court", COURT_NAMES)
        b_time = st.time_input("Start Time", value=datetime.strptime("18:00", "%H:%M"))
        b_duration = st.selectbox("Duration", ["30 min", "60 min", "90 min", "120 min", "150 min"])
        
        st.divider()
        user_pin = st.text_input("Enter PIN", type="password", placeholder="****")
        
        if st.button("Confirm Booking"):
            if user_pin != MY_PIN:
                st.error("❌ INCORRECT PIN!")
            else:
                duration_mins = int(b_duration.split()[0])
                start_dt = datetime.combine(b_date, b_time)
                end_dt = start_dt + timedelta(minutes=duration_mins)
                court_id = COURT_IDS[COURT_NAMES.index(b_court)]
                days_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                day_name = days_en[start_dt.weekday()]
                
                try:
                    price_payload = {
                        "BookingType": "1", "SportsFieldID": str(court_id), "Date": start_dt.strftime("%Y-%m-%d"),
                        "FromTime": start_dt.strftime("%H:%M"), "ToTime": end_dt.strftime("%H:%M"),
                        "IsTrainerRequired": "false", "TillDate": "2026-12-31", "DayOfWeek": day_name, 
                        "IsRecurring": "false", "IsBlocking": "false", "ReservationID": "0", "RecurringReservationID": "", 
                        "UserID": MY_USER_ID 
                    }
                    price_r = st.session_state.session.post(f"{URL_BASE}/Reservation/GetReservationPrice", data=price_payload)
                    
                    if price_r.status_code == 200:
                        price_data = price_r.json()
                        if not price_data.get("SingleReservation"):
                            st.error("Could not get price.")
                            st.stop()
                        
                        gross_amount = str(price_data["SingleReservation"]["Price"])
                        price_uuid = price_data["MainUserPriceDetail"]["PriceCalculationIdentifier"]
                        st.write(f"💰 Price: {gross_amount} Ft")

                        proceed_payload = {
                            "reservation[Reservation_ID]": "0", "reservation[IsRecurring]": "false", "reservation[RecurringReservation_ID]": "",
                            "reservation[SportsField_ID]": str(court_id), "reservation[SportsFieldType_ID]": "1", "reservation[ReservationType_ID]": "1",
                            "reservation[Date]": start_dt.strftime("%Y-%m-%d"), "reservation[DayOfWeek]": day_name, "reservation[EndDate]": "2026.12.31",
                            "reservation[BeginningTime]": start_dt.strftime("%H:%M"), "reservation[EndTime]": end_dt.strftime("%H:%M"), "reservation[ServiceType_ID]": "1"
                        }
                        st.session_state.session.post(f"{URL_BASE}/Reservation/GetProceedToPaymentData", data=proceed_payload)
                        
                        booking_payload = {
                            "addReservation[ActualValue]": gross_amount, "addReservation[Reservation_ID]": "0", "addReservation[RecurringReservation_ID]": "",
                            "addReservation[Date]": start_dt.strftime("%Y-%m-%d"), "addReservation[BeginningTime]": start_dt.strftime("%H:%M"),
                            "addReservation[EndTime]": end_dt.strftime("%H:%M"), "addReservation[IsTrainerRequired]": "false", "addReservation[IsRecurring]": "false",
                            "addReservation[ReservationCount]": "1", "addReservation[Dayofweek]": day_name, "addReservation[EndDate]": "2026.12.31", 
                            "addReservation[SportsField_ID]": str(court_id), "addReservation[SpecialRequest]": "", "addReservation[GrossAmount]": gross_amount,
                            "addReservation[UnitAmount]": gross_amount, "addReservation[PaidByCredit]": "0", "addReservation[ReserveAndPayLater]": "true",
                            "addReservation[SportsFieldType]": "1", "addReservation[ExternalReference]": "", "addReservation[BookingType]": "1",
                            "addReservation[SplitPaymentUsers][0][UserId]": MY_USER_ID, "addReservation[SplitPaymentUsers][0][PriceCalculationIdentifier]": price_uuid,
                            "addReservation[SplitPaymentUsers][0][SplitPayable]": gross_amount, "addReservation[PriceCalculationIdentifier]": price_uuid,
                            "progressHubConnectionID": "", 
                        }
                        book_r = st.session_state.session.post(f"{URL_BASE}/Reservation/AddNewReservation", data=booking_payload)
                        if book_r.status_code == 200 and "true" in book_r.text.lower():
                            st.toast("SUCCESS! 🎉", icon="✅")
                            st.balloons()
                            if b_date == st.session_state.current_date: st.rerun()
                        else:
                            st.error("Booking Rejected")
                            st.text(book_r.text)
                    else: st.error(f"Price Check Failed: {price_r.status_code}")
                except Exception as e: st.error(f"Error: {e}")
    else:
        st.error("⚠️ Auto-Login Failed. Check Credentials.")

# --- MAIN AREA ---
col1, col2, col3 = st.columns([1, 6, 1])
if col1.button("⬅️", on_click=adjust_date, args=(-1,)): pass
if col3.button("➡️", on_click=adjust_date, args=(1,)): pass
col2.markdown(f"<h3 style='text-align:center; margin:0;'>{st.session_state.current_date.strftime('%Y. %B %d. (%A)')}</h3>", unsafe_allow_html=True)

# Render
bookings = fetch_data_session(st.session_state.current_date)
all_data = [get_day_schedule(bookings, st.session_state.current_date, cid) for cid in COURT_IDS]
html = render_html_calendar(all_data, COURT_NAMES)
components.html(html, height=780, scrolling=False)