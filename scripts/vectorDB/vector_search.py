from pathlib import Path
from .vector_store import *
from collections import Counter
from qdrant_client import models


def process_resume(file, model_name: str="text-embedding-3-large"):
    resume = load_data(file)
    resume_content = resume[0].page_content
    resume_embeddings = get_embeddings(resume_content, model_name)
    return resume_content, resume_embeddings


def vector_search(embeddings: list[list[float]], collection: str = "ds_jobs", k: int = 100000):
    qdrant_client = init_vectorDB()
    
    result = qdrant_client.query_points_groups(
        collection_name = collection,
        query = embeddings[0],
        group_by = "jobkey",
        limit = k,
        with_payload = True,
        query_filter = models.Filter(should = [
            models.FieldCondition(
                key = "jobType",
                match = models.MatchValue(value="Full-time")
            )
        ])
    )
    
    job_scores = {}
    for group in result.groups:
        group_id = group.id
        if group_id not in job_scores:
            job_scores[group_id] = {}
        for point in group.hits:
            point_id = point.id
            score = point.score
            job_scores[group_id][point_id] = score
    
    ranked_pairs = []
    for jobKey in job_scores:
        scores = job_scores[jobKey]
        max_jobID = max(scores, key=scores.get)
        ranked_pairs.append((jobKey, max_jobID, scores[max_jobID]))
    
    ranked_pairs.sort(key=lambda x: x[2], reverse=True)
    ranked_jobIDs = [job_id for _, job_id, _ in ranked_pairs]
    
    top_jobs = qdrant_client.retrieve(
        collection_name = collection,
        ids = ranked_jobIDs,
    )
    
    return top_jobs


def format_job_results(top_jobs: list[PointStruct]):
    for i, job in enumerate(top_jobs[:10]):
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
    
    resume_embeddings = process_resume(resume_path, model_name)
    top_jobs = vector_search(resume_embeddings, collection)
    format_job_results(top_jobs)