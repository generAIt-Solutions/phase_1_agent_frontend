"""Simple Streamlit chat interface for conversational environmental report processing"""

import streamlit as st
import uuid
from datetime import datetime
from agent import create_environmental_agent, initialize_state
from config import supabase
from langchain_core.messages import HumanMessage, AIMessage

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

if "agent" not in st.session_state:
    try:
        st.session_state.agent = create_environmental_agent()
    except Exception as e:
        st.error(f"Failed to initialize agent: {e}")
        st.stop()

if "agent_state" not in st.session_state:
    st.session_state.agent_state = initialize_state(
        session_id=st.session_state.session_id
    )

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
        # Upload to Supabase storage
        filename = uploaded_file.name

        # Check if already uploaded
        if filename not in st.session_state.agent_state["uploaded_files"]:
            with st.spinner(f"Uploading {filename}..."):
                try:
                    # Upload to Supabase
                    file_bytes = uploaded_file.read()
                    path = f"{st.session_state.session_id}/uploads/{filename}"

                    supabase.storage.from_("Phase1").upload(
                        path,
                        file_bytes,
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )

                    # Add to state
                    st.session_state.agent_state["uploaded_files"][filename] = {
                        "path": path,
                        "uploaded_at": datetime.now().isoformat(),
                        "size": len(file_bytes)
                    }

                    st.success(f"✅ Uploaded {filename}")

                except Exception as e:
                    st.error(f"❌ Upload failed: {str(e)}")

    # Show uploaded files
    if st.session_state.agent_state["uploaded_files"]:
        st.divider()
        st.subheader("Uploaded Files")
        for filename in st.session_state.agent_state["uploaded_files"].keys():
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
if prompt := st.chat_input("Ask me to process a report or ask questions..."):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
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
                if st.session_state.agent_state.get("subject_address"):
                    context_info += f"- subject_address: {st.session_state.agent_state['subject_address']}\n"
                if st.session_state.agent_state.get("groundwater_flow"):
                    context_info += f"- groundwater_flow: {st.session_state.agent_state['groundwater_flow']}\n"
                context_info += "\n"
            
            # Combine user message with context
            full_message = f"{context_info}**USER MESSAGE:** {prompt}"
            
            # Configure agent
            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            # Build input with just messages - deepagents doesn't use state dict
            agent_input = {
                "messages": [HumanMessage(content=full_message)]
            }

            # Stream agent response
            response_text = ""

            with st.spinner("Thinking..."):
                for event in st.session_state.agent.stream(
                    agent_input,
                    config=config,
                    stream_mode="values"
                ):
                    # Get the last message
                    if event.get("messages"):
                        last_message = event["messages"][-1]

                        if isinstance(last_message, AIMessage):
                            response_text = last_message.content
                            response_container.markdown(response_text)

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

# Instructions (collapsible)
with st.expander("ℹ️ How to Use"):
    st.markdown("""
    ### Getting Started

    1. **Upload a PDF**: Use the sidebar to upload your environmental report PDF
    2. **Select Configuration**: Choose the report source (EDR/ERIS) and section (5.2.1-5.2.4)
    3. **Start Chatting**: Ask the assistant to process your report

    ### Example Conversations

    **For Section 5.2.1 (Subject Property):**
    - You: "Process this file"
    - Assistant: "Sure! I'll extract and process the subject property data..."

    **For Section 5.2.2 (Surrounding Area):**
    - You: "Process this report"
    - Assistant: "I need the groundwater flow direction. What direction does groundwater flow?"
    - You: "East"
    - Assistant: "Thanks! Calculating distances... Here's your summary..."

    ### Available Sections

    - **5.2.1**: Subject Property (EDR) - Extracts property information
    - **5.2.2**: Surrounding Area (EDR) - Includes distance calculations
    - **5.2.3**: Subject Property (ERIS) - Extracts property information
    - **5.2.4**: Surrounding Area (ERIS) - Includes distance calculations

    ### Tips

    - The assistant will guide you through the process
    - It will ask for information when needed (like groundwater flow)
    - You can ask to see summaries, check status, or request help anytime
    - Upload files before asking to process them
    """)