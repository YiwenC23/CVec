import os
import getpass
import numpy as np

from uuid import uuid4
from PyPDF2 import PdfReader
from chonkie import TokenChunker
from chonkie.embeddings import SentenceTransformerEmbeddings
from langchain_community.llms import ollama
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import *
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance


#* Function for loading a list of APIs from the environment
def load_api():
    apiKeys = ["OPENAI_API_KEY", "OLLAMA_API_KEY", "ANTHROPIC_API_KEY", 
            "HUGGINGFACE_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY"]
    for api in apiKeys:
        if not os.environ.get(api):
            os.environ[api] = getpass.getpass(f"Please enter your {api}: ")


#* Function for loading data
def load_data(docs):
    text = ""
    for doc in docs:
        if doc.endswith(".pdf"):
            loader = PyMuPDFLoader(doc)
            for page in loader.load():
                text += page.page_content
        elif doc.endswith(".json"):
            loader = JSONLoader(doc)
            for item in loader.load():
                text += item.page_content
    return text


#* Function for chunking text
def chunk_text(text):
    chunker = TokenChunker(
        tokenizer = "character",
        chunk_size = 500,
        chunk_overlap = 100,
        return_type = "texts"
    )
    chunks = chunker.chunk(text)
    
    return chunks


#* Function that defines the vector store of the Qdrant Database
def create_vectorStore(emb_model):
    #client = QdrantClient(":memory:")
    client = QdrantClient(url="http://localhost:6333")
    
    client.create_collection(
        collection_name="job_collection",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
    
    if emb_model == "text-embedding-3-large":
        vector_store = QdrantVectorStore(
            client=client,
            collection_name="job_collection",
            embedding_function=OpenAIEmbeddings(model="text-embedding-3-large"),
        )
    elif emb_model == "nomic-embed-text":
        vector_store = QdrantVectorStore(
            client=client,
            collection_name="job_collection",
            embedding_function=ollama.embed(model="nomic-embed-text"),
        )
    
    return vector_store