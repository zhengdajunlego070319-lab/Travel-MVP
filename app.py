import base64
import time
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
  st.error("System Error: API Key missing. Please configure Streamlit Secrets.")
  st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-flash-lite')

# --- 3. Session State Management ---
if 'phase1_done' not in st.session_state:
  st.session_state.phase1_done = False
if 'itinerary_text' not in st.session_state:
  st.session_state.itinerary_text = ''
if 'all_locations' not in st.session_state:
  st.session_state.all_locations = []
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
  
  enable_map = st.checkbox('Generate Interactive Route Map (Note: May take a few minutes to load)', value=False)

  # --- PHASE 1: Generate Itinerary ---
  if st.button('Generate Custom Itinerary', type='primary', use_container_width=True):
    with st.spinner('Analyzing and building your schedule...'):

      prompt = f"""
            You are a professional travel planner. Analyze the images and details: {extra_details}.
            OUTPUT STRICTLY IN ENGLISH. DO NOT USE ANY EMOJIS OR EMOTICONS.
            
            Constraints:
            1. Anchor ONLY on locations found in the images. Do not hallucinate external spots.
            2. Apply these parameters: Duration: {duration_option}, Pace: {pace_option}, Window: {start_time} to {end_time}.
            3. Provide a beautifully formatted chronological itinerary divided clearly by days using Markdown headings and bullet points.
            4. EXTRA RECOMMENDATIONS: After the main itinerary, create a dedicated Markdown table titled "### Extra Recommendations". The table MUST have these columns: | Day | Spot Name | Type (Dining/Hidden Gem) | Reason to Visit |. ONLY include spots with exceptionally high historical recognition. Include a 1-sentence disclaimer below the table to check operating hours.
            
            CRITICAL: At the absolute end of your response, you MUST add a separator "===MAP_DATA===" on a new line, followed by a single comma-separated list of the key EXACT OFFICIAL LANDMARK NAMES (e.g., Victoria Peak, Hong Kong Disneyland) in chronological order.
            Example:
            ===MAP_DATA===
            Location A, Location B, Location C
            """

      try:
        response = model.generate_content([prompt, *images])
        raw_text = response.text

        if "===MAP_DATA===" in raw_text:
            parts = raw_text.split("===MAP_DATA===")
            st.session_state.itinerary_text = parts[0].strip()
            loc_string = parts[1].strip()
            st.session_state.all_locations = [loc.replace('\n', '').strip() for loc in loc_string.split(',') if loc.replace('\n', '').strip()]
        else:
            st.session_state.itinerary_text = raw_text.strip()
            st.session_state.all_locations = []

        st.session_state.phase1_done = True
        st.session_state.phase2_done = False  
        st.rerun()

      except Exception as e:
        st.error(f'Generation Error: {str(e)}')

