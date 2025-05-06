import streamlit as st
from models import resume_prompt as rp

with st.sidebar:
    openai_api_key = st.text_input("OpenAI API Key", key="resume_qa_api_key", type="password")
    "[View the source code](https://github.com/streamlit/llm-examples/blob/main/pages/1_File_Q%26A.py)"

st.title("💬 Resume Q&A")
st.caption("Ask questions about your resume and get answers from the LLM")

if "resume_content" in st.session_state:
    resume_content = st.session_state["resume_content"]
    selected_job = st.session_state["job_recommendations"][0]
    messages = rp.resume_prompt(selected_job, resume_content)
    response = rp.get_completion(openai_api_key, messages)
    st.write(response)
else:
    st.warning("Please upload a resume first to get the personalized job recommendations!")
