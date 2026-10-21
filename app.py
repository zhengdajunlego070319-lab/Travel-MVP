import base64
import re
from geopy.geocoders import Nominatim
import folium
from PIL import Image
import google.generativeai as genai
import streamlit as st
from streamlit_folium import st_folium

# --- 1. Branding & UI Setup ---
st.set_page_config(page_title="Pinpoint", layout="centered")

st.title("Pinpoint")
st.subheader("Grab your Itinerary on Fingertips!")
st.markdown("---")

# --- 2. API Configuration ---
try:
  api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
  st.error(
      "System Error: API Key missing. Please configure Streamlit Secrets."
  )
  st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-flash-lite')

# --- 3. Session State Management ---
if 'phase1_done' not in st.session_state:
  st.session_state.phase1_done = False
if 'itinerary_text' not in st.session_state:
  st.session_state.itinerary_text = ''
if 'daily_locations' not in st.session_state:
  st.session_state.daily_locations = {}
if 'phase2_done' not in st.session_state:
  st.session_state.phase2_done = False
if 'transport_budget_text' not in st.session_state:
  st.session_state.transport_budget_text = ''

# --- 4. User Input Panel ---
uploaded_files = st.file_uploader(
    'Upload visual inspirations (Images):',
    type=['jpg', 'jpeg', 'png'],
    accept_multiple_files=True,
)

if uploaded_files:
  cols = st.columns(min(len(uploaded_files), 4))
  images = []
  for idx, uploaded_file in enumerate(uploaded_files):
    img = Image.open(uploaded_file)
    images.append(img)
    with cols[idx % 4]:
      st.image(img, use_container_width=True)

  # User-friendly section header without emojis
  st.markdown('### Trip Preferences')
  col1, col2 = st.columns(2)
  with col1:
    duration_option = st.selectbox(
        'Duration:', ['Half Day', '1 Day', '2 Days', '3 Days', '1 Week']
    )
    start_time = st.text_input('Start Time:', value='09:00')
  with col2:
    pace_option = st.selectbox('Pace:', ['Relaxed', 'Balanced', 'Packed'])
    end_time = st.text_input('End Time:', value='21:00')

  extra_details = st.text_input('Additional Hints (Optional):')

  # --- PHASE 1: Generate Itinerary ---
  # Prominent primary action button
  if st.button(
      'Generate Custom Itinerary', type='primary', use_container_width=True
  ):
    with st.spinner('Analyzing and building your schedule...'):

      prompt = f"""
            You are a professional travel planner. Analyze the images and details: {extra_details}.
            OUTPUT STRICTLY IN ENGLISH. DO NOT USE ANY EMOJIS OR EMOTICONS.
            
            Constraints:
            1. Anchor ONLY on locations found in the images. Do not hallucinate external spots.
            2. Apply these parameters: Duration: {duration_option}, Pace: {pace_option}, Window: {start_time} to {end_time}.
            3. Provide a chronological itinerary divided clearly by days (e.g. Day 1, Day 2).
            4. RECOMMENDATIONS: Suggest nearby restaurants or hidden gems ONLY IF they have exceptionally high historical recognition. If uncertain, leave blank. Include a 1-sentence reason and a disclaimer to check operating hours.
            
            At the very end of your response, parse the key spots for EACH day separately for mapping, formatted EXACTLY like this (one line per day):
            DAY 1 LOCATIONS: Location A, Location B
            DAY 2 LOCATIONS: Location C, Location D
            """

      try:
        response = model.generate_content([prompt, *images])
        raw_text = response.text

        # Parse Daily Locations for Folium Maps
        daily_locs = {}
        lines = raw_text.split('\n')
        clean_lines = []

        for line in lines:
          if re.match(r'^DAY \d+ LOCATIONS:', line, re.IGNORECASE):
            parts = line.split(':', 1)
            day_title = parts[0].strip()
            locs = [loc.strip() for loc in parts[1].split(',') if loc.strip()]
            daily_locs[day_title] = locs
          else:
            clean_lines.append(line)

        st.session_state.itinerary_text = '\n'.join(clean_lines).strip()
        st.session_state.daily_locations = daily_locs
        st.session_state.phase1_done = True
        st.session_state.phase2_done = False  # Reset phase 2
        st.rerun()

      except Exception as e:
        st.error(f'Generation Error: {str(e)}')