# --- Render Phase 1 Output & Refinement & Optional Map ---
if st.session_state.phase1_done:
  st.markdown('---')
  st.markdown('### Your Pinpoint Itinerary')
  st.markdown(st.session_state.itinerary_text)

  # Iterative Feedback Mechanism
  with st.expander("Tweak this itinerary"):
      user_feedback = st.text_area("What would you like to change? (e.g., 'Make Day 1 more relaxed', 'Swap the museum for a park')")
      if st.button("Update Schedule"):
          with st.spinner("Adjusting your schedule based on your feedback..."):
              refine_prompt = f"""
              You are a professional travel planner. Review the following existing itinerary and adjust it based on the user's specific feedback.
              OUTPUT STRICTLY IN ENGLISH. DO NOT USE ANY EMOJIS OR EMOTICONS.
              
              Existing Itinerary:
              {st.session_state.itinerary_text}
              
              User Feedback for Adjustments:
              {user_feedback}
              
              Constraints:
              1. Modify the itinerary to reflect the user's feedback precisely.
              2. Maintain the exact same formatting structure: Main chronological itinerary first, followed by the "### Extra Recommendations" table.
              
              CRITICAL: At the absolute end of your response, you MUST add a separator "===MAP_DATA===" on a new line, followed by a single comma-separated list of the updated key EXACT OFFICIAL LANDMARK NAMES in chronological order.
              """
              try:
                  refine_resp = model.generate_content([refine_prompt])
                  raw_refine_text = refine_resp.text
                  
                  if "===MAP_DATA===" in raw_refine_text:
                      parts = raw_refine_text.split("===MAP_DATA===")
                      st.session_state.itinerary_text = parts[0].strip()
                      loc_string = parts[1].strip()
                      st.session_state.all_locations = [loc.replace('\n', '').strip() for loc in loc_string.split(',') if loc.replace('\n', '').strip()]
                  else:
                      st.session_state.itinerary_text = raw_refine_text.strip()
                  
                  # Reset Phase 2 because the itinerary changed
                  st.session_state.phase2_done = False
                  st.rerun()
              except Exception as e:
                  st.error(f'Refinement Error: {str(e)}')

  # Render Map ONLY if user opted in
  if enable_map and st.session_state.all_locations:
    st.markdown('### Global Route Overview')
    with st.spinner('Plotting your chronological journey on the map...'):
        geolocator = Nominatim(user_agent='pinpoint_app_v4')
        m = folium.Map(location=[22.3193, 114.1694], zoom_start=11)
        valid_coords = []
        missing_locs = []

        for idx, loc in enumerate(st.session_state.all_locations):
            try:
                location = geolocator.geocode(loc + ', Hong Kong', timeout=10)
                if location:
                    coords = [location.latitude, location.longitude]
                    
                    folium.Marker(
                        coords,
                        popup=loc,
                        tooltip=f"Stop {idx + 1}: {loc}",
                        icon=folium.Icon(color='red', icon='info-sign')
                    ).add_to(m)
                    
                    valid_coords.append(coords)
                else:
                    missing_locs.append(loc)
                
                time.sleep(1)
                
            except Exception as e:
                missing_locs.append(loc)
                time.sleep(1)

        if len(valid_coords) > 1:
            folium.PolyLine(
                valid_coords, color='#ff4b4b', weight=3, opacity=0.8
            ).add_to(m)
            m.fit_bounds(valid_coords)

        st_folium(m, width=700, height=450, key="global_route_map")
        
        if missing_locs:
            st.info(f"Note: Could not precisely map the following locations: {', '.join(missing_locs)}")

  # --- PHASE 2: Detailed Transport & Itemized Budget ---
  st.markdown('---')
  if not st.session_state.phase2_done:
    if st.button('Get Transport & Budget Breakdown', type='primary', use_container_width=True):
      with st.spinner('Calculating exact routes and itemized budget...'):
        budget_prompt = f"""
                Based on this itinerary:
                {st.session_state.itinerary_text}

                OUTPUT STRICTLY IN ENGLISH. DO NOT USE ANY EMOJIS.

                Requirements:
                1. **Detailed Transport Guide**: First, provide specific, realistic point-to-point public transit directions between each location. Mimic real-world map logic (e.g., "Take MTR Tsuen Wan Line from X to Y, then take Bus 973"). Include estimated travel times.
                2. **Itemized Budget Breakdown**: Under a new heading, provide a highly granular cost breakdown in HKD.
                   - Transport: List the estimated cost for EACH specific ride.
                   - Dining: Estimate the cost for EACH specific meal using a reasonable range (e.g., $80 - $150), adjusting for a {pace_option} travel pace.
                   - Attractions: List specific admission fees if applicable.
                3. **Total Calculation**: Conclude with a clear "Total Estimated Budget Range" that sums up all the itemized costs.
                4. Use clear Markdown headings (`### Transport Guide` and `### Itemized Budget`) and bullet points for readability. Do not use a single compressed table.
                """
        try:
          budget_resp = model.generate_content([budget_prompt])
          st.session_state.transport_budget_text = budget_resp.text
          st.session_state.phase2_done = True
          st.rerun()
        except Exception as e:
          st.error(f'Error: {str(e)}')

# --- Render Phase 2 Details & HTML Export ---
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
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; line-height: 1.6; color: #333; }}
            h1, h2, h3 {{ color: #111; }}
            hr {{ border: 0; height: 1px; background: #ccc; margin: 20px 0; }}
            .content-box {{ background: #f9f9f9; padding: 20px; border-radius: 8px; border: 1px solid #eee; white-space: pre-wrap; font-family: inherit; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Pinpoint</h1>
        <h3>Grab your Itinerary on Fingertips!</h3>
        <hr>
        <h2>Your Itinerary</h2>
        <div class="content-box">{st.session_state.itinerary_text}</div>
        <hr>
        <h2>Logistics & Budget</h2>
        <div class="content-box">{st.session_state.transport_budget_text}</div>
    </body>
    </html>
    """
  b64_html = base64.b64encode(full_html.encode()).decode()

  href_html = f'<a href="data:text/html;base64,{b64_html}" download="Pinpoint_Itinerary.html" style="text-decoration: none; padding: 14px 28px; background-color: #ff4b4b; color: white; font-weight: bold; border-radius: 6px; display: block; text-align: center; font-size: 16px;">Download Interactive HTML Itinerary</a>'

  st.markdown(href_html, unsafe_allow_html=True)
