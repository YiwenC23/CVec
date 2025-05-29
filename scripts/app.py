import os
import streamlit as st
from pathlib import Path
# from st_pages import add_page_title, get_nav_from_toml

st.set_page_config(
    page_title="Career Vector",
    page_icon="🏠",
    layout="wide",
)


pg_main = st.Page("web/cvec.py", title="Career Vector", icon="🏠", default=True)
pg_chatbot = st.Page("web/resume_q&a.py", title="Resume Polish", icon=":material/edit:")
pg_mock_interview = st.Page("web/mock_interview.py", title="Mock Interview", icon=":material/question_answer:")
pg = st.navigation([pg_main, pg_chatbot, pg_mock_interview])
pg.run()
