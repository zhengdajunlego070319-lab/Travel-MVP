import streamlit as st
import google.generativeai as genai
from PIL import Image

st.set_page_config(page_title="AI Visual Itinerary Planner", page_icon="✈️", layout="centered")

st.title("✈️ AI Visual Itinerary Planner")
st.caption("Upload photos of places you saw on social media, and AI will plan your trip with precise time schedules and direct map links.")

# 從 Streamlit Secrets 安全讀取金鑰
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("System configuration error: API Key missing.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-flash-lite')

uploaded_files = st.file_uploader("Upload photos (Multiple allowed):", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    cols = st.columns(min(len(uploaded_files), 4))
    images = []
    for idx, uploaded_file in enumerate(uploaded_files):
        img = Image.open(uploaded_file)
        images.append(img)
        with cols[idx % 4]:
            st.image(img, use_container_width=True)

    extra_details = st.text_input("💡 Hints (Optional): Add text hints for blurry photos.")
    force_schedule = st.checkbox("⚠️ Plan itinerary even if locations are extremely far apart.")

    # 醒目大按鈕
    if st.button("✨ Generate Detailed Itinerary", type="primary", use_container_width=True):
        with st.spinner("Analyzing photos and building your schedule..."):
            
            # 優化 Prompt：要求具體時間段與點對點 Google Maps 連結
            prompt = f"""
            Analyze the uploaded photos and extra details: {extra_details}.
            Output strictly in ENGLISH. 
            
            Requirements:
            1. Provide a practical, structured itinerary divided by days. 
            2. Include specific time slots (e.g., 09:00 - 11:00) for each activity, along with suggested transport methods and estimated travel times.
            3. **MAP INTEGRATION**: For EVERY location or attraction mentioned in the itinerary, you MUST format it as a clickable Markdown link pointing directly to its Google Maps search page, using this exact format: `[Location Name](https://www.google.com/maps/search/?api=1&query=Location+Name)` (replace spaces with plus signs or standard URL encoding).
            """
            
            try:
                response = model.generate_content([prompt, *images])
                st.markdown("---")
                st.markdown(response.text)

            except Exception as e:
                st.error(f"Error: {str(e)}")
