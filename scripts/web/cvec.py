import time
import streamlit as st

from vectorDB import vector_search as vs


st.set_page_config(
    page_title="Career Vector",
    page_icon="🏠",
    layout="wide"
)


st.title("💬 Career Vector")
st.caption("🚀 The Career Vector for your job hunting needs!")


#* Define the resume uploader and processor components on the sidebar
st.sidebar.header("My Documents", divider="gray")
resume_file = st.sidebar.file_uploader("Upload your Resume", type=("pdf", "docx", "doc"))

@st.cache_data
def load_resume():
    resume_content, resume_vector = vs.process_resume(resume_file)
    return resume_content, resume_vector

@st.cache_resource
def get_job_recommendations(resume_vector):
    job_list = vs.vector_search(resume_vector, "ds_jobs")
    return job_list

if resume_file:
    with st.sidebar:
        info_container = st.empty()
        with info_container.container():
            with st.spinner("Processing your resume..."):
                resume_content, resume_vector = load_resume()
                time.sleep(2)
                st.session_state["resume_content"] = resume_content
                st.session_state["resume_vector"] = resume_vector
            st.success("Resume processed successfully!")
            st.balloons()
            time.sleep(2)
            info_container.empty()


#* Render job card components on the main page
def render_job_card(job):
    job_id = job.get("jobKey", hash(str(job)))
    
    html = "<div class='job-card'>"
    
    if job.get("jobTitle"):
        html += f"<div class='job-title'>{job['jobTitle']}</div>"
    
    if job.get("companyName"):
        html += f"<div class='job-company'>🏢 Company: {job['companyName']}</div>"
    
    if job.get("locationInfo"):
        html += f"<div class='job-location'>📍 Location: {job['locationInfo']}</div>"
    
    if job.get("jobDescription"):
        description = job["jobDescription"]
        short_desc = description[:300] + "..." if len(description) > 300 else description
        
        html += f"""
        <div class="job-description"><strong>Job Description:</strong>
        <div class="job-description-container">
            <div id="short-desc-{job_id}" class="job-description">{short_desc}</div>
            <div id="full-desc-{job_id}" class="job-description-full" style="display:none;">{description}</div>
            <button class="read-more-btn" id="read-more-{job_id}" onclick="toggleDescription('{job_id}')">Read More</button>
        </div>
        """
    
    html += "</div>"
    
    return html


#* Add custom CSS for scrolling and job description handling
st.markdown("""
<style>
    /* Job card container with scrolling */
    .job-cards-container {
        max-height: 80vh;
        overflow-y: auto;
        padding-right: 10px;
    }
    
    /* Styling for job cards */
    .job-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .job-title {
        font-weight: bold;
        font-size: 18px;
        margin-bottom: 8px;
    }
    
    .job-company {
        font-size: 16px;
        color: #555;
        margin-bottom: 8px;
    }
    
    .job-location {
        font-size: 14px;
        color: #777;
        margin-bottom: 12px;
    }
    
    /* Job description container */
    .job-description-container {
        position: relative;
    }
    
    .job-description {
        font-size: 14px;
        color: #444;
        line-height: 1.5;
        margin-bottom: 10px;
    }
    
    .job-description-full {
        font-size: 14px;
        color: #444;
        line-height: 1.5;
        margin-bottom: 10px;
    }
    
    .read-more-btn {
        background-color: transparent;
        color: #1E88E5;
        border: none;
        padding: 0;
        font-size: 14px;
        cursor: pointer;
        text-decoration: underline;
    }
    
    /* Custom scrollbar */
    .job-cards-container::-webkit-scrollbar {
        width: 6px;
    }
    
    .job-cards-container::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    .job-cards-container::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 10px;
    }
    
    .job-cards-container::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
</style>

<script>
    function toggleDescription(jobId) {
        const shortDesc = document.getElementById(`short-desc-${jobId}`);
        const fullDesc = document.getElementById(`full-desc-${jobId}`);
        const readMoreBtn = document.getElementById(`read-more-${jobId}`);
        
        if (shortDesc.style.display !== "none") {
            shortDesc.style.display = "none";
            fullDesc.style.display = "block";
            readMoreBtn.textContent = "Show Less";
        } else {
            shortDesc.style.display = "block";
            fullDesc.style.display = "none";
            readMoreBtn.textContent = "Read More";
        }
    }
</script>
""", unsafe_allow_html=True)


#* Get job recommendations based on the resume vector
if "resume_vector" in st.session_state:
    job_recommendations = get_job_recommendations(st.session_state["resume_vector"])
    st.session_state["job_recommendations"] = job_recommendations

    jobCard_list = {}
    for i, job in enumerate(st.session_state["job_recommendations"]):
        jobCard_list[i] = {}
        for key, value in job.payload.items():
            if key == "remoteWorkInfo" and value:
                text = value.get("text") if value.get("text") else None
                remote_type = value.get("type") if value.get("type") else None
                
                if text:
                    jobCard_list[i][f"{key}"] = text
                elif remote_type:
                    jobCard_list[i][f"{key}"] = remote_type
            
            elif key == "locationInfo" and value:
                city = value.get("jobLocationCity") if value.get("jobLocationCity") else None
                state = value.get("jobLocationState") if value.get("jobLocationState") else None
                
                if city and state:
                    jobCard_list[i][f"{key}"] = f"{city}, {state}"
                elif city:
                    jobCard_list[i][f"{key}"] = city
                elif state:
                    jobCard_list[i][f"{key}"] = state
            
            elif value:
                jobCard_list[i][f"{key}"] = value
    
    with st.container():
        st.markdown("<div class='job-cards-container'>", unsafe_allow_html=True)
        for i in jobCard_list:
            st.markdown(render_job_card(jobCard_list[i]), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
else:
    st.info("Please upload your resume to get job recommendations.")
