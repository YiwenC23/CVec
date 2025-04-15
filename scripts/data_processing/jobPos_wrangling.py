import os
import json

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
    
    job_searches = {}
    for job in total_search_results:
        job_key = job["jobkey"]
        job_searches[job_key] = job
    
    job_details = {}
    for job in jobDetails:
        job_key = job["jobkey"]
        job_details[job_key] = job
    
    return job_searches, job_details


def main():
    job_searches, job_details = load_data()
    
    ds_jobs = []
    for i_key in job_searches.keys():
        for j_key in job_details.keys():
            if i_key == j_key:
                job_detail = job_details[j_key]
                job_search = job_searches[i_key]
                
                company_images = job_detail.get("companyImagesModel") if job_detail.get("companyImagesModel") else {}
                company_review = job_detail.get("companyReviewModel") if job_detail.get("companyReviewModel") else {}
                ratings_model = company_review.get("ratingsModel") if company_review.get("ratingsModel") else {}
                
                ds_jobs.append({
                    "companyName": job_detail.get("companyName"),
                    "jobTitle": job_detail.get("jobTitle"),
                    "jobkey": i_key,
                    "jobLink": "https://www.indeed.com/viewjob?jk=" + i_key,
                    "jobType": job_detail.get("jobType"),
                    "remoteWorkModel": job_search.get("remoteWorkModel"),
                    "jobLocationCity": job_search.get("jobLocationCity"),
                    "jobLocationState": job_search.get("jobLocationState"),
                    "formattedLocation": job_detail.get("formattedLocation"),
                    "salarySnippet": job_search.get("salarySnippet"),
                    "description": job_detail.get("description"),
                    "subtitle": job_detail.get("subtitle"),
                    "companyOverviewLink": job_detail.get("companyOverviewLink"),
                    "companyImagesModel": {
                        "headerImageUrl": company_images.get("headerImageUrl"),
                        "logoUrl": company_images.get("logoUrl"),
                    },
                    "companyReviewLink": job_detail.get("companyReviewLink"),
                    "companyReviewModel": {
                        "desktopCompanyLink": company_review.get("desktopCompanyLink"),
                        "ratingsModel": {
                            "count": ratings_model.get("count"),
                            "rating": ratings_model.get("rating"),
                        },
                    },
                    "highVolumeHiringModel": job_search.get("highVolumeHiringModel"),
                    "urgentlyHiring": job_search.get("urgentlyHiring"),
                })
    
    ds_jobs.sort(key=lambda r: r["jobkey"])
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ds_jobs, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parents[2]
    jobDetails_file = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_jobs_detail.json")
    searchResults_file1 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds_search_results.json")
    searchResults_file2 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds2_search_results.json")
    searchResults_file3 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds3_search_results.json")
    searchResults_file4 = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_ds4_search_results.json")
    
    output_file = os.path.join(BASE_DIR, "data/processed_data/ds_jobs.json")
    
    main()