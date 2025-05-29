import re
import time
import streamlit as st


from functools import partial
from joblib import Parallel, delayed
from vectorDB import vector_search as vs


#* Add custom CSS for scrolling and job description handling
st.markdown("""
    <style>
        /* Job cards container */
        .st-key-job-cards-container {
            max-height: 80vh;
            overflow-y: auto;
            padding-right: 10px;
        }
        
        /* Job card */
        .st-key-job-card {
            display: flex;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        [class*="st-key-job-card-"] {
            margin: 4px 0;
            padding: 0 8px;
        }
        
        .job-title {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 8px;
        }
        
        .job-company {
            font-size: 14px;
            color: #555;
            margin-bottom: 8px;
        }
        
        .job-type {
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }
        
        .job-location {
            font-size: 14px;
            color: #777;
            margin-bottom: 12px;
        }
        
        /* Job description container */
       .st-key-job-description-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
        }
        [class*="st-key-job-description-"] {
            margin: 4px 0;
            padding: 0 8px;
        }
        
        .job-description {
            font-size: 14px;
            color: #444;
            line-height: 1.5;
        }
        
        .stAlertContainer {
            margin-top: 24px;
        }
        
        /* Read More / Show Less Button */
        [class*="st-key-read_more_btn_"] 
        > div:nth-child(1) > button:nth-child(1) {
            background-color: transparent;
            color: #1E88E5;
            border: none;
            padding: 0;
            cursor: pointer;
            text-decoration: underline;
        }
        
        div[class*="st-key-job-card-"] 
        > div:nth-child(1) > div:nth-child(1)
        > div:nth-child(1) > div:nth-child(2) {
            display: flex;
            align-items: right;
            justify-content: right;
            padding-right: 10px;
        }
    </style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_resume(resume_file):
    content, vector = vs.process_resume(resume_file)
    return content, vector


@st.cache_data(show_spinner=False)
def get_job_list(resume_vector, filter_dict):
    job_list = vs.vector_search(resume_vector, filter_dict)
    return job_list


@st.cache_data(show_spinner=False)
def get_job_recommendations(resume_vector, filter_dict):
    job_list = get_job_list(resume_vector, filter_dict)
    
    def parse_job(job):
        job_data = {}
        for key, value in job.payload.items():
            if key == "remoteWorkInfo" and value:
                text = value.get("text") if value.get("text") else None
                remote_type = value.get("type") if value.get("type") else None
                if text:
                    job_data[f"{key}"] = text
                elif remote_type:
                    job_data[f"{key}"] = remote_type
            
            elif key == "locationInfo" and value:
                city = value.get("jobLocationCity") if value.get("jobLocationCity") else None
                state = value.get("jobLocationState") if value.get("jobLocationState") else None
                if city and state:
                    job_data[f"{key}"] = f"{city}, {state}"
                elif city:
                    job_data[f"{key}"] = city
                elif state:
                    job_data[f"{key}"] = state
            
            elif value:
                job_data[f"{key}"] = value
        
        return job_data
    
    jobCard_list = Parallel(n_jobs=12, backend="threading")(
        delayed(parse_job)(job) for job in job_list
    )
    
    return jobCard_list


def filter_job_list(resume_vector, filter_dict):
    st.session_state["jobCard_list"] = get_job_recommendations(resume_vector, filter_dict)


@st.cache_data(show_spinner=False)
def get_job_description(job: dict) -> str:
    return job.get("jobDescription")


@st.cache_data(show_spinner=False)
def get_short_desc(text: str) -> str:
    return text[:300] + "..." if len(text) > 300 else text


def click_button(desc_key):
    st.session_state[desc_key] = not st.session_state[desc_key]


def change_job(job):
    st.session_state["selected_job"] = job


def main():
    #* Page Title and Caption
    st.markdown("""
            <div style='display: flex; flex-direction: column; align-items: center; text-align: center; margin: 0; padding: 0;'>
               <h1> 💬 Career Vector </h1>
               <caption> 🚀 The Career Vector for your job hunting needs!</caption>
            </div>
            """, unsafe_allow_html=True)
    
    #* Resume uploader
    st.sidebar.header("My Documents", divider="gray")
    resume_file = st.sidebar.file_uploader("Upload your Resume", type=["pdf", "docx", "doc"])
    
    #* Process the resume
    if resume_file and "resume_vector" not in st.session_state:
        with st.sidebar:
            with st.spinner("Processing your resume..."):
                resume_content, resume_vector = load_resume(resume_file)
            st.session_state["resume_content"] = resume_content
            st.session_state["resume_vector"] = resume_vector
            info_container = st.empty()
            with info_container.container():
                st.success("Resume processed successfully!")
                time.sleep(1)
                info_container.empty()
    

    
    #* Get job recommendations
    if "resume_vector" in st.session_state:
        #* Filter job
        jobTypes_list = [""] + [
            "Full-time", "Part-time", "Contract", "Internship", "Seasonal",
            "Temporary", "Non-tenure", "PRN", "Per diem", "Temp-to-hire",
            "Travel healthcare", "Permanent", "Tenure track", "Apprenticeship", "Tenured"
        ]
        
        st.sidebar.header("Filter Job", divider="gray")
        with st.sidebar:
            filter_col1, filter_col2 = st.columns([0.5, 0.5])
            with filter_col1:
                city_input = st.text_input("City", value="", placeholder="e.g. Los Angeles")
            with filter_col2:
                state_input = st.text_input("State", value="", placeholder="e.g. CA")
            job_type_input = st.selectbox("Job Type", placeholder="Select Job Type", options=jobTypes_list)
        
        filter_dict = {
            "filter_city": city_input.strip() or None,
            "filter_state": state_input.strip() or None,
            "filter_job_type": job_type_input or None,
        }
        
        jobCard_list = get_job_recommendations(st.session_state["resume_vector"], filter_dict)
        with st.container():
            st.write("<div class='job-cards-container'/>", unsafe_allow_html=True)
            for job in jobCard_list:
                job_id = job.get("jobKey", hash(str(job)))
                
                @st.fragment
                def job_card_fragment(job, job_id):
                    col1, col2 = st.columns([0.7, 0.3])
                    
                    with col1:
                        if job.get("jobTitle"):
                            job_title = job.get("jobTitle")
                            st.write(f"<div class='job-title'>{job_title}</div>", unsafe_allow_html=True)
                        if job.get("companyName"):
                            company_name = job.get("companyName")
                            st.write(f"<div class='job-company'>Company: 🏢 {company_name}</div>", unsafe_allow_html=True)
                        if job.get("jobType"):
                            job_type = job.get("jobType")
                            st.write(f"<div class='job-type'>Job Type: 💼 {job_type}</div>", unsafe_allow_html=True)
                        if job.get("locationInfo"):
                            location_info = job.get("locationInfo")
                            st.write(f"<div class='job-location'>Location: 📍 {location_info}</div>", unsafe_allow_html=True)
                    
                    with col2:
                        if "selected_job" not in st.session_state:
                            st.session_state["selected_job"] = None
                        
                        resume_polish = st.button("Resume Polish", key=f"resume-polish-job-btn-{job_id}", on_click=partial(change_job, job), type="primary")
                        mock_interview = st.button("Mock Interview", key=f"mock-interview-job-btn-{job_id}", on_click=partial(change_job, job), type="primary")
                        
                        if resume_polish:
                            st.session_state["selected_job"] = job
                            st.switch_page("web/resume_q&a.py")
                        elif mock_interview:
                            st.session_state["selected_job"] = job
                            st.switch_page("web/mock_interview.py")
                        
                    if get_job_description(job):
                        job_description = get_job_description(job)
                        short_desc = get_short_desc(job_description)
                        
                        desc_key = f"job-description-{job_id}"
                        if desc_key not in st.session_state:
                            st.session_state[desc_key] = False
                        
                        st.write("<div class='job-description'> <strong>Job Description:</strong> </div>", unsafe_allow_html=True)
                        
                        with st.container(key=desc_key):
                            st.write("<div class='job-description-container'>", unsafe_allow_html=True)
                            
                            if st.session_state[desc_key]:
                                st.write(f"<div class='job-description'>{job_description}", unsafe_allow_html=True)
                            else:
                                st.write(f"<div class='job-description'>{short_desc}", unsafe_allow_html=True)
                            
                            button_text = "show less" if st.session_state[desc_key] else "read more"
                            st.button(button_text, key=f"read_more_btn_{job_id}", on_click=partial(click_button, desc_key))
            
                with st.container(border=True, key=f"job-card-{job_id}"):
                    job_card_fragment(job, job_id)
    
    else:
        st.info("Please upload your resume to get job recommendations!", icon=":material/info:")


if __name__ == "__main__":
    
    main()