import os
import json
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


def load_api():
    apiKeys = ["OPENAI_API_KEY", "OLLAMA_API_KEY", "ANTHROPIC_API_KEY", 
            "HUGGINGFACE_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY"]
    for api in apiKeys:
        if not os.environ.get(api):
            os.environ[api] = getpass.getpass(f"Please enter your {api}: ")


def load_data(docs: list[str]) -> list[str]:
    """Return a list of the documents' text content"""
    text_list = []
    for doc in docs:
        if doc.endswith(".pdf"):
            text = ""
            loader = PyMuPDFLoader(doc, extract_tables=True)
            
            for page in loader.load():
                text += page.page_content
            text_list.append(text)
        
        elif doc.endswith(".json"):
            # TODO: If the document is a json file, apply Document Augmentation using llm
            text = ""
            loader = JSONLoader(doc)
            for item in loader.load():
                text += item.page_content
            text_list.append(text)
    
    return text_list


def chunk_text(text):
    chunker = TokenChunker(
        tokenizer = "character",
        chunk_size = 500,
        chunk_overlap = 100,
        return_type = "texts"
    )
    chunks = chunker.chunk(text)
    
    return chunks


def create_vectorStore(emb_model):
    #client = QdrantClient(":memory:")
    client = QdrantClient(url="http://localhost:6333")
    
    client.create_collection(
        collection_name="DS_jobs",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
    
    if emb_model == "text-embedding-3-large":
        vector_store = QdrantVectorStore(
            client=client,
            collection_name="DS_jobs",
            embedding_function=OpenAIEmbeddings(model="text-embedding-3-large"),
        )
    elif emb_model == "nomic-embed-text":
        vector_store = QdrantVectorStore(
            client=client,
            collection_name="DS_jobs",
            embedding_function=ollama.embed(model="nomic-embed-text"),
        )
    
    return vector_store