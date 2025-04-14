import os
import sys
import time
import ollama
import numpy as np
import pandas as pd
import streamlit as st

from vectorDB import VectorDB
from vector_store import (
    extract_pdf_text,
    chunk_text,
    embed_text,
    create_vector_store,
    client
)

# BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# DB_DIR = os.path.join(BASE_PATH, "data/VectorDB")

# def connect_vectorDB():
#     embedding_dim = 745
#     index_file = os.path.join(DB_DIR, "index.faiss")
#     mapping_file = os.path.join(DB_DIR, "mapping.json")
    
#     if os.path.exists(index_file) and os.path.exists(mapping_file):
#         db = VectorDB.load(DB_DIR, embedding_dim)
#         print("\nSuccessfully connected to the VectorDB.")
#         return db
#     else:
#         db = VectorDB(embedding_dim)
#         print("\nThe VectorDB has been successfully initialized.")
#         return db

# vector_db = connect_vectorDB()

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
st.set_page_config(page_title="MiniChat", page_icon=":robot_face:", initial_sidebar_state="expanded")


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


def init_chat_history():
    if "messages" in st.session_state:
        for i, message in enumerate(st.session_state.messages):
            if message["role"] == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(message["content"], unsafe_allow_html=True)
                    
                    #? Add action button below the message content
                    if st.button("🗑", key=f"delete_{i}"):
                            st.session_state.messages.pop(i)
                            st.session_state.messages.pop(i - 1)
                            st.session_state.chat_history.pop(i)
                            st.session_state.chat_history.pop(i - 1)
                            st.rerun()
            else:
                st.markdown(f"""
                            <div style='display: flex; justify-content: flex-end;'>
                                <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: #ddd; border-radius: 10px; color: black;'>
                                    {message['content']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
    else:
        st.session_state.messages = []
        st.session_state.chat_history = []
    
    return st.session_state.messages


#* Define the sidebar components
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


st.sidebar.header("Model Settings", divider="gray")
embedding_model = st.sidebar.selectbox("Choose a Embedding Model:", ["nomic-embed-text", "nomic-embed-text-v1.5", "text-embedding-3-small"], index = 0)
llm_model = st.sidebar.selectbox("Choose a LLM Model:", ["gemma3:27b-it-q4_K_M", "gpt-4o-mini"], index = 1)

# st.sidebar.divider()

st.sidebar.header("My Documents", divider="gray")
pdf_docs = st.sidebar.file_uploader("*Upload your PDFs", accept_multiple_files=True)

if st.sidebar.button("Process"):
    if not pdf_docs:
        st.sidebar.warning("Please upload your PDFs first!")
    else:
        with st.sidebar:
            sideSP_container = st.empty()
            with sideSP_container.container():
                with st.spinner("Processing the uploaded PDFs..."):
                    raw_text = extract_pdf_text(pdf_docs)
                    text_chunks = chunk_text(raw_text)
                    embeddings = embed_text(text_chunks, embedding_model)
                    vector_store = create_vector_store(embeddings)
                    st.session_state.text_chunks = text_chunks
                    st.session_state.vector_store = vector_store
                st.success("Processing complete!")
                time.sleep(2)
                sideSP_container.empty()


slogan = "Hi, I'm MiniChat"
image_url = "https://github.com/YiwenC23/DSCI560-group_labs/raw/main/lab9/scripts/icon.png?raw=true"
st.markdown(
    f"""
    <div style='display: flex; flex-direction: column; align-items: center; text-align: center; margin: 0; padding: 0;'>
        <div style='font-style: italic; font-weight: 900; margin: 0; padding-top: 4px; display: flex; align-items: center; justify-content: center; flex-warp: warp; width: 100%;'>
            <img src='{image_url}' style='width: 45px; height: 45px;'>
            <span style='font-size: 26px; margin-left: 10px;'>
                {slogan}
            </span>
        </div>
        <!-- 
        <span style='color: #bbb; font-style: italic; margin-top: 6px; margin-bottom: 10px;'>
            Embedding Model: {embedding_model}; LLM Model: {llm_model}
        </span>
        -->
    </div>
    """, unsafe_allow_html=True)


def conversation_chain(query, chat_context, vector_store, embedding_model, llm_model):
    query_embedding = embed_text([query], embedding_model)[0]
    query_embedding_array = np.array([query_embedding]).astype("float32")
    
    _, indices = vector_store.search(query_embedding_array, k=4)
    context_chunks = "\n".join([st.session_state.text_chunks[i] for i in indices[0]])
    prompt = f"{chat_context}\nContext: {context_chunks}\nUser: {query}\nBot:"
    
    if llm_model == "gpt-4o-mini":
        response = client.chat.completions.create(
            model = llm_model,
            messages = [
                {"role": "system", "content": "You are a helpful assistant that can answer questions about the context provided."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.choices[0].message.content.strip()
    elif llm_model == "gemma3:27b-it-q4_K_M":
        response = ollama.chat(
            model = llm_model,
            messages = [
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.message.content.strip()
    return answer


def main():
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.chat_history = []
    
    messages = st.session_state.messages
    
    for i, message in enumerate(messages):
        if message["role"] == "assistant":
            #? Display assistant messages on the left side of the screen and provide a action button to delete the message
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(message["content"], unsafe_allow_html=True)
                if st.button("×", key=f"delete_{i}"):
                    st.session_state.messages = st.session_state.messages[:i - 1]
                    st.session_state.chat_history = st.session_state.chat_history[:i - 1]
                    st.rerun()
        else:
            st.markdown(f"""
                        <div style='display: flex; justify-content: flex-end;'>
                            <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: #ddd; border-radius: 10px; color: black;'>
                                {message['content']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
    
    prompt = st.chat_input(key="input", placeholder="Ask me anything...")
    
    if prompt:
        st.markdown(f"""
                    <div style='display: flex; justify-content: flex-end;'>
                        <div style='display: inline-block; margin: 10px 0; padding: 8px 12px 8px 12px; background-color: gray; border-radius: 10px; color: white;'>
                            {prompt}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        messages.append({"role": "user", "content": prompt})
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        #? Process the user message and display the assistant message
        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            
            chat_context = system_prompt + st.session_state.chat_history
            
            if "vector_store" not in st.session_state:
                assistant_answer = "Please upload and process PDFs first!"
            else:
                assistant_answer = conversation_chain(
                    prompt,
                    chat_context,
                    st.session_state.vector_store,
                    embedding_model,
                    llm_model
                )
            
            placeholder.markdown(assistant_answer, unsafe_allow_html=True)
            
            messages.append({"role": "assistant", "content": assistant_answer})
            st.session_state.chat_history.append({"role": "assistant", "content": assistant_answer})
            
            with st.empty():
                if st.button("×", key=f"delete_{len(messages) - 1}"):
                    st.session_state.messages = st.session_state.messages[:-2]
                    st.session_state.chat_history = st.session_state.chat_history[:-2]
                    st.rerun()


if __name__ == "__main__":
    main()