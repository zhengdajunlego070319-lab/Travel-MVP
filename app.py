import streamlit as st
import google.generativeai as genai
from PIL import Image
import urllib.parse

st.set_page_config(page_title="AI Visual Itinerary Planner", page_icon="✈️", layout="centered")

st.title("✈️ AI Visual Itinerary Planner")
st.caption("Upload photos of places you saw on social media, and AI will plan your trip directly.")

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

    # 優化按鈕：文字簡短、顏色醒目、全寬顯示
    if st.button("✨ Generate Itinerary", type="primary", use_container_width=True):
        with st.spinner("Analyzing..."):
            
            # 優化 Prompt：強制極簡輸出
            prompt = f"""
            Analyze the uploaded photos and extra details: {extra_details}.
            Output strictly in ENGLISH. 
            CRITICAL INSTRUCTION: Be extremely concise. NO introductory or concluding sentences. DO NOT say "Here is your itinerary". Jump directly into the plan.
            
            1. If distance is extreme and user did NOT check force schedule ({force_schedule}), output ONLY a short warning.
            2. Otherwise, provide a direct, highly structured itinerary using a Markdown table or compact bullet points. Include ONLY: Day/Time, Location, and suggested transport.
            """
            
            try:
                response = model.generate_content([prompt, *images])
                st.markdown("---")
                st.markdown(response.text)
                
                search_query = urllib.parse.quote(" ".join([extra_details if extra_details else "Attractions"]))
                maps_url = f"https://www.google.com/maps/search/?api=1&query={search_query}"
                st.markdown(f"🗺️ 👉 [Open in Google Maps]({maps_url})")

            except Exception as e:
                st.error(f"Error: {str(e)}")
