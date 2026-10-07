import streamlit as st
import google.generativeai as genai

st.title("🔧 API 金鑰權限診斷工具")

api_key = st.text_input("請貼上你的 AQ... 金鑰:", type="password")

if st.button("🔍 檢測可用模型"):
    if not api_key:
        st.warning("請先輸入金鑰")
    else:
        try:
            genai.configure(api_key=api_key)
            st.write("連線中，正在讀取權限清單...")
            
            # 獲取所有支援生成內容的模型
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            if models:
                st.success("成功連線！這把金鑰支援以下模型：")
                for m in models:
                    st.code(m)
            else:
                st.warning("連線成功，但這把金鑰目前沒有任何可用模型的權限。")
                
        except Exception as e:
            st.error(f"連線失敗，錯誤訊息：{str(e)}")
