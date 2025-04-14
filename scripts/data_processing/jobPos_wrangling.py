import os
import json
import cerberus

from pathlib import Path


def load_json_file(file_path: str) -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_data():
    jobDetails = load_json_file(jobDetails_file)
    searchResults_1 = load_json_file(searchResults_file1)
    searchResults_2 = load_json_file(searchResults_file2)
    searchResults_3 = load_json_file(searchResults_file3)
    searchResults_4 = load_json_file(searchResults_file4)
    
    total_search_results = searchResults_1 + searchResults_2 + searchResults_3 + searchResults_4
    
    job_searchs = {}
    for job in total_search_results:
        job_key = job["jobkey"]
        job_searchs[job_key] = job
    
    job_details = {}
    for job in jobDetails:
        job_key = job["jobkey"]
        job_details[job_key] = job
    
    return job_searchs, job_details


def main():
    job_searchs, job_details = load_data()
    
    ds_jobs = {
        "jobkey": {"type": "string", "required": True},
        "company": {"type": "string", "required": True},
        "companyBrandingAttributes": {
            "type": dict,
            "schema": {
                "headerImageUrl": {"type": "string", "nullable": True},
                "logoUrl": {"type": "string", "nullable": True}
            }
        },
        "companyScore": {
            "type": "dict",
            "nullable": True,
            "schema": {
                "companyRating": {"type": "float", "nullable": True},
                "companyReviewCount": {"type": "integer", "nullable": True},
                "companyReviewLink": {"type": "string", "nullable": True}
            }
        },
    }
    
    for i_key in job_searchs.keys():
        for j_key in job_details.keys():
            if i_key == j_key:
                ds_jobs[i_key] = {
                    "jobkey": i_key,
                }


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parents[2]
    jobDetails_file = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_jobs_detail.json")
    searchResults_file1 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds_search_results.json")
    searchResults_file2 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds2_search_results.json")
    searchResults_file3 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds3_search_results.json")
    searchResults_file4 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds4_search_results.json")
    
    main()