import os
import sys
import time
# import ollama
import numpy as np
import pandas as pd
import streamlit as st

#* Add the parent directory to the Python path
__package__ = "scripts"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#* Import modules
from prompts.resume_prompt import resume_prompt, get_completion
from vectorDB.vector_store import load_data
from vectorDB.vector_search import process_resume, vector_search

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Configures the Streamlit page with several settings
st.set_page_config(
    page_title="MiniChat", 
    page_icon=":robot_face:", 
    initial_sidebar_state="expanded",
    layout="wide",
    menu_items={
        'Get Help': 'https://www.example.com/help',
        'Report a bug': 'https://www.example.com/bug',
        'About': 'MiniChat with Job Recommendations'
    }
)


st.markdown("""
    <style>
        /* Add action button styles */
        .stButton button {
            border-radius: 50% !important;             /* Make the button circular */
            width: 32px !important;                    /* Set the width of the button */
            height: 32px !important;                   /* Set the height of the button */
            padding: 0 !important;                     /* Remove padding */
            background-color: transparent !important;  /* Make the background transparent */
            border: 1px solid #ddd !important;         /* Add a border */
            display: flex !important;                  /* Use flexbox for centering */
            align-items: center !important;            /* Center the icon vertically */
            justify-content: center !important;        /* Center the icon horizontally */
            font-size: 14px !important;                /* Set the font size */
            color: #666 !important;                    /* Set the color */
            margin: 5px 0 !important;                  /* Add margin between buttons */
        }
        .stButton button:hover {
            border-color: #999 !important;             /* Change border color on hover */
            color: #333 !important;                    /* Change text color on hover */
            background-color: #f5f5f5 !important;      /* Change background color on hover */
        }
        .stMainBlockContainer > div:first-child {
            margin-top: -35px !important;  /* Optional: Slight spacing if needed */
        }
        .stAPP > div:last-child {
            margin-bottom: -35px !important;  /* Optional: slight space */
        }
        /* Reset basic styles for the action buttons */
        .stButton > button {
            all: unset !important;                     /* Reset all default styles */
            box-sizing: border-box !important;         /* Include padding and border in the element's total width and height */
            border-radius: 50% !important;             /* Make the button circular */
            width: 18px !important;                    /* Set the width of the button */
            height: 18px !important;                   /* Set the height of the button */
            min-width: 18px !important;                /* Set the minimum width of the button */
            min-height: 18px !important;               /* Set the minimum height of the button */
            max-width: 18px !important;                /* Set the maximum width of the button */
            max-height: 18px !important;               /* Set the maximum height of the button */
            padding: 0 !important;                     /* Remove padding */
            background-color: transparent !important;  /* Make the background transparent */
            border: 1px solid #ddd !important;         /* Add a border */
            display: flex !important;                  /* Use flexbox for centering */
            align-items: center !important;            /* Center the icon vertically */
            justify-content: center !important;        /* Center the icon horizontally */
            font-size: 14px !important;                /* Set the font size */
            color: #888 !important;                    /* Set the color */
            cursor: pointer !important;                /* Change the cursor to a pointer on hover */
            transition: all 0.2s ease !important;      /* Add a smooth transition for hover effects */
            margin: 0 2px !important;                  /* Add margin between buttons */
        }
        /* Define the Process button on the sidebar */
        .stSidebar .stButton > button {
            all: initial !important;
            background-color: #2B2C35 !important;      /* Set the background color to green */
            border: 1px solid #54555C !important;         /* Add a border */
            border-radius: 6px !important;             /* Set the border radius */
            height: auto !important;                   /* Set the height to auto */
            width: auto !important;                    /* Set the width to auto */
            padding: 8px 16px !important;              /* Set the padding to 6px and 12px */
            font-size: 14px !important;                /* Set the font size */
            color: #fff !important;                    /* Set the text color to white */
            cursor: pointer !important;                /* Change the cursor to a pointer on hover */
            transition: all 0.2s ease !important;      /* Add a smooth transition for hover effects */
            margin: 0 2px !important;                  /* Add margin between buttons */
        }
        .stSidebar .stButton > button:hover {
            border-color: #999 !important;             /* Change border color on hover */
            color: #333 !important;                    /* Change text color on hover */
            background-color: #5F8575 !important;      /* Change the background color on hover */
        }
        
        /* Job posting card styles */
        .job-card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;  /* Make all cards the same height */
            display: flex;
            flex-direction: column;
        }
        .job-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .job-title {
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 8px;
            color: #333;
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
        .job-description {
            font-size: 14px;
            color: #444;
            margin-bottom: 12px;
            line-height: 1.4;
        }
        .job-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
        }
        .job-tag {
            background-color: #f0f0f0;
            border-radius: 16px;
            padding: 4px 10px;
            font-size: 12px;
            color: #555;
        }
        .job-details-btn {
            background-color: #2B2C35;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.2s ease;
        }
        .job-details-btn:hover {
            background-color: #5F8575;
        }
        
        /* Split pane styling */
        .main-content {
            display: flex;
            gap: 20px;
        }
        .chat-container {
            flex: 7;
        }
        .job-container {
            flex: 3;
            border-left: 1px solid #e0e0e0;
            padding-left: 20px;
            max-height: 85vh;
            overflow-y: auto;
        }
        
        /* Customize job panel header */
        .job-panel-header {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 16px;
            color: #333;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 8px;
        }
        
        /* Make chat input full width of its container */
        .stChatInput {
            width: 100%;
        }
    </style>
    """, unsafe_allow_html=True)


