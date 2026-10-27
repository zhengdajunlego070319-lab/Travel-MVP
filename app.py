import base64
import time
import uuid
import pandas as pd
from geopy.geocoders import Nominatim
import folium
from PIL import Image
import google.generativeai as genai
import streamlit as st
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection

# --- 1. Branding & UI Setup ---
st.set_page_config(page_title="Pinpoint", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .reportview-container { background: #f7f9fc; }
    .top-rated-badge { background: #ff4b4b; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-bottom: 10px; display: inline-block;}
    .welcome-card { background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-top: 6px solid #ff4b4b; }
    .comment-box { background: #f9f9f9; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 3px solid #ccc;}
</style>
""", unsafe_allow_html=True)

# --- 2. Session State Initialization (Identity & Routing) ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

if 'current_view' not in st.session_state:
    st.session_state.current_view = 'home'

if 'detail_itinerary_id' not in st.session_state:
    st.session_state.detail_itinerary_id = None

if 'welcome_shown' not in st.session_state:
    st.session_state.welcome_shown = False

if 'publish_success_msg' not in st.session_state:
    st.session_state.publish_success_msg = False

# --- Welcome Splash Screen (Updated Clean Guidelines) ---
if not st.session_state.welcome_shown:
    st.title("📍 Pinpoint")
    st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
    st.markdown("## Welcome to Pinpoint 📍")
    st.markdown("*Grab your itinerary on fingertips!* Whether you are looking for instant inspiration or crafting the perfect trip, here is your quick guide to mastering the platform.")
    st.markdown("""
    ### 🌍 Explore the Community
    *   **Discover & Filter:** Browse itineraries and sort trips by travel pace (Relaxed, Balanced, or Packed).
    *   **Interactive Engagement:** View detailed routes, read comments, and toggle **❤️ Likes** to support your favorite trips.

    ### ✨ Create Your Masterpiece
    *   **Visual AI Generation:** Upload photos to anchor your custom itinerary.
    *   **Smart Refinement:** Easily tweak your schedule using conversational feedback.
    *   **Interactive Mapping:** Automatically plot your chronological journey on an interactive route map.

    ### 💰 Logistics, Export & Share
    *   **Budget Breakdown:** Generate granular, point-to-point transit guides and HKD cost estimates.
    *   **Social Export:** Download a mobile-optimized HTML file designed for Instagram Stories.
    *   **Community Publishing:** Share your custom itineraries to the public cloud database for others to discover.
    """)
    st.markdown('</div><br>', unsafe_allow_html=True)
    if st.button("Got it! Let's Go 🚀", type="primary", use_container_width=True):
        st.session_state.welcome_shown = True
        st.rerun()
    st.stop()

st.title("📍 Pinpoint")
st.subheader("Grab your Itinerary on Fingertips!")
st.markdown("---")

# --- 3. API & TRUE CLOUD DB SETUP ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("System Error: API Key missing.")
    st.stop()
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-flash-lite')

@st.cache_data(ttl=2)
def load_itineraries():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1")
        if df.empty or 'ID' not in df.columns:
            return pd.DataFrame(columns=["ID", "Title", "Pace", "Duration", "Itinerary", "Budget", "Liked_By"])
        return df.fillna("")
    except:
        return pd.DataFrame(columns=["ID", "Title", "Pace", "Duration", "Itinerary", "Budget", "Liked_By"])

@st.cache_data(ttl=2)
def load_comments():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Comments")
        if df.empty or 'Comment_ID' not in df.columns:
            return pd.DataFrame(columns=["Comment_ID", "Itinerary_ID", "User_Name", "Content", "Liked_By"])
        return df.fillna("")
    except:
        return pd.DataFrame(columns=["Comment_ID", "Itinerary_ID", "User_Name", "Content", "Liked_By"])

def save_itineraries(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet="Sheet1", data=df)
    st.cache_data.clear()

def save_comments(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet="Comments", data=df)
    st.cache_data.clear()

def toggle_like(liked_by_str, user_id):
    liked_list = str(liked_by_str).split(',') if str(liked_by_str).strip() != '' else []
    if user_id in liked_list:
        liked_list.remove(user_id)
    else:
        liked_list.append(user_id)
    return ','.join(liked_list)

# ==========================================
# VIEW ROUTER 1: DETAIL PAGE (獨立詳情與留言頁面)
# ==========================================
if st.session_state.current_view == 'detail':
    if st.button("⬅️ Back to Explore"):
        st.session_state.current_view = 'home'
        st.rerun()

    df_iti = load_itineraries()
    current_iti = df_iti[df_iti['ID'] == st.session_state.detail_itinerary_id]
    
    if current_iti.empty:
        st.error("Itinerary not found.")
        st.button("Go Back", on_click=lambda: st.session_state.update(current_view='home'))
    else:
        row = current_iti.iloc[0]
        likes_list = str(row['Liked_By']).split(',') if str(row['Liked_By']).strip() != '' else []
        like_count = len(likes_list)
        has_liked = st.session_state.user_id in likes_list

        st.markdown(f"## {row['Title']}")
        st.caption(f"⏱️ {row['Duration']} | 🚶‍♂️ Pace: {row['Pace']}")
        
        btn_label = f"❤️ {like_count} Likes (Click to Unlike)" if has_liked else f"🤍 {like_count} Likes"
        if st.button(btn_label, key=f"detail_like_{row['ID']}"):
            new_liked_by = toggle_like(row['Liked_By'], st.session_state.user_id)
            df_iti.loc[df_iti['ID'] == row['ID'], 'Liked_By'] = new_liked_by
            save_itineraries(df_iti)
            st.rerun()

        with st.container(border=True):
            st.markdown("**📝 Itinerary:**")
            st.markdown(row['Itinerary'])
            st.markdown("---")
            st.markdown("**💰 Logistics & Budget:**")
            st.markdown(row['Budget'])

        st.markdown("---")
        st.markdown("### 💬 Comments")
        
        df_com = load_comments()
        iti_comments = df_com[df_com['Itinerary_ID'] == row['ID']]

        if iti_comments.empty:
            st.info("No comments yet. Be the first to share your thoughts!")
        else:
            for c_idx, c_row in iti_comments.iterrows():
                c_likes_list = str(c_row['Liked_By']).split(',') if str(c_row['Liked_By']).strip() != '' else []
                c_like_count = len(c_likes_list)
                c_has_liked = st.session_state.user_id in c_likes_list
                
                st.markdown(f"""
                <div class="comment-box">
                    <strong>👤 {c_row['User_Name']}</strong><br>
                    {c_row['Content']}
                </div>
                """, unsafe_allow_html=True)
                
                c_btn_label = f"❤️ {c_like_count}" if c_has_liked else f"🤍 {c_like_count}"
                if st.button(c_btn_label, key=f"clike_{c_row['Comment_ID']}"):
                    new_c_liked = toggle_like(c_row['Liked_By'], st.session_state.user_id)
                    df_com.loc[df_com['Comment_ID'] == c_row['Comment_ID'], 'Liked_By'] = new_c_liked
                    save_comments(df_com)
                    st.rerun()

        with st.form("new_comment_form", clear_on_submit=True):
            st.markdown("##### Leave a Comment")
            c_name = st.text_input("Your Name (Optional):", placeholder="Anonymous")
            c_content = st.text_area("What do you think about this trip?")
            submitted = st.form_submit_button("Post Comment")
            
            if submitted:
                if not c_content.strip():
                    st.warning("Please enter a comment before posting.")
                else:
                    new_c_id = str(uuid.uuid4())[:8]
                    new_comment = pd.DataFrame([{
                        "Comment_ID": new_c_id,
                        "Itinerary_ID": row['ID'],
                        "User_Name": c_name if c_name.strip() else "Anonymous Traveler",
                        "Content": c_content,
                        "Liked_By": ""
                    }])
                    df_com = pd.concat([df_com, new_comment], ignore_index=True)
                    save_comments(df_com)
                    st.success("Comment posted successfully!")
                    st.rerun()

# ==========================================
# VIEW ROUTER 2: HOME TABS (社群大廳與創建)
# ==========================================
elif st.session_state.current_view == 'home':
    tab_explore, tab_create = st.tabs(["🌍 Explore Community", "✨ Create Itinerary"])

    # --- TAB 1: EXPLORE COMMUNITY ---
    with tab_explore:
        st.markdown("### Discover & Get Inspired")
        
        db_df = load_itineraries()
        
        if db_df.empty:
            st.info("The community is currently empty. Go to 'Create Itinerary' and be the first to publish!")
        else:
            db_df['Like_Count'] = db_df['Liked_By'].apply(lambda x: len(str(x).split(',')) if str(x).strip() != '' else 0)
            
            col_f1, col_f2 = st.columns(2)
            filter_pace = col_f1.selectbox("Filter by Pace:", ["All", "Relaxed", "Balanced", "Packed"])
            
            filtered_df = db_df.copy()
            if filter_pace != "All":
                filtered_df = filtered_df[filtered_df['Pace'] == filter_pace]
                
            filtered_df = filtered_df.sort_values(by="Like_Count", ascending=False)
            
            if filtered_df.empty:
                st.write("No itineraries found for this filter.")
            else:
                for index, row in filtered_df.iterrows():
                    with st.container(border=True):
                        cols_header = st.columns([3, 1])
                        with cols_header[0]:
                            if index == filtered_df.index[0] and filter_pace == "All" and row['Like_Count'] > 0:
                                st.markdown(f"<span class='top-rated-badge'>🔥 Top Rated</span>", unsafe_allow_html=True)
                            st.markdown(f"#### {row['Title']}")
                            st.caption(f"⏱️ {row['Duration']} | 🚶‍♂️ Pace: {row['Pace']} | ❤️ {row['Like_Count']} Likes")
                        
                        with cols_header[1]:
                            if st.button("👁️ View Details", key=f"view_{row['ID']}", use_container_width=True):
                                st.session_state.current_view = 'detail'
                                st.session_state.detail_itinerary_id = row['ID']
                                st.rerun()

    # --- TAB 2: CREATE ITINERARY ---
    with tab_create:
        if st.session_state.publish_success_msg:
            st.success("🎉 Your itinerary was published successfully to the community!")
            if st.button("🔄 Create Another Itinerary"):
                st.session_state.publish_success_msg = False
                st.session_state.phase1_done = False
                st.session_state.phase2_done = False
                st.rerun()
            st.markdown("---")

        if 'phase1_done' not in st.session_state: st.session_state.phase1_done = False
        if 'itinerary_text' not in st.session_state: st.session_state.itinerary_text = ''
        if 'all_locations' not in st.session_state: st.session_state.all_locations = []
        if 'phase2_done' not in st.session_state: st.session_state.phase2_done = False
        if 'transport_budget_text' not in st.session_state: st.session_state.transport_budget_text = ''

        uploaded_files = st.file_uploader('Upload visual inspirations (Images):', type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

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
                duration_option = st.selectbox('Duration:', ['Half Day', '1 Day', '2 Days', '3 Days', '1 Week'])
                start_time = st.text_input('Start Time:', value='09:00')
            with col2:
                pace_option = st.selectbox('Pace:', ['Relaxed', 'Balanced', 'Packed'])
                end_time = st.text_input('End Time:', value='21:00')
            
            extra_details = st.text_input('Additional Hints (Optional):')
            enable_map = st.checkbox('Generate Interactive Route Map (Note: May take a few minutes)', value=False)

            if st.button('Generate Custom Itinerary', type='primary', use_container_width=True):
                with st.spinner('Analyzing and building your schedule...'):
                    prompt = f"""
                    You are a professional travel planner. Analyze the images and details: {extra_details}.
                    OUTPUT STRICTLY IN ENGLISH. 
                    Visual Formatting Rule: Use ONLY these functional unicode icons: 📍, 🕒, 🚶‍♂️, 🍽️. NO EXPRESSIVE EMOJIS.
                    Constraints:
                    1. Anchor ONLY on locations found in the images.
                    2. Apply parameters: Duration: {duration_option}, Pace: {pace_option}, Window: {start_time} to {end_time}.
                    3. Provide a chronological itinerary divided clearly by days using Markdown headings (###). 
                    4. EXTRA RECOMMENDATIONS: Create a dedicated Markdown table titled "### Extra Recommendations".
                    CRITICAL: End with "===MAP_DATA===" followed by a comma-separated list of the exact official landmark names.
                    """
                    try:
                        response = model.generate_content([prompt, *images])
                        raw_text = response.text
                        if "===MAP_DATA===" in raw_text:
                            parts = raw_text.split("===MAP_DATA===")
                            st.session_state.itinerary_text = parts[0].strip()
                            st.session_state.all_locations = [loc.replace('\n', '').strip() for loc in parts[1].split(',') if loc.replace('\n', '').strip()]
                        else:
                            st.session_state.itinerary_text = raw_text.strip()
                            st.session_state.all_locations = []
                        st.session_state.phase1_done = True
                        st.session_state.phase2_done = False  
                        st.session_state.publish_success_msg = False
                        st.rerun()
                    except Exception as e:
                        st.error(f'Generation Error: {str(e)}')

        if st.session_state.phase1_done:
            st.markdown('---')
            st.markdown('### Your Pinpoint Itinerary')
            with st.container(border=True):
                st.markdown(st.session_state.itinerary_text)

            st.markdown('### Refine Your Itinerary')
            user_feedback = st.text_area("Need adjustments? Tell us what to change:")
            if st.button("Update Schedule"):
                with st.spinner("Adjusting your schedule..."):
                    refine_prompt = f"""
                    You are a professional travel planner. Adjust the itinerary based on user feedback.
                    OUTPUT STRICTLY IN ENGLISH. Use ONLY functional icons. NO EXPRESSIVE EMOJIS.
                    Existing Itinerary: {st.session_state.itinerary_text}
                    Feedback: {user_feedback}
                    Constraints: Maintain formatting. CRITICAL: End with "===MAP_DATA===" and landmark list.
                    """
                    try:
                        refine_resp = model.generate_content([refine_prompt])
                        raw_refine_text = refine_resp.text
                        if "===MAP_DATA===" in raw_refine_text:
                            parts = raw_refine_text.split("===MAP_DATA===")
                            st.session_state.itinerary_text = parts[0].strip()
                            st.session_state.all_locations = [loc.replace('\n', '').strip() for loc in parts[1].split(',') if loc.replace('\n', '').strip()]
                        else:
                            st.session_state.itinerary_text = raw_refine_text.strip()
                        st.session_state.phase2_done = False
                        st.session_state.publish_success_msg = False
                        st.rerun()
                    except Exception as e:
                        st.error(f'Refinement Error: {str(e)}')

            if enable_map and st.session_state.all_locations:
                st.markdown('### Global Route Overview')
                with st.spinner('Plotting map...'):
                    geolocator = Nominatim(user_agent='pinpoint_app_v12')
                    m = folium.Map(location=[22.3193, 114.1694], zoom_start=11)
                    valid_coords = []
                    for idx, loc in enumerate(st.session_state.all_locations):
                        try:
                            location = geolocator.geocode(loc + ', Hong Kong', timeout=10)
                            if location:
                                coords = [location.latitude, location.longitude]
                                folium.Marker(coords, popup=loc, tooltip=f"Stop {idx + 1}", icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
                                valid_coords.append(coords)
                            time.sleep(1)
                        except:
                            time.sleep(1)
                    if len(valid_coords) > 1:
                        folium.PolyLine(valid_coords, color='#ff4b4b', weight=3).add_to(m)
                        m.fit_bounds(valid_coords)
                    st_folium(m, width=700, height=450, key="global_route_map")

            st.markdown('---')
            if not st.session_state.phase2_done:
                if st.button('Get Transport & Budget Breakdown', type='primary', use_container_width=True):
                    with st.spinner('Calculating routes and budget...'):
                        budget_prompt = f"""
                        Based on this itinerary: {st.session_state.itinerary_text}
                        OUTPUT STRICTLY IN ENGLISH. NO EXPRESSIVE EMOJIS.
                        Requirements: Detailed Transport Guide, Itemized Budget in HKD, Total Calculation.
                        """
                        try:
                            budget_resp = model.generate_content([budget_prompt])
                            st.session_state.transport_budget_text = budget_resp.text
                            st.session_state.phase2_done = True
                            st.session_state.publish_success_msg = False
                            st.rerun()
                        except Exception as e:
                            st.error(f'Error: {str(e)}')

        if st.session_state.phase2_done:
            st.markdown('### Logistics & Budget Breakdown')
            with st.container(border=True):
                st.markdown(st.session_state.transport_budget_text)

            st.markdown('---')
            st.markdown('### 🚀 Export (Instagram-Ready)')
            full_html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pinpoint Itinerary</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
                <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
                <style>
                    body {{ font-family: 'Inter', sans-serif; background: #f7f9fc; margin: 0; padding: 20px; display: flex; justify-content: center; }}
                    .story-container {{ background: white; max-width: 420px; width: 100%; padding: 30px 20px; border-radius: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
                    .header {{ text-align: center; margin-bottom: 25px; }}
                    h1 {{ color: #ff4b4b; margin: 0; font-size: 28px; font-weight: 700; }}
                    h3 {{ color: #718096; margin: 5px 0 20px 0; font-size: 14px; font-weight: 400; }}
                    .content-card h3 {{ font-size: 18px; color: #1a202c; border-bottom: 2px solid #edf2f7; padding-bottom: 8px; margin-top: 25px; }}
                    .content-card {{ background: #fdfdfd; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; line-height: 1.6; font-size: 14px; }}
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
                    <div id="raw-itinerary" style="display:none;">{st.session_state.itinerary_text}</div>
                    <div id="raw-budget" style="display:none;">{st.session_state.transport_budget_text}</div>
                    <div class="content-card" id="rendered-itinerary"></div><br>
                    <div class="content-card" id="rendered-budget"></div>
                </div>
                <script>
                    document.getElementById('rendered-itinerary').innerHTML = marked.parse(document.getElementById('raw-itinerary').textContent);
                    document.getElementById('rendered-budget').innerHTML = marked.parse(document.getElementById('raw-budget').textContent);
                </script>
            </body>
            </html>
            """
            b64_html = base64.b64encode(full_html.encode()).decode()
            href_html = f'<a href="data:text/html;base64,{b64_html}" download="Pinpoint_Story.html" style="text-decoration: none; padding: 16px 20px; background-color: #111; color: white; font-weight: bold; border-radius: 12px; display: block; text-align: center;">Download Image Format (HTML)</a>'
            st.markdown(href_html, unsafe_allow_html=True)

            st.markdown('---')
            st.markdown('### 🌐 Publish to Community')
            st.caption("Share your masterpiece! Give it a catchy title so others can discover it.")
            post_title = st.text_input("Give your itinerary a title:", placeholder="e.g., Ultimate 3-Day HK Foodie Tour")
            
            if st.button("Publish Itinerary", type="primary"):
                if not post_title:
                    st.warning("Please enter a title before publishing.")
                else:
                    with st.spinner("Publishing your itinerary to the cloud database..."):
                        db_df_current = load_itineraries()
                        new_id = str(uuid.uuid4())[:8]
                        new_row = pd.DataFrame([{
                            "ID": new_id,
                            "Title": post_title,
                            "Pace": pace_option,
                            "Duration": duration_option,
                            "Itinerary": st.session_state.itinerary_text,
                            "Budget": st.session_state.transport_budget_text,
                            "Liked_By": "" 
                        }])
                        updated_df = pd.concat([db_df_current, new_row], ignore_index=True)
                        if save_itineraries(updated_df):
                            st.session_state.publish_success_msg = True
                            st.balloons()
                            time.sleep(0.5)
                            st.rerun()
