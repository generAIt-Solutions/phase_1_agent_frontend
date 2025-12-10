# streamlit.py
import streamlit as st
import uuid
import requests
import json
from config import supabase

st.set_page_config(page_title="Phase I ESA Agent", page_icon="🌍")
st.title("🌍 Phase I ESA Report Processor")
st.caption("Conversational AI for Phase I Environmental Site Assessment Reports")
st.caption("This agent will complete the ERIS/EDR sections for the subject property and surrounding properties Do Not upload the entire ERIS/EDR report.")
st.caption("Only upload the individual listings for each address Keep in mind the max amount of files you can upload at a time is 8.")
st.caption("DISCLAIMER: This agent may make mistakes. Make sure to double check the summaries prior to finalizing your report.")

# LangSmith Configuration
LANGSMITH_URL = "https://a3e-beta-test-47dfa3bfa7bf56c4a3f89c7dc4d37d41.us.langgraph.app"
ASSISTANT_ID = "e7bec632-7e78-51e1-bb27-d7e79cafb2ab"


def stream_langsmith_response(message: str, thread_id: str) -> str:
    """Stream response from LangSmith LangGraph deployment"""
    
    payload = {
        "assistant_id": ASSISTANT_ID,
        "input": {
            "messages": [{"role": "user", "content": message}]
        },
        "config": {
            "configurable": {"thread_id": thread_id}
        },
        "stream_mode": ["values"]
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer streamlit-frontend-2025"
    }
    
    full_response = ""
    
    try:
        with requests.post(
            f"{LANGSMITH_URL}/runs/stream",
            headers=headers,
            json=payload,
            stream=True,
            timeout=300
        ) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        try:
                            data = json.loads(data_str)
                            if "messages" in data:
                                messages = data["messages"]
                                if messages:
                                    last = messages[-1]
                                    if last.get("type") == "ai":
                                        content = last.get("content", "")
                                        if content:
                                            full_response = content
                        except json.JSONDecodeError:
                            pass
    except requests.exceptions.RequestException as e:
        return f"Error connecting to agent: {str(e)}"
    
    return full_response


# Initialize
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "file_paths" not in st.session_state:
    st.session_state.file_paths = {}

# Sidebar
with st.sidebar:
    source = st.selectbox("Report Source", ["EDR", "ERIS"])
    
    uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files:
        new_files = {f.name for f in uploaded_files}
        existing_files = set(st.session_state.file_paths.keys())
        
        if new_files != existing_files:
            st.session_state.file_paths = {}
            for i, f in enumerate(uploaded_files):
                path = f"{st.session_state.session_id}/uploads/{f.name}"
                file_bytes = f.read()
                supabase.storage.from_("Phase1").upload(
                    path, file_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"}
                )
                st.session_state.file_paths[f.name] = path
            st.success(f"✅ Uploaded {len(uploaded_files)} file(s)")
    
    if st.button("Reset"):
        for path in st.session_state.file_paths.values():
            try:
                supabase.storage.from_("Phase1").remove([path])
            except:
                pass
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.file_paths = {}
        st.rerun()

# Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Build context with FULL PATHS, not just filenames
    files = list(st.session_state.file_paths.keys())
    paths = list(st.session_state.file_paths.values())
    
    subject_file_path = paths[0] if paths else None
    surrounding_file_paths = paths[1:] if len(paths) > 1 else []
    
    context = f"""**SYSTEM CONTEXT:**
- session_id: {st.session_state.session_id}
- source: {source}
- subject_property_file: {subject_file_path}
- surrounding_property_files: {surrounding_file_paths}
"""
    
    full_message = f"{context}\n\n**USER MESSAGE:** {prompt}"
    
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            ai_message = stream_langsmith_response(
                message=full_message,
                thread_id=st.session_state.session_id
            )
            st.markdown(ai_message)
            st.session_state.messages.append({"role": "assistant", "content": ai_message})
