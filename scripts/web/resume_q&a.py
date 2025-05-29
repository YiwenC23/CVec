import os
import asyncio
import streamlit as st
# from openai import OpenAI
from web.agents import run_hr_agent


#* Define action button styles
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
            margin-top: -50px !important;              /* Adjust the margin-top to move the main block container up */
        }
        .stAPP > div:last-child {
            margin-bottom: -35px !important;           /* Adjust the margin-bottom to move the app container up */
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
    </style>
    """, unsafe_allow_html=True)


#* Spinner HTML
spinner_html = """
<div style="display:inline-flex; align-items:center; justify-content: center;">
    <div class="loader" style="margin-right:6px;"></div>
    <span style="font-size:0.85rem;color:#555;">thinking&nbsp;…</span>
    </div>
    <style>
    .loader{
        display: inline-block;
        border:4px solid #f3f3f3;
        border-top:4px solid #1E88E5;
        border-radius:50%;
        width:18px;height:18px;
        animation:spin 1s linear infinite;
    }
    @keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}
    </style>
"""


#* Clear chat history
def clear_chat_history():
    st.session_state.messages = []
    st.session_state.chat_history = []
    st.rerun()


#* Regenerate answer
def regenerate_answer():
    if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "assistant":
        st.session_state.messages.pop()
        st.session_state.chat_history.pop()
        st.rerun()


#* Delete conversation pair
def delete_conversation_pair(index):
    #? If index is -1, delete the last conversation pair
    if index == -1:
        st.session_state.messages = st.session_state.messages[:-2]
        st.session_state.chat_history = st.session_state.chat_history[:-2]
    else:
        #? Delete specific conversation pair
        st.session_state.messages = st.session_state.messages[:index-1] + st.session_state.messages[index+1:]
        st.session_state.chat_history = st.session_state.chat_history[:index-1] + st.session_state.chat_history[index+1:]
    st.rerun()

def main():
    slogan = "Hi, I'm CVec"
    image_url = "https://github.com/YiwenC23/DSCI560-group_labs/raw/main/lab9/scripts/icon.png?raw=true"
    st.markdown(
        f"""
        <div style='display: flex; flex-direction: column; align-items: center; text-align: center; margin: 0; padding: 0;'>
            <div style='font-style: italic; font-weight: 900; margin: 0; padding-top: 4px; display: flex; align-items: center; justify-content: center; flex-wrap: wrap; width: 100%;'>
                <img src={image_url} style='width: 45px; height: 45px;'>
                <span style='font-size: 26px; margin-left: 10px;'>
                    {slogan}
                </span>
            </div>
            <!-- 
            <span style='color: #bbb; font-style: italic; margin-top: 6px; margin-bottom: 10px;'>
                Embedding Model: "text-embedding-3-large"; LLM Model: "gpt-4o"
            </span>
            -->
        </div>
        """, unsafe_allow_html=True)
    
    #* Initialize session state of resume content and selected job
    resume_content = st.session_state["resume_content"] if "resume_content" in st.session_state else None
    selected_job = st.session_state["selected_job"] if "selected_job" in st.session_state else None
    
    if resume_content is None and selected_job is None:
        st.warning("Please upload your resume, and select a job first!")
    elif resume_content is None:
        st.warning("Please upload your resume first!")
    elif selected_job is None:
        st.warning("Please select a job first!")
    
    #* Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.chat_history = []
    
    #* Display chat history
    messages = st.session_state.messages
    for i, message in enumerate(messages):
        if message["role"] == "assistant":
            #? Display assistant messages on the left side of the screen and provide a action button to delete the message
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(f"""
                            <div style='display: flex; justify-content: flex-start;'>
                                <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: #ddd; border-radius: 10px; color: black;'>
                                    {message["content"]}
                                </div>
                            </div>
                """, unsafe_allow_html=True)
                
                if st.button("×", key=f"delete_{i}"):
                    delete_conversation_pair(i)
        
        else:
            #? Display user messages on the right side of the screen
            st.markdown(f"""
                        <div style='display: flex; justify-content: flex-end;'>
                            <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: white; border-radius: 10px; color: black;'>
                                {message['content']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
    
    #* Handle user input
    user_input = st.chat_input("Ask me anything about your resume and job recommendations!")
    if user_input:
        st.markdown(f"""
                    <div style='display: flex; justify-content: flex-end;'>
                        <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: gray; border-radius: 10px; color: white;'>
                            {user_input}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        with st.chat_message("assistant", avatar="🤖"):
            thinking_ph = st.empty()
            placeholder = st.empty()
            
            answer_parts = []
            
            agent_conversation = [{"role": "user", "content": f"Here is my resume: {resume_content}\n\nHere is the job description: {selected_job}\n\n"}] + st.session_state.chat_history
            agent_conversation.append({"role": "user", "content": user_input})
            async def stream_response():
                nonlocal thinking_ph
                thinking_ph.markdown(spinner_html, unsafe_allow_html=True)
                
                async for delta in run_hr_agent(agent_conversation):
                    if thinking_ph:
                        thinking_ph.empty()
                        thinking_ph = None
                    answer_parts.append(delta)
                    placeholder.markdown("".join(answer_parts), unsafe_allow_html=True)

            asyncio.run(stream_response())
            full_answer = "".join(answer_parts)
            
            st.session_state.messages.append({"role": "assistant", "content": full_answer})
            st.session_state.chat_history.append({"role": "assistant", "content": full_answer})
            
            with st.empty():
                if st.button("×", key=f"delete_{len(messages) - 1}"):
                    delete_conversation_pair(-1)


if __name__ == "__main__":
    #* Get OpenAI API Key
    with st.sidebar:
        if os.environ.get("OPENAI_API_KEY"):
            openai_api_key = st.text_input("OpenAI API Key", key="openai_api", type="password", value=os.environ.get("OPENAI_API_KEY"))
        else:
            openai_api_key = st.text_input("OpenAI API Key", key="openai_api", type="password")
    
    main()