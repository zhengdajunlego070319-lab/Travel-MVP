import streamlit as st
import google.generativeai as genai
from PIL import Image

st.set_page_config(page_title="AI Visual Itinerary Planner", page_icon="✈️", layout="centered")

st.title("✈️ AI Visual Itinerary Planner")
st.caption("Upload your social media inspiration photos, select your travel preferences, and get a precise, customized itinerary instantly.")

# 從 Streamlit Secrets 安全讀取金鑰
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("System configuration error: API Key missing.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-flash-lite')

uploaded_files = st.file_uploader("Upload attraction photos (Multiple allowed):", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    cols = st.columns(min(len(uploaded_files), 4))
    images = []
    for idx, uploaded_file in enumerate(uploaded_files):
        img = Image.open(uploaded_file)
        images.append(img)
        with cols[idx % 4]:
            st.image(img, use_container_width=True)

    # 參數設定欄位（減少 AI 猜測，降低算力消耗）
    st.markdown("---")
    st.subheader("⚙️ Travel Preferences")
    
    col1, col2 = st.columns(2)
    with col1:
        duration_option = st.selectbox(
            "Desired Trip Duration:",
            ["Half Day", "1 Day", "2 Days", "3 Days", "1 Week"]
        )
    with col2:
        pace_option = st.selectbox(
            "Pace:",
            ["Relaxed", "Balanced", "Packed / Fast-paced"]
        )

    col3, col4 = st.columns(2)
    with col3:
        start_time = st.text_input("Earliest Start Time:", value="09:00")
    with col4:
        end_time = st.text_input("Latest End Time:", value="21:00")

    extra_details = st.text_input("💡 Hints (Optional): Add text hints for blurry photos.")
    force_schedule = st.checkbox("⚠️ Plan itinerary even if locations are extremely far apart.")

    # 醒目大按鈕
    if st.button("✨ Generate Custom Itinerary", type="primary", use_container_width=True):
        with st.spinner("Analyzing your photos and building your optimized schedule..."):
            
            # 優化 Prompt：限定嚴格基於所提供圖片地點，並帶入用戶自定義參數
            prompt = f"""
            You are a professional travel planner. Analyze the uploaded photos and extra details: {extra_details}.
            Output strictly in ENGLISH.
            
            CRITICAL CONSTRAINTS:
            1. **Strictly Relevance**: Focus ONLY on the specific locations identified from the uploaded photos. Do NOT arbitrarily add random irrelevant external attractions that the user did not provide, unless necessary for transit logic.
            2. **User Parameters**: 
               - Desired Duration: {duration_option}
               - Pace: {pace_option}
               - Daily Time Window: {start_time} to {end_time}
            3. **Detailed Breakdown**: For each spot, clearly specify:
               - Specific time slots (e.g., activity time, how long to play/explore)
               - Meal/dining time allocation
               - Commute/transit time between locations
               - Whether it fits into a Half Day, X Days, etc., and how many spots to visit in one go.
            
            Keep the output clean, highly structured, and focused purely on scheduling logistics without unnecessary fluff or map links.
            """
            
            try:
                response = model.generate_content([prompt, *images])
                st.markdown("---")
                st.markdown(response.text)

            except Exception as e:
                st.error(f"Error: {str(e)}")