system_prompt = []


def clear_chat_history():
    del st.session_state.messages
    del st.session_state.chat_history


def delete_conversation_pair(index):
    st.session_state.messages.pop(index)
    st.session_state.messages.pop(index - 1)
    st.session_state.chat_history.pop(index)
    st.session_state.chat_history.pop(index - 1)
    st.rerun()


# Mock function to get job recommendations --> will be replaced with actual recommendation algorithm --> subject to change!!!!!
def get_job_recommendations(num_jobs=5):
    mock_jobs = [
        {
            "id": 1,
            "title": "Data Scientist",
            "company": "TechCorp Inc.",
            "location": "San Francisco, CA",
            "description": "Looking for a data scientist with expertise in NLP and machine learning to join our growing team.",
            "tags": ["Python", "Machine Learning", "NLP", "SQL"],
            "match_score": 95
        },
        {
            "id": 2,
            "title": "ML Engineer",
            "company": "AI Solutions",
            "location": "Remote",
            "description": "Build and optimize ML systems that solve real-world problems at scale.",
            "tags": ["PyTorch", "TensorFlow", "MLOps", "Python"],
            "match_score": 88
        },
        {
            "id": 3,
            "title": "Data Analyst",
            "company": "FinTech Innovations",
            "location": "New York, NY",
            "description": "Analyze financial data and create meaningful insights for our clients.",
            "tags": ["SQL", "Tableau", "Excel", "Statistics"],
            "match_score": 82
        },
        {
            "id": 4,
            "title": "Research Scientist",
            "company": "BioData Lab",
            "location": "Boston, MA",
            "description": "Conduct research on applying AI to solve complex biological problems.",
            "tags": ["Biology", "AI", "Research", "PhD"],
            "match_score": 79
        },
        {
            "id": 5,
            "title": "Software Engineer - AI",
            "company": "InnovateTech",
            "location": "Austin, TX",
            "description": "Develop and maintain AI-powered features in our enterprise software.",
            "tags": ["Java", "Python", "AI Integration", "Cloud"],
            "match_score": 75
        }
    ]
    return mock_jobs

# render job card components
def render_job_card(job):
    # Sets a color based on the job's match score
    match_color = "green" if job['match_score'] >= 85 else "orange" if job['match_score'] >= 70 else "gray"
    
    # Creates HTML for a job card with several elements
    html = f"""
    <div class="job-card">
        <div class="job-title">{job['title']}</div>
        <div class="job-company">{job['company']}</div>
        <div class="job-location">📍 {job['location']}</div>
        <div class="job-description">{job['description']}</div>
        <div class="job-tags">
    """
    
    # For each tag in the job's tags array, adds a span element with the "job-tag" class
    for tag in job['tags']:
        html += f'<span class="job-tag">{tag}</span>'
        
    # Adds a footer section at the bottom of the card with:
    #      1. The match score percentage, colored according to the match_color
    #      2. A "View Details" button that currently just shows an alert (placeholder functionality) --> subject to change!!!!!
    html += f"""
        </div>
        <div style="margin-top: auto; padding-top: 10px;"> <!-- Push to bottom of card -->
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: {match_color}; font-weight: bold;"> 
                    {job['match_score']}% Match
                </span>
                <button class="job-details-btn" onclick="alert('Job details would open here')">View Details</button>
            </div>
        </div>
    </div>
    """
    return html


