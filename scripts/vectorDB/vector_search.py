from typing import List
from pathlib import Path
from loguru import logger
from .vector_store import *
from qdrant_client import models


qdrant_client = init_vectorDB()


def process_resume(file, model_name: str="text-embedding-3-large"):
    resume = load_data(file)
    resume_content = resume[0].page_content
    resume_embeddings = get_embeddings(resume_content, model_name)
    return resume_content, resume_embeddings


def search_filter(filter_dict: dict):
    key_map = {
        "filter_job_type": "jobType",
        "filter_state": "locationInfo.jobLocationState",
        "filter_city": "locationInfo.jobLocationCity",
    }
    
    query_filter = models.Filter(must = [])
    for key, value in filter_dict.items():
        if key == "filter_city" and value == "Bay Area":
            value = "San Francisco Bay Area"
        if value is not None:
            search_key = key_map.get(key)
            if search_key:
                query_filter.must.append(
                    models.FieldCondition(
                        key = search_key,
                        match = models.MatchValue(value=value)
                    )
                )
    
    return query_filter

def vector_search(embeddings: list[list[float]], filter_dict: dict, collection: str = "ds_jobs", k: int = 300):
    try:
        result = qdrant_client.query_points_groups(
            collection_name = collection,
            query = embeddings[0],
            group_by = "jobkey",
            limit = k,
            query_filter = search_filter(filter_dict),
            with_payload = True,
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

    except Exception as e:
        logger.error(f"Error: {e}")


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
    
    resume_embeddings = process_resume(resume_path)
    top_jobs = vector_search(resume_embeddings)
    format_job_results(top_jobs)