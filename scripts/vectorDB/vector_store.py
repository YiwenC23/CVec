import os
import getpass
import tiktoken
import tempfile
import multiprocessing as mp

from pathlib import Path
from openai import OpenAI
from functools import partial
from multiprocessing import Pool
from chonkie import SentenceChunker
from uuid import uuid4,uuid5, NAMESPACE_DNS
from langchain_community.llms import ollama
from langchain_community.document_loaders import *
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


MAX_TOKENS = 230
BATCH_SIZE = 100


def load_api(api: str):
    if not os.environ.get(api):
        os.environ[api] = getpass.getpass(f"Please enter your {api}: ")


def metadata_func(job, metadata):
    for i in [
        "companyName", "jobTitle", "jobkey", "jobLink", "jobType", "remoteWorkInfo",
        "locationInfo", "salaryInfo", "subtitle", "companyOverviewLink", "companyImages",
        "companyReviewLink", "companyReview", "highVolumeHiring", "urgentlyHiring"
    ]:
        metadata[i] = job.get(i)
    return metadata


def input_files(directory: str) -> list[str]:
    """Return a list of the documents' file paths"""
    file_paths = []
    for file in os.listdir(directory):
        if file.endswith(".pdf") or file.endswith(".json"):
            file_paths.append(os.path.join(directory, file))
    return file_paths


def load_data(file_input):
    """Return a list of the documents' text content"""
    docs = []
    
    #? Check if the files are inputted from local or from streamlit
    if isinstance(file_input, str) or isinstance(file_input, list):
        paths = [file_input] if not isinstance(file_input, list) else file_input
    
    else:
        file_name = file_input.name
        file_extension = file_name.split(".")[-1].lower()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_file:
            temp_file.write(file_input.getvalue())
            temp_path = temp_file.name
            paths = [temp_path]
    
    for path in paths:
        if path.endswith(".pdf"):
            loader = PyMuPDFLoader(
                file_path = path,
                extract_tables = False,
                mode = "page",
            )
            loaded_docs = loader.load()
            for doc in loaded_docs:
                doc.metadata["file_type"] = "pdf"
            docs.extend(loaded_docs)
        
        elif path.endswith(".json"):
            loader = JSONLoader(
                file_path = path,
                jq_schema = ".[]",
                content_key = "description",
                metadata_func = metadata_func,
            )
            loaded_docs = loader.load()
            for doc in loaded_docs:
                doc.metadata["file_type"] = "json"
            docs.extend(loaded_docs)
        
        elif path.endswith(".docx"):
            loader = Docx2txtLoader(
                file_path = path,
            )
            loaded_docs = loader.load()
            for doc in loaded_docs:
                doc.metadata["file_type"] = "docx"
            docs.extend(loaded_docs)
    
    #? Check if the temp file is still exists, clean up if it does
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    
    return docs


def chunk_text(text: str):
    chunker = SentenceChunker(
        tokenizer_or_token_counter = tiktoken.get_encoding("cl100k_base"),
        chunk_size = MAX_TOKENS,
        chunk_overlap = 128,
        min_sentences_per_chunk = 1,
        return_type = "texts",
    )
    chunks = chunker.chunk(text)
    
    return chunks


def num_tokens(text: str, model_name: str = "text-embedding-3-large") -> int:
    """Returns the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(text))
    return num_tokens


def get_embeddings(chunks: list[str], model_name: str):
    if model_name == "text-embedding-3-large":
        load_api("OPENAI_API_KEY")
        client = OpenAI()
        response = client.embeddings.create(
            input = chunks,
            model = "text-embedding-3-large",
        )
        embeddings = [i.embedding for i in response.data]
    
    elif model_name == "nomic-embed-text":
        response = ollama.embed(
            input = chunks,
            model = "nomic-embed-text",
        )
        embeddings = response.embeddings
    
    return embeddings


def init_vectorDB(collection: str = None):
    client = QdrantClient(url="http://localhost:6333")
    if collection is not None and collection not in client.get_collections():
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
        )
    return client


def process_doc(doc, model_name: str) -> list[PointStruct]:
    points = []
    file_type = doc.metadata.get("file_type")
    
    if file_type == "json":
        job_key = doc.metadata.get("jobkey")
        job_id = str(uuid5(NAMESPACE_DNS, job_key))
        
        text = doc.page_content
        payload = metadata_func(doc.metadata, {})
        payload["jobDescription"] = text
        
        if num_tokens(text, model_name) <= MAX_TOKENS:
            chunks = [text]
            ids = [job_id]
        
        else:
            chunks = chunk_text(text)
            ids = [
                str(uuid5(NAMESPACE_DNS, f"{job_key}-{i}"))
                for i in range(len(chunks))
            ]
    
    elif file_type == "pdf":
        doc_id = str(uuid4())
        text = doc.page_content
        payload = metadata_func(doc.metadata, {})
        
        chunks = chunk_text(text)
        ids = [doc_id]
    
    vectors = get_embeddings(chunks, model_name)
    for pid, vec in zip(ids, vectors):
        points.append(
            PointStruct(
                id = pid,
                vector = vec,
                payload = payload,
            )
        )
    
    return points


def parallel_upsert(paths, collection, model_name):
    docs = load_data(paths)
    
    with Pool(processes=mp.cpu_count()) as pool:
        results = pool.map(partial(process_doc, model_name=model_name), docs)
    flat_points = [point for points in results for point in points]
    
    qdrant_client = init_vectorDB(collection)
    for i in range(0, len(flat_points), BATCH_SIZE):
        batch = flat_points[i:i+BATCH_SIZE]
        qdrant_client.upsert(collection_name=collection, points=batch)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    
    BASE_DIR = Path(__file__).resolve().parents[2]
    data_dir = os.path.join(BASE_DIR, "data/processed_data/ds_jobs")
    paths = input_files(data_dir)
    
    model_name = "text-embedding-3-large"
    collection = "ds_jobs"
    
    parallel_upsert(paths, collection, model_name)