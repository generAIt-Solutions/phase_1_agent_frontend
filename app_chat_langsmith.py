"""Simple Streamlit chat interface - calls LangSmith backend"""

import streamlit as st
import uuid
from datetime import datetime
from config import supabase
import requests
import json

# LangSmith deployment URL
LANGSMITH_URL = "https://a3e-beta-test-47dfa3bfa7bf56c4a3f89c7dc4d37d41.us.langgraph.app"
ASSISTANT_ID = "e7bec632-7e78-51e1-bb27-d7e79cafb2ab"

# Page config
st.set_page_config(
    page_title="Phase I ESA Report Processor",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Phase I ESA Report Processor")
st.caption("Conversational AI for Phase I Environmental Site Assessment Reports")
st.caption("This agent will complete the ERIS/EDR sections for the subject property and surrounding properties Do Not upload the entire ERIS/EDR report.")
st.caption("Only upload the individual listings for each address Keep in mind the max amount of files you can upload at a time is 8.")
st.caption("DISCLAIMER: This agent may make mistakes. Make sure to double check the summaries prior to finalizing your report.")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "agent_state" not in st.session_state:
    st.session_state.agent_state = {
        "uploaded_files": {},
        "session_id": st.session_state.session_id,
        "source": "EDR",
        "subject_property_file": None,
        "surrounding_property_files": []
    }

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# Sidebar
with st.sidebar:
    # Source selection
    source = st.selectbox(
        "Report Source",
        ["EDR", "ERIS"],
        key="source"
    )
    st.session_state.agent_state["source"] = source

    # File upload
    uploaded_files = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploader"
    )

    if uploaded_files:
        new_files = {f.name for f in uploaded_files}
        existing_files = set(st.session_state.agent_state["uploaded_files"].keys())
        
        if new_files != existing_files:
            st.session_state.agent_state["uploaded_files"] = {}
            st.session_state.agent_state["subject_property_file"] = None
            st.session_state.agent_state["surrounding_property_files"] = []
            
            for i, f in enumerate(uploaded_files):
                filename = f.name
                path = f"{st.session_state.session_id}/uploads/{filename}"
                file_bytes = f.read()
                
                supabase.storage.from_("Phase1").upload(
                    path,
                    file_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"}
                )
                
                st.session_state.agent_state["uploaded_files"][filename] = {
                    "path": path,
                    "bucket": "Phase1",
                    "uploaded_at": datetime.now().isoformat(),
                    "size": len(file_bytes)
                }
                
                # First file = subject, rest = surrounding
                if i == 0:
                    st.session_state.agent_state["subject_property_file"] = filename
                else:
                    st.session_state.agent_state["surrounding_property_files"].append(filename)
            
            st.success(f"✅ Uploaded {len(uploaded_files)} file(s)")

    # Reset button
    if st.button("Reset"):
        for fname, finfo in st.session_state.agent_state.get("uploaded_files", {}).items():
            try:
                supabase.storage.from_("Phase1").remove([finfo["path"]])
            except:
                pass
        st.session_state.clear()
        st.rerun()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_container = st.empty()

        try:
            # Build context message with state info
            uploaded_files = st.session_state.agent_state.get("uploaded_files", {})
            
            context_info = "**SYSTEM CONTEXT:**\n"
            context_info += f"- uploaded_files: {list(uploaded_files.keys())}\n"
            for fname, finfo in uploaded_files.items():
                context_info += f"  - {fname}: path={finfo['path']}\n"
            context_info += f"- session_id: {st.session_state.session_id}\n"
            context_info += f"- source: {st.session_state.agent_state.get('source')}\n"
            context_info += f"- subject_property_file: {st.session_state.agent_state.get('subject_property_file')}\n"
            context_info += f"- surrounding_property_files: {st.session_state.agent_state.get('surrounding_property_files', [])}\n"
            if st.session_state.agent_state.get("subject_address"):
                context_info += f"- subject_address: {st.session_state.agent_state['subject_address']}\n"
            if st.session_state.agent_state.get("state"):
                context_info += f"- state: {st.session_state.agent_state['state']}\n"
            if st.session_state.agent_state.get("groundwater_flow"):
                context_info += f"- groundwater_flow: {st.session_state.agent_state['groundwater_flow']}\n"
            context_info += "\n"
            
            full_message = f"{context_info}**USER MESSAGE:** {prompt}"
            
            payload = {
                "assistant_id": ASSISTANT_ID,
                "input": {
                    "messages": [{"role": "user", "content": full_message}]
                },
                "config": {
                    "configurable": {"thread_id": st.session_state.thread_id}
                },
                "stream_mode": ["values"]
            }

            response_text = ""
            status_text = st.empty()

            with requests.post(
                f"{LANGSMITH_URL}/runs/stream",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer streamlit-frontend-2025"
                },
                json=payload,
                stream=True,
                timeout=300
            ) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]
                            
                            try:
                                data = json.loads(data_str)
                                
                                if "messages" in data:
                                    messages = data["messages"]
                                    if messages:
                                        last_message = messages[-1]
                                        
                                        if last_message.get("type") == "ai":
                                            response_text = last_message.get("content", "")
                                            response_container.markdown(response_text)
                                        else:
                                            status_text.info("🔄 Processing...")
                            except json.JSONDecodeError:
                                pass
            
            status_text.empty()

            if response_text:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text
                })

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            response_container.error(error_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg
            })
            import traceback
            st.code(traceback.format_exc())
