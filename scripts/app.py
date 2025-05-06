import streamlit as st

pg_main = st.Page("web/cvec.py", title="Career Vector", icon="🏠", default=True)
pg_chatbot = st.Page("web/resume_q&a.py", title="Resume Polish", icon=":material/edit:")
pg = st.navigation([pg_main, pg_chatbot])
pg.run()