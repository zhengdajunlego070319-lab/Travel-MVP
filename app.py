import streamlit as st
import google.generativeai as genai
from PIL import Image
import urllib.parse

# Page Configuration
st.set_page_config(page_title="AI Visual Itinerary Planner", page_icon="✈️", layout="centered")

st.title("✈️ AI Visual Itinerary Planner (MVP)")
st.caption("Upload photos of places you saw on social media, and AI will automatically identify the locations and plan your itinerary!")

# 1. API Key Input
api_key = st.sidebar.text_input("Enter Gemini API Key:", type="password")

if not api_key:
    st.info("👈 Please enter your Gemini API Key in the left sidebar to get started.")
    st.stop()

# Configure Gemini API
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-pro')

# 2. Multi-image uploader
uploaded_files = st.file_uploader("Upload attraction photos (Multiple selection allowed):", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"Uploaded {len(uploaded_files)} photo(s):")
    
    # Display thumbnails
    cols = st.columns(min(len(uploaded_files), 4))
    images = []
    for idx, uploaded_file in enumerate(uploaded_files):
        img = Image.open(uploaded_file)
        images.append(img)
        with cols[idx % 4]:
            st.image(img, use_container_width=True)

    # Extra details input
    extra_details = st.text_input("💡 Hints/Additional Details (Optional): If any photos are hard to recognize, add text hints here (e.g., Admiralty, Repulse Bay)")

    # Checkbox for extreme distance
    force_schedule = st.checkbox("⚠️ If the locations are extremely far apart (e.g., cross-country/continent), still proceed to group and plan the itinerary.")

    if st.button("🚀 Identify Locations & Plan Itinerary", type="primary"):
        with st.spinner("AI is analyzing photos and geographical locations..."):
            
            # Prompt construction (Instructed to reply strictly in English)
            prompt = f"""
            You are a professional AI travel itinerary planner. Please analyze the user's uploaded photos and additional details.
            Additional Details: {extra_details}
            
            Please execute the following steps and output your ENTIRE response strictly in ENGLISH:
            
            1. **Location Identification**: Identify the specific attractions/locations in the photos. If a photo is too blurry or unidentifiable, explicitly point out which photo it is and prompt the user to provide more details.
            2. **Feasibility Check**: Check if the geographical distance between the identified locations is too large (e.g., one in Asia, one in Europe).
               - If the distance is extreme and the user has NOT checked the force scheduling option, return a warning explaining that the itinerary is unreasonable, and ask if they are sure they want to plan an extreme long-distance trip.
               - If the distance is extreme but the user HAS checked the force scheduling option, group the locations by large regions and plan separate itineraries within those regions.
            3. **Itinerary Planning**: Based on the number of locations, reasonably arrange the number of days (e.g., 1-day tour, multi-day tour). Provide a specific daily schedule, suggested transportation methods between locations, and estimated travel time.
            
            Please format your output clearly using Markdown.
            """
            
            try:
                # Call Gemini Vision API
                response = model.generate_content([prompt, *images])
                
                st.markdown("---")
                st.subheader("📋 Your AI-Generated Itinerary")
                st.markdown(response.text)
                
                # Generate Google Maps link
                st.markdown("---")
                st.subheader("🗺️ Quick Navigation & Maps Links")
                st.write("Click the link below to view the search results directly on Google Maps:")
                
                search_query = urllib.parse.quote(" ".join([extra_details if extra_details else "Popular attractions"]))
                maps_url = f"https://www.google.com/maps/search/?api=1&query={search_query}"
                st.markdown(f"👉 [Open Navigation Preview on Google Maps]({maps_url})")

            except Exception as e:
                st.error(f"An error occurred during analysis: {str(e)}")