def init_chat_history():
    # Checks if there are existing messages in st.session_state.messages
    if "messages" in st.session_state:
        # loops through them to get both the index and message content
        for i, message in enumerate(st.session_state.messages):
            # For assistant messages
            if message["role"] == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(message["content"], unsafe_allow_html=True)
                    
                    # Add action button below the message content to delete information
                    if st.button("×", key=f"delete_{i}"):
                            st.session_state.messages.pop(i)
                            st.session_state.messages.pop(i - 1)
                            st.session_state.chat_history.pop(i)
                            st.session_state.chat_history.pop(i - 1)
                            st.rerun()
            # For user messages
            else:
                st.markdown(f"""
                            <div style='display: flex; justify-content: flex-end;'>
                                <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: #ddd; border-radius: 10px; color: black;'>
                                    {message['content']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
    # If no messages exist yet, initializes empty lists for both messages and chat_history in the session state
    else:
        st.session_state.messages = []
        st.session_state.chat_history = []
    
    return st.session_state.messages


# Initialize the show_job_panel session state variable if it doesn't exist
if "show_job_panel" not in st.session_state:
    st.session_state.show_job_panel = True

# Create the checkbox with a different key to avoid conflict
job_panel_checkbox = st.sidebar.checkbox(
    "Show job recommendations", 
    value=st.session_state.show_job_panel, 
    key="job_panel_checkbox"
)

# Update the session state based on the checkbox value
st.session_state.show_job_panel = job_panel_checkbox

# Define the sidebar components
st.markdown("""
        <style>
            [data-testid='stSidebarCollapseButton'] {
                display: inline !important;
                padding: 8px 16px !important;
            }
            .stFileUploader {
                font-size: 14px !important;
            }
        </style>
            """, unsafe_allow_html=True)

# Define sidebar for model settings
st.sidebar.header("Model Settings", divider="gray")
embedding_model = st.sidebar.selectbox("Choose a Embedding Model:", ["nomic-embed-text", "nomic-embed-text-v1.5", "text-embedding-3-small"], index = 0)
llm_model = st.sidebar.selectbox("Choose a LLM Model:", ["gemma3:27b-it-q4_K_M", "gpt-4o-mini"], index = 1)
# Define sidebar for document upload
st.sidebar.header("My Documents", divider="gray")
pdf_docs = st.sidebar.file_uploader("*Upload your PDFs", accept_multiple_files=True)

# Creates a "Process" button in the sidebar and executes the following code when clicked
if st.sidebar.button("Process"):
    # If no PDFs are uploaded, displays a warning message asking the user to upload PDFs first
    if not pdf_docs:
        st.sidebar.warning("Please upload your PDFs first!")
    # If PDFs are uploaded, proceeds with processing --> subject to change!!!!
    else:
        with st.sidebar:
            sideSP_container = st.empty()
            with sideSP_container.container():
                with st.spinner("Processing the uploaded PDFs..."):
                    # raw_text = extract_pdf_text(pdf_docs)
                    # text_chunks = chunk_text(raw_text)
                    # embeddings = embed_text(text_chunks, embedding_model)
                    # vector_store = create_vector_store(embeddings)
                    # st.session_state.text_chunks = text_chunks
                    # st.session_state.vector_store = vector_store
                    
                    time.sleep(2)
                    # Set mock session state variables for demo
                    st.session_state.text_chunks = ["Mock text chunk 1", "Mock text chunk 2"]
                    st.session_state.vector_store = "Mock vector store"
                st.success("Processing complete!")
                time.sleep(2)
                sideSP_container.empty()


def main():
    # Make sure we have session state variables initialized
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.chat_history = []
    
    if "job_recommendations" not in st.session_state:
        st.session_state.job_recommendations = get_job_recommendations()
    
    # Get the show_job_panel value from session state
    show_job_panel = st.session_state.show_job_panel
    
    # If the user wants to see the job panel
    if show_job_panel:
        # Create a two-column layout
        cols = st.columns([7, 3])
        main_col = cols[0]
        job_col = cols[1]
        
        # Set up the layout for the main chatbot section
        main_col.markdown(
            f"""
            <div style='display: flex; flex-direction: column; align-items: center; text-align: center; margin-bottom: 20px;'>
                <div style='font-style: italic; font-weight: 900; display: flex; align-items: center; justify-content: center; flex-warp: warp; width: 100%;'>
                    <img src='https://github.com/YiwenC23/DSCI560-group_labs/raw/main/lab9/scripts/icon.png?raw=true' style='width: 45px; height: 45px;'>
                    <span style='font-size: 26px; margin-left: 10px;'>
                        Hi, I'm MiniChat
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    # If the user does not want to see the job panel
    else:
        # Use the full width
        main_col = st
        job_col = None
        
        # Set up the layout for the main chatbot section
        st.markdown(
            f"""
            <div style='display: flex; flex-direction: column; align-items: center; text-align: center; margin-bottom: 20px;'>
                <div style='font-style: italic; font-weight: 900; display: flex; align-items: center; justify-content: center; flex-warp: warp; width: 100%;'>
                    <img src='https://github.com/YiwenC23/DSCI560-group_labs/raw/main/lab9/scripts/icon.png?raw=true' style='width: 45px; height: 45px;'>
                    <span style='font-size: 26px; margin-left: 10px;'>
                        Hi, I'm MiniChat
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Add CSS to make only the job column scrollable
    st.markdown("""
        <style>
            /* Make only the job recommendation panel scrollable */
            [data-testid="column"][data-column-index="1"] {
                max-height: 85vh;
                overflow-y: auto;
                position: sticky;
                top: 0;
            }
            
            /* Prevent the main content from scrolling */
            [data-testid="column"][data-column-index="0"] {
                overflow-y: hidden;
            }
            
            /* Add a custom scrollbar for the job panel */
            [data-testid="column"][data-column-index="1"]::-webkit-scrollbar {
                width: 6px;
            }
            
            [data-testid="column"][data-column-index="1"]::-webkit-scrollbar-track {
                background: #f1f1f1;
                border-radius: 10px;
            }
            
            [data-testid="column"][data-column-index="1"]::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 10px;
            }
            
            [data-testid="column"][data-column-index="1"]::-webkit-scrollbar-thumb:hover {
                background: #555;
            }
        </style>
    """, unsafe_allow_html=True)

    # Create a container for chat history that will appear above the input
    chat_history_container = main_col.container()

    # Add CSS to ensure the input box is always at the bottom regardless of layout
    st.markdown("""
        <style>
            /* Make the main app container take full height */
            [data-testid="stAppViewContainer"] {
                height: 100vh;
            }
            
            /* Ensure content area fills available space */
            .main .block-container {
                display: flex;
                flex-direction: column;
                height: calc(100vh - 80px);
                overflow: hidden;
            }
            
            /* Fix chat input at the bottom with proper layout adaptation */
            .stChatInput {
                position: fixed !important;
                bottom: 20px !important;
                z-index: 1000 !important;
                background: white !important;
                padding: 10px !important;
            }
        
            /* When in full width mode (no job panel) */
            .stApp:not(:has([data-testid="column"][data-column-index="1"])) .stChatInput {
                width: 90% !important;
                max-width: 1200px !important;
            }
            
            /* When sidebar is expanded but job panel is hidden */
            .stApp:has(.stSidebar [data-testid="stSidebarContent"]):not(:has([data-testid="column"][data-column-index="1"])) .stChatInput {
                width: calc(90% - 260px) !important; /* Adjust the width to account for sidebar width */
                max-width: 900px !important;
            }
            
            /* Add padding to prevent content being hidden behind input */
            .block-container, [data-testid="column"] {
                padding-bottom: 70px !important;
            }
            
            /* Make chat history container scrollable */
            .stVerticalBlock {
                overflow-y: auto !important;
                max-height: calc(100vh - 200px) !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    
    # Show chat history in the main column
    with chat_history_container:
        messages = st.session_state.messages
        
        # Position the container near the bottom using CSS
        st.markdown("""
            <style>
                [data-testid="stVerticalBlock"] {
                    gap: 0px !important;
                }
            </style>
        """, unsafe_allow_html=True)
        
        # Display messages in reverse order (newest at the bottom)
        messages_to_show = messages[-6:] if len(messages) > 6 else messages
        
        for i, message in enumerate(messages_to_show):
            actual_index = messages.index(message)
            if message["role"] == "assistant":
                # Display assistant messages on the left
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(message["content"], unsafe_allow_html=True)
                    # Using "×" character for delete button
                    if st.button("×", key=f"delete_{actual_index}"):
                        if actual_index > 0 and messages[actual_index-1]["role"] == "user":
                            st.session_state.messages.pop(actual_index)
                            st.session_state.messages.pop(actual_index-1)
                            st.session_state.chat_history.pop(actual_index)
                            st.session_state.chat_history.pop(actual_index-1)
                        else:
                            st.session_state.messages.pop(actual_index)
                            st.session_state.chat_history.pop(actual_index)
                        st.rerun()
            else:
                # Display user messages on the right
                st.markdown(f"""
                            <div style='display: flex; justify-content: flex-end;'>
                                <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: #ddd; border-radius: 10px; color: black;'>
                                    {message['content']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
    
    # Add the chat input at the bottom within the main column to match its width
    prompt = main_col.chat_input(key="input", placeholder="Ask me anything...")
    
    # Process user input when submitted    
    if prompt:
        # Add the user message to session state
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # Process the user message and generate a response
        chat_context = system_prompt + st.session_state.chat_history
        
        if "vector_store" not in st.session_state:
            assistant_answer = "Please upload and process PDFs first!"
        else:
            assistant_answer = f"This is a mock response to your query: '{prompt}'"
            # In the real implementation, you would call your conversation_chain function:
            # assistant_answer = conversation_chain(
            #     prompt,
            #     chat_context,
            #     st.session_state.vector_store,
            #     embedding_model,
            #     llm_model
            # )
            
            # This would be where you dynamically update job recommendations
            # based on the user's message - simulating algorithm-based recommendations
            st.session_state.job_recommendations = get_job_recommendations()
        
        # Add the assistant response to session state
        st.session_state.messages.append({"role": "assistant", "content": assistant_answer})
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_answer})
        
        # Rerun to update the chat history
        st.rerun()
    
    # Job recommendations in the right column
    if show_job_panel and job_col is not None:
        job_col.markdown("<div class='job-panel-header'>📝 Job Recommendations</div>", unsafe_allow_html=True)
        
        # Use filtered_jobs to hold our recommendations
        filtered_jobs = st.session_state.job_recommendations
        
        # Add a note that these are context-based recommendations
        if len(st.session_state.messages) > 0:
            job_col.markdown("<div style='font-size: 14px; color: #666; margin-bottom: 15px;'>These job recommendations are based on your conversation.</div>", unsafe_allow_html=True)
        else:
            job_col.markdown("<div style='font-size: 14px; color: #666; margin-bottom: 15px;'>Start chatting to get personalized job recommendations.</div>", unsafe_allow_html=True)
        
        if not filtered_jobs:
            job_col.info("No matching jobs found.")
        
        # Sort jobs by match score
        filtered_jobs = sorted(filtered_jobs, key=lambda x: x['match_score'], reverse=True)
        
        # Display job cards
        for job in filtered_jobs:
            job_col.markdown(render_job_card(job), unsafe_allow_html=True)
            
        # Add a refresh button at the bottom of the recommendations
        job_col.markdown("""
            <div style="text-align: center; margin-top: 20px;">
                <button style="background-color: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; padding: 5px 10px; cursor: pointer; font-size: 12px;" 
                        onclick="window.location.reload();">
                    Refresh Recommendations
                </button>
            </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()