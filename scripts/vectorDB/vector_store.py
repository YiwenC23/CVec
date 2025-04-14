import os
import torch
import faiss
import ollama
import getpass
import numpy as np
from openai import OpenAI
from PyPDF2 import PdfReader
from chonkie import TokenChunker
from chonkie.embeddings import SentenceTransformerEmbeddings

torch.classes.__path__ = []

#* Get the API key from the environment variable, ask for input if not found
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API Key: ")
client = OpenAI()


def extract_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    
    return text


def chunk_text(text):
    chunker = TokenChunker(
        tokenizer = "character",
        chunk_size = 500,
        chunk_overlap = 100,
        return_type = "texts"
    )
    chunks = chunker.chunk(text)
    
    return chunks


def embed_text(text_chunks, emb_model):
    if emb_model == "text-embedding-3-small":
        response = client.embeddings.create(
            input = text_chunks,
            model = emb_model
        )
        embeddings = [item.embedding for item in response.data]
    elif emb_model == "nomic-embed-text":
        response = ollama.embed(
            model = emb_model,
            input = text_chunks
        )
        embeddings = response.embeddings
    elif emb_model == "nomic-embed-text-v1.5":
        model = SentenceTransformerEmbeddings("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
        embeddings = model.embed(text_chunks)
    else:
        raise ValueError(f"Model {emb_model} not supported")
    
    return embeddings


def create_vector_store(embeddings):
    embeddings_array = np.array(embeddings).astype("float32")
    vector_dim = embeddings_array.shape[1]
    vector_store = faiss.IndexFlatL2(vector_dim)
    vector_store.add(embeddings_array)
    
    return vector_store