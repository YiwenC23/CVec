import os
import json

from pathlib import Path
from bs4 import BeautifulSoup


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
                
                company_images = {
                    "headerImageUrl": None,
                    "logoUrl": None,
                }
                if job_detail.get("companyImagesModel"):
                    if job_detail["companyImagesModel"].get("headerImageUrl"):
                        company_images["headerImageUrl"] = job_detail["companyImagesModel"]["headerImageUrl"]
                    if job_detail["companyImagesModel"].get("logoUrl"):
                        company_images["logoUrl"] = job_detail["companyImagesModel"]["logoUrl"]
                
                company_review = {
                    "desktopCompanyLink": None,
                    "reviewCount": None,
                    "rating": None,
                }
                if job_detail.get("companyReviewModel"):
                    if job_detail["companyReviewModel"].get("desktopCompanyLink"):
                        company_review["desktopCompanyLink"] = job_detail["companyReviewModel"]["desktopCompanyLink"]
                    if job_detail["companyReviewModel"].get("ratingsModel"):
                        if job_detail["companyReviewModel"]["ratingsModel"].get("count"):
                            company_review["reviewCount"] = job_detail["companyReviewModel"]["ratingsModel"]["count"]
                        if job_detail["companyReviewModel"]["ratingsModel"].get("rating"):
                            company_review["rating"] = job_detail["companyReviewModel"]["ratingsModel"]["rating"]
                
                salaryInfo = {
                    "currency": None,
                    "text": None,
                    "min": None,
                    "max": None,
                    "type": None,
                }
                if job_search.get("extractedSalary"):
                    if job_search["extractedSalary"].get("min"):
                        salaryInfo["min"] = job_search["extractedSalary"]["min"]
                    if job_search["extractedSalary"].get("max"):
                        salaryInfo["max"] = job_search["extractedSalary"]["max"]
                    if job_search["extractedSalary"].get("type"):
                        salaryInfo["type"] = job_search["extractedSalary"]["type"]
                elif job_search.get("salarySnippet"):
                    if job_search["salarySnippet"].get("currency"):
                        salaryInfo["currency"] = job_search["salarySnippet"]["currency"]
                    if job_search["salarySnippet"].get("text"):
                        salaryInfo["text"] = job_search["salarySnippet"]["text"]
                
                remoteWorkModel = {
                    "text": None,
                    "type": None,
                }
                if job_search.get("remoteWorkModel"):
                    if job_search["remoteWorkModel"].get("text"):
                        remoteWorkModel["text"] = job_search["remoteWorkModel"]["text"]
                    if job_search["remoteWorkModel"].get("type"):
                        remoteWorkModel["type"] = job_search["remoteWorkModel"]["type"]
                
                description = BeautifulSoup(job_detail.get("description"), "html.parser").get_text().lstrip("\n")
                
                ds_jobs.append({
                    "companyName": job_detail.get("companyName"),
                    "jobTitle": job_detail.get("jobTitle"),
                    "jobKey": i_key,
                    "jobLink": "https://www.indeed.com/viewjob?jk=" + i_key,
                    "jobType": job_detail.get("jobType"),
                    "remoteWorkInfo": remoteWorkModel,
                    "locationInfo": {
                        "jobLocationCity": job_search.get("jobLocationCity"),
                        "jobLocationState": job_search.get("jobLocationState"),
                        "formattedLocation": job_detail.get("formattedLocation"),
                    },
                    "salaryInfo": salaryInfo,
                    "description": description,
                    "subtitle": job_detail.get("subtitle"),
                    "companyOverviewLink": job_detail.get("companyOverviewLink"),
                    "companyImages": company_images,
                    "companyReviewLink": job_detail.get("companyReviewLink"),
                    "companyReview": company_review,
                    "highVolumeHiring": job_search.get("highVolumeHiring"),
                    "urgentlyHiring": job_search.get("urgentlyHiring"),
                })
    
    ds_jobs.sort(key=lambda r: r["jobKey"])
    
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