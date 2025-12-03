"""Simple Streamlit chat interface - calls LangSmith backend"""

import streamlit as st
import uuid
from datetime import datetime
from config import supabase
import requests
import json

# LangSmith deployment URL
LANGSMITH_URL = "https://a3e-beta-test-47dfa3bfa7bf56c4a3f89c7dc4d37d41.us.langgraph.app"

# Page config
st.set_page_config(
    page_title="Environmental Report Assistant",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Environmental Report Assistant")
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
        "section": "5.2.1",
        "subject_property_file": None,
        "surrounding_property_files": []
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
                        "bucket": "Phase1",
                        "uploaded_at": datetime.now().isoformat(),
                        "size": len(file_bytes)
                    }

                    # Assign file role based on workflow stage
                    if not st.session_state.agent_state.get("subject_property_file"):
                        # First file = subject property
                        st.session_state.agent_state["subject_property_file"] = filename
                        st.success(f"✅ Uploaded {filename} (Subject Property)")
                    else:
                        # Subsequent files = surrounding properties
                        st.session_state.agent_state["surrounding_property_files"].append(filename)
                        st.success(f"✅ Uploaded {filename} (Surrounding Properties)")

                except Exception as e:
                    st.error(f"❌ Upload failed: {str(e)}")

    # Display uploaded files with roles
    if st.session_state.agent_state["uploaded_files"]:
        st.divider()
        st.subheader("Uploaded Files")
        
        subject_file = st.session_state.agent_state.get("subject_property_file")
        surrounding_files = st.session_state.agent_state.get("surrounding_property_files", [])
        
        for filename in st.session_state.agent_state["uploaded_files"].keys():
            if filename == subject_file:
                st.text(f"📄 {filename} (Subject)")
            elif filename in surrounding_files:
                st.text(f"📄 {filename} (Surrounding)")
            else:
                st.text(f"📄 {filename}")

    # Show extracted data
    if st.session_state.agent_state.get("subject_address"):
        st.divider()
        st.subheader("Extracted Data")
        st.text(f"📍 Subject: {st.session_state.agent_state['subject_address'][:50]}...")

    if st.session_state.agent_state.get("groundwater_flow"):
        st.text(f"🌊 Flow: {st.session_state.agent_state['groundwater_flow']}")

    # Reset button
    st.divider()
    if st.button("🔄 Reset Session", type="secondary"):
        st.session_state.clear()
        st.rerun()

# Main chat interface
st.divider()

# Display chat messages
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Describe task for Phase 1 Agent to complete"):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response from LangSmith
    with st.chat_message("assistant"):
        response_container = st.empty()

        try:
            # Build context message with state info
            uploaded_files = st.session_state.agent_state.get("uploaded_files", {})
            
            # Create a context string to prepend to user message
            context_info = ""
            if uploaded_files:
                context_info += "**SYSTEM CONTEXT:**\n"
                context_info += f"- uploaded_files: {list(uploaded_files.keys())}\n"
                for fname, finfo in uploaded_files.items():
                    context_info += f"  - {fname}: path={finfo['path']}\n"
                context_info += f"- session_id: {st.session_state.session_id}\n"
                context_info += f"- source: {st.session_state.agent_state.get('source')}\n"
                context_info += f"- section: {st.session_state.agent_state.get('section')}\n"
                context_info += f"- subject_property_file: {st.session_state.agent_state.get('subject_property_file')}\n"
                context_info += f"- surrounding_property_files: {st.session_state.agent_state.get('surrounding_property_files', [])}\n"
                if st.session_state.agent_state.get("subject_address"):
                    context_info += f"- subject_address: {st.session_state.agent_state['subject_address']}\n"
                if st.session_state.agent_state.get("groundwater_flow"):
                    context_info += f"- groundwater_flow: {st.session_state.agent_state['groundwater_flow']}\n"
                context_info += "\n"
            
            # Combine user message with context
            full_message = f"{context_info}**USER MESSAGE:** {prompt}"
            
            # Prepare payload for LangSmith
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

            # Stream agent response from LangSmith
            response_text = ""
            status_text = st.empty()

            with requests.post(
                f"{LANGSMITH_URL}/runs/stream",
                headers={
                    "Content-Type": "application/json"
                },
                json=payload,
                stream=True,
                timeout=300
            ) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        
                        # Parse SSE format
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # Remove 'data: ' prefix
                            
                            try:
                                data = json.loads(data_str)
                                
                                if "messages" in data:
                                    messages = data["messages"]
                                    if messages:
                                        last_message = messages[-1]
                                        
                                        if last_message.get("type") == "ai":
                                            # Update the response as it comes in
                                            response_text = last_message.get("content", "")
                                            response_container.markdown(response_text)
                                        else:
                                            # Show tool activity
                                            status_text.info("🔄 Processing...")
                            except json.JSONDecodeError:
                                pass
            
            # Clear status when done
            status_text.empty()

            # Add assistant response to chat history
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