# --- Render Phase 1 Output & Daily Folium Maps ---
if st.session_state.phase1_done:
  st.markdown('---')
  st.markdown('### Your Pinpoint Itinerary')
  st.markdown(st.session_state.itinerary_text)

  # Render Daily Route Maps
  if st.session_state.daily_locations:
    st.markdown('### Daily Route Overview')
    geolocator = Nominatim(user_agent='pinpoint_app')

    for day_title, locs in st.session_state.daily_locations.items():
      st.markdown(f'#### {day_title} Route Map')
      with st.spinner(f'Plotting map for {day_title}...'):
        m = folium.Map(location=[22.3193, 114.1694], zoom_start=11)
        valid_coords = []

        for loc in locs:
          try:
            location = geolocator.geocode(loc + ', Hong Kong', timeout=5)
            if location:
              folium.Marker(
                  [location.latitude, location.longitude], popup=loc
              ).add_to(m)
              valid_coords.append([location.latitude, location.longitude])
          except:
            pass

        if len(valid_coords) > 1:
          folium.PolyLine(
              valid_coords, color='blue', weight=2.5, opacity=0.8
          ).add_to(m)
          m.fit_bounds(valid_coords)

        st_folium(
            m, width=700, height=350, key=f"map_{day_title.replace(' ', '_')}"
        )

  # --- PHASE 2: Transport & Budget Table ---
  st.markdown('---')
  if not st.session_state.phase2_done:
    # Prominent primary action button
    if st.button(
        'Get Transport & Budget Breakdown',
        type='primary',
        use_container_width=True,
    ):
      with st.spinner('Calculating logistics and table estimates...'):
        budget_prompt = f"""
                Based on this itinerary:
                {st.session_state.itinerary_text}

                OUTPUT STRICTLY IN ENGLISH. DO NOT USE ANY EMOJIS.

                Requirements:
                1. Output a SINGLE structured Markdown table summarizing logistics and budget breakdown.
                2. Table columns MUST be exactly:
                   | Day / Segment | Transit Route & Duration | Estimated Transit Cost | Estimated Dining Cost | Estimated Admission / Other | Total Segment Cost |
                3. Below the table, include a 1-sentence disclaimer stating that costs are baseline historical estimates and actual prices may vary.
                """
        try:
          budget_resp = model.generate_content([budget_prompt])
          st.session_state.transport_budget_text = budget_resp.text
          st.session_state.phase2_done = True
          st.rerun()
        except Exception as e:
          st.error(f'Error: {str(e)}')

# --- Render Phase 2 Table & HTML Export ---
if st.session_state.phase2_done:
  st.markdown('### Logistics & Budget Breakdown')
  st.markdown(st.session_state.transport_budget_text)

  st.markdown('---')
  st.markdown('### Export & Share')

  # HTML Export Package
  full_html = f"""
    <html>
    <head>
        <title>Pinpoint Itinerary</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; line-height: 1.6; }}
            h1, h2, h3 {{ color: #111; }}
            hr {{ border: 0; height: 1px; background: #ccc; margin: 20px 0; }}
            pre {{ white-space: pre-wrap; font-family: inherit; background: #f9f9f9; padding: 15px; border-radius: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Pinpoint</h1>
        <h3>Grab your Itinerary on Fingertips!</h3>
        <hr>
        <h2>Itinerary</h2>
        <div>{st.session_state.itinerary_text.replace('\n', '<br>')}</div>
        <hr>
        <h2>Logistics & Budget</h2>
        <div>{st.session_state.transport_budget_text.replace('\n', '<br>')}</div>
    </body>
    </html>
    """
  b64_html = base64.b64encode(full_html.encode()).decode()

  # Prominent styled HTML download button
  href_html = f'<a href="data:text/html;base64,{b64_html}" download="Pinpoint_Itinerary.html" style="text-decoration: none; padding: 14px 28px; background-color: #ff4b4b; color: white; font-weight: bold; border-radius: 6px; display: block; text-align: center; font-size: 16px;">Download Interactive HTML Itinerary</a>'

  st.markdown(href_html, unsafe_allow_html=True)
