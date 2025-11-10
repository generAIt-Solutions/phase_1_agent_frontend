"""Simple Streamlit chat interface - calls LangSmith backend"""

import streamlit as st
import uuid
from datetime import datetime
from config import supabase
import requests
import json
import os

# LangSmith deployment URL
LANGSMITH_URL = "https://a3e-beta-test-47dfa3bfa7bf56c4a3f89c7dc4d37d41.us.langgraph.app"
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")

# Page config
st.set_page_config(
    page_title="Environmental Report Assistant",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Environmental Report Assistant")
st.caption("Conversational AI for Phase I Environmental Site Assessment Reports")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "agent_state" not in st.session_state:
    st.session_state.agent_state = {
        "uploaded_files": {},
        "session_id": st.session_state.session_id,
        "source": "EDR",
        "section": "5.2.1"
    }

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# Sidebar for configuration and file upload
with st.sidebar:
    st.header("Configuration")

    # Source selection
    source = st.selectbox(
        "Report Source",
        ["EDR", "ERIS"],
        key="source"
    )
    st.session_state.agent_state["source"] = source

    # Section selection
    section = st.selectbox(
        "Section",
        ["5.2.1", "5.2.2", "5.2.3", "5.2.4"],
        key="section"
    )
    st.session_state.agent_state["section"] = section

    st.divider()

    # File upload
    st.header("Upload PDF")
    uploaded_file = st.file_uploader(
        "Upload Environmental Report PDF",
        type=["pdf"],
        key="pdf_uploader"
    )

    if uploaded_file is not None:
        filename = uploaded_file.name
        if filename not in st.session_state.agent_state["uploaded_files"]:
            with st.spinner(f"Uploading {filename}..."):
                try:
                    file_bytes = uploaded_file.read()
                    path = f"{st.session_state.session_id}/uploads/{filename}"

                    supabase.storage.from_("Phase1").upload(
                        path,
                        file_bytes,
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )

                    st.session_state.agent_state["uploaded_files"][filename] = {
                        "path": path,
                        "uploaded_at": datetime.now().isoformat(),
                        "size": len(file_bytes)
                    }

                    st.success(f"✅ Uploaded {filename}")

                except Exception as e:
                    st.error(f"❌ Upload failed: {str(e)}")

    if st.session_state.agent_state["uploaded_files"]:
        st.divider()
        st.subheader("Uploaded Files")
        for filename in st.session_state.agent_state["uploaded_files"].keys():
            st.text(f"📄 {filename}")

    st.divider()
    if st.button("🔄 Reset Session", type="secondary"):
        st.session_state.clear()
        st.rerun()

st.divider()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me to process a report or ask questions..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_container = st.empty()

        try:
            uploaded_files = st.session_state.agent_state.get("uploaded_files", {})
            
            context_info = ""
            if uploaded_files:
                context_info += "**SYSTEM CONTEXT:**\n"
                context_info += f"- uploaded_files: {list(uploaded_files.keys())}\n"
                for fname, finfo in uploaded_files.items():
                    context_info += f"  - {fname}: path={finfo['path']}\n"
                context_info += f"- session_id: {st.session_state.session_id}\n"
                context_info += f"- source: {st.session_state.agent_state.get('source')}\n"
                context_info += f"- section: {st.session_state.agent_state.get('section')}\n\n"
            
            full_message = f"{context_info}**USER MESSAGE:** {prompt}"
            
            payload = {
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": full_message
                        }
                    ]
                },
                "config": {
                    "configurable": {
                        "thread_id": st.session_state.thread_id
                    }
                }
            }

            response_text = ""
            status_text = st.empty()

            with requests.post(
            f"{LANGSMITH_URL}/runs/stream",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LANGSMITH_API_KEY}" if LANGSMITH_API_KEY else ""
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