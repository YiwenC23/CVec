import os
import sys
import pprint as pp

from pathlib import Path
from vector_store import *
from collections import Counter
from qdrant_client import models


def process_resume(path: str, model_name: str):
    resume = load_data(path)
    resume_embeddings = get_embeddings(resume[0].page_content, model_name)
    return resume_embeddings

def vector_search(embeddings: list[list[float]], collection: str = "ds_jobs", k: int = 10):
    qdrant_client = init_vectorDB()
    
    all_matches = []
    for embedding in embeddings:
        chunk_results = qdrant_client.query_points(
            collection_name = collection,
            query = embedding,
            query_filter = models.Filter(should = [
                models.FieldCondition(
                    key = "jobType",
                    match = models.MatchValue(value="Full-time")
                )
            ]),
            limit = k,
        )
        all_matches.extend(chunk_results)
    
    all_points = []
    for match in all_matches:
        all_points.extend(match[1])
    
    base_job_ids = []
    for point in all_points:
        point_id = point.id
        if "-" in point_id:
            parts = point_id.rsplit("-", 1)
            if parts[1].isdigit():
                base_job_ids.append(parts[0])
            else:
                base_job_ids.append(point_id)
        else:
            base_job_ids.append(point_id)
    
    job_counter = Counter(base_job_ids)
    top_jobIDs = [job_id for job_id, _ in job_counter.most_common(10)]
    
    top_jobs = qdrant_client.retrieve(
        collection_name = "ds_jobs",
        ids = top_jobIDs,
    )
    
    return top_jobs


def format_job_results(top_jobs: list[PointStruct]):
    for i, job in enumerate(top_jobs):
        print(f"Matched Job #{i+1}")
        print(f"Job Title: {job.payload.get('jobTitle', 'N/A')}")
        print(f"Company: {job.payload.get('companyName', 'N/A')}")
        print(f"Job Type: {job.payload.get('jobType', 'N/A')}")
        print(f"Job Link: {job.payload.get('jobLink', 'N/A')}")
        print(f"Job Description: \n {job.payload.get('jobDescription', 'N/A')[:1000]} \n ...")
        print("-" * 50)


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parents[2]
    
    resume_path = "/Users/yiwen/Desktop/resume_yiwen.pdf"
    model_name = "text-embedding-3-large"
    collection = "ds_jobs"
    k = 10
    
    resume_embeddings = process_resume(resume_path, model_name)
    top_jobs = vector_search(resume_embeddings, collection, k)
    format_job_results(top_jobs)