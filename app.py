import streamlit as st
import google.generativeai as genai
from PIL import Image
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from fpdf import FPDF
import base64

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
# 記憶使用者的操作階段，避免重整時資料消失
if "phase1_done" not in st.session_state:
    st.session_state.phase1_done = False
if "itinerary_text" not in st.session_state:
    st.session_state.itinerary_text = ""
if "locations_list" not in st.session_state:
    st.session_state.locations_list = []
if "phase2_done" not in st.session_state:
    st.session_state.phase2_done = False
if "transport_budget_text" not in st.session_state:
    st.session_state.transport_budget_text = ""

# --- 4. User Input Panel ---
uploaded_files = st.file_uploader("Upload visual inspirations (Images):", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    cols = st.columns(min(len(uploaded_files), 4))
    images = []
    for idx, uploaded_file in enumerate(uploaded_files):
        img = Image.open(uploaded_file)
        images.append(img)
        with cols[idx % 4]:
            st.image(img, use_container_width=True)

    st.markdown("### Parameters")
    col1, col2 = st.columns(2)
    with col1:
        duration_option = st.selectbox("Duration:", ["Half Day", "1 Day", "2 Days", "3 Days"])
        start_time = st.text_input("Start Time:", value="09:00")
    with col2:
        pace_option = st.selectbox("Pace:", ["Relaxed", "Balanced", "Packed"])
        end_time = st.text_input("End Time:", value="21:00")

    extra_details = st.text_input("Additional Hints (Optional):")

    # --- PHASE 1: Generate Itinerary ---
    if st.button("Generate Custom Itinerary", type="primary", use_container_width=True):
        with st.spinner("Analyzing and building your schedule..."):
            
            prompt = f"""
            You are a professional travel planner. Analyze the images and details: {extra_details}.
            OUTPUT STRICTLY IN ENGLISH. DO NOT USE ANY EMOJIS.
            
            Constraints:
            1. Anchor ONLY on locations found in the images. Do not hallucinate external spots.
            2. Apply these parameters: Duration: {duration_option}, Pace: {pace_option}, Window: {start_time} to {end_time}.
            3. Provide a chronological itinerary. 
            4. RECOMMENDATIONS: Suggest nearby restaurants or hidden gems ONLY IF they have exceptionally high historical recognition. If uncertain, leave blank. Include a 1-sentence reason and a disclaimer to check operating hours.
            
            At the very end of your response, provide a comma-separated list of the main location names (Max 5) for mapping purposes, formatted exactly like this:
            LOCATIONS: Location 1, Location 2, Location 3
            """
            
            try:
                response = model.generate_content([prompt, *images])
                response_text = response.text
                
                # Extract locations for the map
                loc_list = []
                if "LOCATIONS:" in response_text:
                    parts = response_text.split("LOCATIONS:")
                    st.session_state.itinerary_text = parts[0].strip()
                    loc_string = parts[1].strip()
                    loc_list = [l.strip() for l in loc_string.split(",") if l.strip()]
                else:
                    st.session_state.itinerary_text = response_text
                
                st.session_state.locations_list = loc_list
                st.session_state.phase1_done = True
                st.session_state.phase2_done = False # Reset phase 2
                
            except Exception as e:
                st.error(f"Generation Error: {str(e)}")

# --- Render Phase 1 Output & Folium Map ---
if st.session_state.phase1_done:
    st.markdown("---")
    st.markdown("### Your Pinpoint Itinerary")
    st.markdown(st.session_state.itinerary_text)
    
    # Generate Map
    if st.session_state.locations_list:
        st.markdown("### Route Overview")
        with st.spinner("Plotting map..."):
            geolocator = Nominatim(user_agent="pinpoint_app")
            m = folium.Map(location=[22.3193, 114.1694], zoom_start=11) # Default HK
            
            valid_coords = []
            for loc in st.session_state.locations_list:
                try:
                    location = geolocator.geocode(loc + ", Hong Kong", timeout=5)
                    if location:
                        folium.Marker([location.latitude, location.longitude], popup=loc).add_to(m)
                        valid_coords.append([location.latitude, location.longitude])
                except:
                    pass
            
            if len(valid_coords) > 1:
                folium.PolyLine(valid_coords, color="blue", weight=2.5, opacity=0.8).add_to(m)
                m.fit_bounds(valid_coords)
            
            st_folium(m, width=700, height=400)

    # --- PHASE 2: Transport & Budget ---
    st.markdown("---")
    if not st.session_state.phase2_done:
        if st.button("Get Transport & Budget Options", use_container_width=True):
            with st.spinner("Calculating logistics and budget estimates..."):
                budget_prompt = f"""
                Based on this itinerary: {st.session_state.itinerary_text}
                OUTPUT STRICTLY IN ENGLISH. NO EMOJIS.
                
                Provide:
                1. Transport Guide: Specific point-to-point public transit routes and estimated times.
                2. Baseline Budget (Estimated Range in HKD): Break down into Transport, Dining (based on {pace_option} pace), and Attraction fees.
                Note: Remind the user that these are historical estimates and actual prices may vary.
                """
                try:
                    budget_resp = model.generate_content([budget_prompt])
                    st.session_state.transport_budget_text = budget_resp.text
                    st.session_state.phase2_done = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# --- Render Phase 2 & Phase 3 (Export) ---
if st.session_state.phase2_done:
    st.markdown("### Logistics & Budget")
    st.markdown(st.session_state.transport_budget_text)
    
    st.markdown("---")
    st.markdown("### Export & Share")
    
    col_exp1, col_exp2 = st.columns(2)
    
    # Export HTML
    full_html = f"""
    <html>
    <head><title>Pinpoint Itinerary</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px;">
        <h1>Pinpoint</h1>
        <h3>Grab your Itinerary on Fingertips!</h3>
        <hr>
        <h2>Your Itinerary</h2>
        <pre style="white-space: pre-wrap; font-family: inherit;">{st.session_state.itinerary_text}</pre>
        <hr>
        <h2>Logistics & Budget</h2>
        <pre style="white-space: pre-wrap; font-family: inherit;">{st.session_state.transport_budget_text}</pre>
    </body>
    </html>
    """
    b64_html = base64.b64encode(full_html.encode()).decode()
    href_html = f'<a href="data:text/html;base64,{b64_html}" download="Pinpoint_Itinerary.html" style="text-decoration: none; padding: 10px 20px; background-color: #f0f2f6; color: black; border-radius: 5px; border: 1px solid #ccc; display: block; text-align: center;">Download Interactive HTML</a>'
    
    with col_exp1:
        st.markdown(href_html, unsafe_allow_html=True)
    
    # Export PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Pinpoint - Grab your Itinerary on Fingertips!", ln=1, align="C")
    pdf.line(10, 20, 200, 20)
    pdf.ln(10)
    pdf.multi_cell(0, 7, txt="ITINERARY:\n" + st.session_state.itinerary_text.encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)
    pdf.multi_cell(0, 7, txt="LOGISTICS & BUDGET:\n" + st.session_state.transport_budget_text.encode('latin-1', 'replace').decode('latin-1'))
    
    pdf_out = pdf.output(dest="S").encode("latin-1")
    
    with col_exp2:
        st.download_button(label="Download PDF Report", data=pdf_out, file_name="Pinpoint_Itinerary.pdf", mime="application/pdf", use_container_width=True)
