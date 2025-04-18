import os
import getpass
import tiktoken
import multiprocessing as mp

from pathlib import Path
from openai import OpenAI
from functools import partial
from multiprocessing import Pool
from chonkie import SentenceChunker
from uuid import uuid5, NAMESPACE_DNS
from langchain_community.llms import ollama
from langchain_community.document_loaders import *
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


MAX_TOKENS = 512
BATCH_SIZE = 100


# def load_api():
#     for api in [
#         "OPENAI_API_KEY", "OLLAMA_API_KEY", "ANTHROPIC_API_KEY", 
#         "HUGGINGFACE_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY"
#     ]:
#         if not os.environ.get(api):
#             os.environ[api] = getpass.getpass(f"Please enter your {api}: ")


if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API Key: ")


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


def load_data(paths: list[str]):
    """Return a list of the documents' text content"""
    docs = []
    for path in paths:
        if path.endswith(".pdf"):
            loader = PyMuPDFLoader(
                file_path = path,
                extract_tables = True,
                mode = "page",
            )
            docs.extend(loader.load())
        
        elif path.endswith(".json"):
            loader = JSONLoader(
                file_path = path,
                jq_schema = ".[]",
                content_key = "description",
                metadata_func = metadata_func,
            )
            docs.extend(loader.load())
    
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
    client = OpenAI()
    if model_name == "text-embedding-3-large":
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


def conn_vectorDB(collection: str):
    client = QdrantClient(url="http://localhost:6333", headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0"})
    if collection not in client.get_collections():
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
        )
    return client


def process_doc(doc, model_name: str) -> list[PointStruct]:
    points = []
    
    job_key = doc.metadata.get("jobkey")
    job_id = str(uuid5(NAMESPACE_DNS, job_key))
    
    text = doc.page_content
    payload = metadata_func(doc.metadata, {})
    
    if num_tokens(text, model_name) <= MAX_TOKENS:
        chunks = [text]
        ids = [job_id]
    
    else:
        chunks = chunk_text(text)
        ids = [
            str(uuid5(NAMESPACE_DNS, f"{job_key}-{i}"))
            for i in range(len(chunks))
        ]
    
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
    
    client = conn_vectorDB(collection)
    for i in range(0, len(flat_points), BATCH_SIZE):
        batch = flat_points[i:i+BATCH_SIZE]
        client.upsert(collection_name=collection, points=batch)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    
    BASE_DIR = Path(__file__).resolve().parents[2]
    data_dir = os.path.join(BASE_DIR, "data/processed_data")
    paths = input_files(data_dir)
    
    model_name = "text-embedding-3-large"
    collection = "ds_jobs_parallel"
    
    parallel_upsert(paths, collection, model_name)