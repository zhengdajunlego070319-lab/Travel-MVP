import base64
import time
from geopy.geocoders import Nominatim
import folium
from PIL import Image
import google.generativeai as genai
import streamlit as st
from streamlit_folium import st_folium

# --- 1. Branding & UI Setup ---
st.set_page_config(page_title="Pinpoint", layout="centered", initial_sidebar_state="collapsed")

# 注入全域自訂 CSS (已清理不需要的假連結樣式)
st.markdown("""
<style>
    .reportview-container {
        background: #f7f9fc;
    }
</style>
""", unsafe_allow_html=True)

st.title("📍 Pinpoint")
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
            OUTPUT STRICTLY IN ENGLISH. 
            
            Visual Formatting Rule: 
            Use ONLY these functional unicode icons for structure: 📍(location), 🕒(time), 🚶‍♂️(walking/transport), 🍽️(dining). 
            ABSOLUTELY NO EXPRESSIVE EMOJIS (no smileys, faces, etc).
            
            Constraints:
            1. Anchor ONLY on locations found in the images.
            2. Apply these parameters: Duration: {duration_option}, Pace: {pace_option}, Window: {start_time} to {end_time}.
            3. Provide a beautifully formatted chronological itinerary divided clearly by days using Markdown headings (###). 
            4. EXTRA RECOMMENDATIONS: After the main itinerary, create a dedicated Markdown table titled "### Extra Recommendations". Columns: | Day | Spot Name | Type (Dining/Hidden Gem) | Reason to Visit |. ONLY include spots with exceptionally high historical recognition. Include a 1-sentence disclaimer below.
            
            CRITICAL: At the absolute end of your response, you MUST add a separator "===MAP_DATA===" on a new line, followed by a single comma-separated list of the key EXACT OFFICIAL LANDMARK NAMES (e.g., Victoria Peak) in chronological order.
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

# --- Render Phase 1 Output & Direct Refinement ---
if st.session_state.phase1_done:
  st.markdown('---')
  st.markdown('### Your Pinpoint Itinerary')
  
  with st.container(border=True):
      st.markdown(st.session_state.itinerary_text)

  st.markdown('### Refine Your Itinerary')
  user_feedback = st.text_area("Need adjustments? Tell us what to change (e.g., 'Make Day 1 more relaxed'):")
  
  if st.button("Update Schedule"):
      with st.spinner("Adjusting your schedule based on your feedback..."):
          refine_prompt = f"""
          You are a professional travel planner. Review the existing itinerary and adjust it based on user feedback.
          OUTPUT STRICTLY IN ENGLISH. Use ONLY functional icons (📍, 🕒, 🚶‍♂️, 🍽️). NO EXPRESSIVE EMOJIS.
          
          Existing Itinerary:
          {st.session_state.itinerary_text}
          
          Feedback:
          {user_feedback}
          
          Constraints: Maintain the exact same formatting structure (Main itinerary + Extra Recommendations table).
          
          CRITICAL: End with "===MAP_DATA===" followed by a comma-separated list of official landmark names.
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
              
              st.session_state.phase2_done = False
              st.rerun()
          except Exception as e:
              st.error(f'Refinement Error: {str(e)}')

  # Render Map ONLY if user opted in
  if enable_map and st.session_state.all_locations:
    st.markdown('### Global Route Overview')
    with st.spinner('Plotting your chronological journey on the map...'):
        geolocator = Nominatim(user_agent='pinpoint_app_v7')
        m = folium.Map(location=[22.3193, 114.1694], zoom_start=11)
        valid_coords = []
        missing_locs = []

        for idx, loc in enumerate(st.session_state.all_locations):
            try:
                location = geolocator.geocode(loc + ', Hong Kong', timeout=10)
                if location:
                    coords = [location.latitude, location.longitude]
                    folium.Marker(
                        coords, popup=loc, tooltip=f"Stop {idx + 1}: {loc}",
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
            folium.PolyLine(valid_coords, color='#ff4b4b', weight=3, opacity=0.8).add_to(m)
            m.fit_bounds(valid_coords)

        st_folium(m, width=700, height=450, key="global_route_map")
        
        if missing_locs:
            st.info(f"Note: Could not precisely map: {', '.join(missing_locs)}")

  # --- PHASE 2: Detailed Transport & Itemized Budget ---
  st.markdown('---')
  if not st.session_state.phase2_done:
    if st.button('Get Transport & Budget Breakdown', type='primary', use_container_width=True):
      with st.spinner('Calculating exact routes and itemized budget...'):
        budget_prompt = f"""
                Based on this itinerary:
                {st.session_state.itinerary_text}

                OUTPUT STRICTLY IN ENGLISH. Use ONLY functional icons (📍, 🕒, 🚶‍♂️, 🍽️). NO EXPRESSIVE EMOJIS.

                Requirements:
                1. **Detailed Transport Guide**: Point-to-point public transit directions.
                2. **Itemized Budget Breakdown**: Highly granular cost breakdown in HKD (Transport, Dining ranges for {pace_option} pace, Attractions).
                3. **Total Calculation**: A clear "Total Estimated Budget Range".
                4. Use clear Markdown headings and bullet points.
                """
        try:
          budget_resp = model.generate_content([budget_prompt])
          st.session_state.transport_budget_text = budget_resp.text
          st.session_state.phase2_done = True
          st.rerun()
        except Exception as e:
          st.error(f'Error: {str(e)}')

# --- Render Phase 2 Details & Premium HTML Export ---
if st.session_state.phase2_done:
  st.markdown('### Logistics & Budget Breakdown')
  
  with st.container(border=True):
      st.markdown(st.session_state.transport_budget_text)

  st.markdown('---')
  st.markdown('### Export & Share (Instagram-Ready)')

  # PREMIUM HTML Export Package with embedded JS Markdown parser
  full_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pinpoint Itinerary</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <!-- 引入 marked.js 即時解析 Markdown -->
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body {{ 
                font-family: 'Inter', sans-serif; 
                background: #f7f9fc; 
                margin: 0; 
                padding: 20px; 
                color: #2d3748;
                display: flex;
                justify-content: center;
            }}
            .story-container {{
                background: white;
                max-width: 420px;
                width: 100%;
                padding: 30px 20px;
                border-radius: 24px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            }}
            .header {{ text-align: center; margin-bottom: 25px; }}
            h1 {{ color: #ff4b4b; margin: 0; font-size: 28px; font-weight: 700; }}
            h3 {{ color: #718096; margin: 5px 0 20px 0; font-size: 14px; font-weight: 400; }}
            .content-card h3 {{ font-size: 18px; color: #1a202c; border-bottom: 2px solid #edf2f7; padding-bottom: 8px; margin-top: 25px; }}
            .content-card ul {{ padding-left: 20px; }}
            .content-card li {{ margin-bottom: 8px; }}
            .content-card {{ 
                background: #fdfdfd; 
                padding: 20px; 
                border-radius: 12px; 
                border: 1px solid #e2e8f0; 
                line-height: 1.6;
                font-size: 14px;
            }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: left; }}
            th {{ background-color: #f7fafc; font-weight: 600; color: #4a5568; }}
        </style>
    </head>
    <body>
        <div class="story-container">
            <div class="header">
                <h1>📍 Pinpoint</h1>
                <h3>Grab your Itinerary on Fingertips!</h3>
            </div>
            
            <!-- 隱藏的原始 Markdown 數據 -->
            <div id="raw-itinerary" style="display:none;">{st.session_state.itinerary_text}</div>
            <div id="raw-budget" style="display:none;">{st.session_state.transport_budget_text}</div>
            
            <!-- 渲染後的 HTML 容器 -->
            <div class="content-card" id="rendered-itinerary"></div>
            <br>
            <div class="content-card" id="rendered-budget"></div>
        </div>

        <script>
            // 讀取並解析 Markdown
            document.getElementById('rendered-itinerary').innerHTML = marked.parse(document.getElementById('raw-itinerary').textContent);
            document.getElementById('rendered-budget').innerHTML = marked.parse(document.getElementById('raw-budget').textContent);
        </script>
    </body>
    </html>
    """
  b64_html = base64.b64encode(full_html.encode()).decode()

  href_html = f'<a href="data:text/html;base64,{b64_html}" download="Pinpoint_Story_Format.html" style="text-decoration: none; padding: 16px 20px; background-color: #111; color: white; font-weight: bold; border-radius: 12px; display: block; text-align: center; font-size: 16px; transition: 0.3s; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">Download Instagram-Ready Image Format (HTML)</a>'

  st.markdown(href_html, unsafe_allow_html=True)
  st.caption("*(Open the downloaded file on your phone or browser, and it will be perfectly proportioned for an Instagram Story screenshot!)*")
