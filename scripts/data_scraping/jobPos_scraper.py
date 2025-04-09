import os
import re
import json
import math
import urllib
import asyncio
import pprint as pp

from pathlib import Path
from typing import Dict, List
from loguru import logger as log
from scrapfly import ScrapeApiResponse, ScrapeConfig, ScrapflyClient, ScrapflyScrapeError


def parse_search_page(response):
    try:
        html = re.findall(r"window.mosaic.providerData\[['\"]mosaic-provider-jobcards['\"]\]=(\{.+?\});", response.content)
        html = json.loads(html[0])
        job_dict = {
            "job_results": html["metaData"]["mosaicProviderJobCardsModel"]["results"],
                "search_meta": html["metaData"]["mosaicProviderJobCardsModel"]["tierSummaries"],
            }
        return job_dict
    except Exception as e:
        log.error(f"Failed to parse {response.config['url']}: {e}")
        return None


def add_url_params(url, **kwargs):
    url_parts = list(urllib.parse.urlparse(url))
    query = dict(urllib.parse.parse_qsl(url_parts[4]))
    query.update(kwargs)
    url_parts[4] = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(url_parts)


#* There's a page limit on indeed.com of 1000 results per search
async def scrape_search(url: str, max_results: int = 1000) -> List[Dict]:
    log.info(f"scraping search: {url}")
    result_first_page = await SCRAPFLY.async_scrape(ScrapeConfig(url, **BASE_CONFIG))
    data_first_page = parse_search_page(result_first_page)
    
    results = data_first_page["job_results"]
    total_results = sum(category["jobCount"] for category in data_first_page["search_meta"])
    
    if total_results > max_results:
        total_results = max_results
    print(f"Scraping remaining {(total_results - 10) / 10} pages...")
    
    other_pages = [
        ScrapeConfig(add_url_params(url, start=offset), **BASE_CONFIG)
        for offset in range(10, total_results + 10, 10)
    ]
    log.info(f"found total {math.ceil(total_results / 10)} pages")
    
    async for result in SCRAPFLY.concurrent_scrape(other_pages):
        if not isinstance(result, ScrapflyScrapeError):
            data = parse_search_page(result)
            results.extend(data["job_results"])
        else:
            log.error(f"Failed to scrape {result.api_response.config['url']}, got: {result.message}")
    return results


async def parse_job_page(response: ScrapeApiResponse):
    try:
        data = re.findall(r"_initialData=(\{.+?\});", response.content)
        data = json.loads(data[0])
        data = data["jobInfoWrapperModel"]["jobInfoModel"]
        job_details = {
            "description": data["sanitizedJobDescription"],
            **data["jobMetadataHeaderModel"],
            **(data["jobTagModel"] or {}),
            **data["jobInfoHeaderModel"],
        }
        return job_details
    except Exception as e:
        log.error(f"Failed to parse {response.config['url']}: {e}")
        return None


async def scrape_jobs(job_keys: List[str]):
    log.info(f"Scraping {len(job_keys)} job listings")
    jobDetail_results = []
    jobKeys_left = []
    job_key_to_url = {}
    
    if os.path.exists(JOB_DETAILS_FILE):
        with open(JOB_DETAILS_FILE, "r") as f:
            jobDetail_scraped = json.load(f)
            jobKey_scraped = [job["jobkey"] for job in jobDetail_scraped]
            jobKeys_left = [job for job in job_keys if job not in jobKey_scraped]
        job_keys = jobKeys_left
    
    urls = []
    for job_key in job_keys:
        url = f"https://www.indeed.com/viewjob?jk={job_key}"
        urls.append(url)
        job_key_to_url[url] = job_key
    
    to_scrape = [ScrapeConfig(url, **BASE_CONFIG) for url in urls]
    
    async for result in SCRAPFLY.concurrent_scrape(to_scrape):
        if result.result.get("result").get("success") == True:
            job_detail = await parse_job_page(result)
            
            if job_detail:
                job_url = result.config["url"]
                job_key = job_key_to_url[job_url]
                job_detail["jobkey"] = job_key
                jobDetail_results.append(job_detail)
                
                with open(JOB_DETAILS_FILE, "w", encoding="utf-8") as f:
                    json.dump(jobDetail_results, f, indent=4, ensure_ascii=False)
        
    log.info(f"Scraped {len(jobDetail_results)/len(job_keys)} job details successfully")
    return jobDetail_results


async def main():
    if not os.path.exists(SEARCH_RESULTS_FILE):
        url = "https://www.indeed.com/jobs?q=Data%20Science"
        search_results = await scrape_search(url)
        
        with open(SEARCH_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(search_results, f, indent=4, ensure_ascii=False)
        
        job_keys = [job["jobkey"] for job in search_results if "jobkey" in job]
            
        with open(JOB_KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(job_keys, f, indent=4, ensure_ascii=False)
    else:
        with open(JOB_KEYS_FILE, "r", encoding="utf-8") as f:
            job_keys = json.load(f)
        
        with open(SEARCH_RESULTS_FILE, "r", encoding="utf-8") as f:
            search_results = json.load(f)
    
    if job_keys:
        jobDetail_results = await scrape_jobs(job_keys)
        
        job_details_dict = {
            detail.get("jobkey"): detail
            for detail in jobDetail_results
            if detail.get("jobkey")
        }
        
        for job in search_results:
            key = job.get("jobkey")
            if key and key in job_details_dict:
                job.update(job_details_dict[key])
        
    with open(JOBS_FINAL_FILE, "w", encoding="utf-8") as f:
        json.dump(search_results, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    #* File path constants
    BASE_DIR = Path(__file__).resolve().parents[2]
    JOB_KEYS_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_jobKeys.json")
    SEARCH_RESULTS_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_search_results.json")
    JOB_DETAILS_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_job_details.json")
    FAILED_JOB_KEYS_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_failed_jobKeys.json")
    JOBS_FINAL_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_jobs_final.json")
    
    SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_API_KEY"])
    BASE_CONFIG = {
        "asp": True,
        "cost_budget": 1000,
        "country": "US",
        "render_js": True,
        "rendering_wait": 2000,
        "proxy_pool": "public_residential_pool",
    }
    
    asyncio.run(main())
