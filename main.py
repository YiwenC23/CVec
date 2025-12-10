import os
import streamlit as st
from pathlib import Path

def main():
    st.set_page_config(
        page_title="Career Vector",
        page_icon="🏠",
        layout="wide",
    )

    pg_main = st.Page("scripts/web/cvec.py", title="Career Vector", icon="🏠", default=True)
    pg_chatbot = st.Page("scripts/web/resume_q&a.py", title="Resume Polish", icon=":material/edit:")
    pg_mock_interview = st.Page("scripts/web/mock_interview.py", title="Mock Interview", icon=":material/question_answer:")
    pg = st.navigation([pg_main, pg_chatbot, pg_mock_interview])
    pg.run()

if __name__ == "__main__":
    main()
