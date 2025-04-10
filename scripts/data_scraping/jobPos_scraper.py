import os
import re
import json
import math
import urllib
import asyncio

from scrapfly import *
from pathlib import Path
from typing import Dict, List
from loguru import logger as log
from requests.exceptions import ReadTimeout

def parse_search_page(response):
    html = re.findall(r"window.mosaic.providerData\[['\"]mosaic-provider-jobcards['\"]\]=(\{.+?\});", response.content)
    html = json.loads(html[0])
    job_dict = {
        "job_results": html["metaData"]["mosaicProviderJobCardsModel"]["results"],
            "search_meta": html["metaData"]["mosaicProviderJobCardsModel"]["tierSummaries"],
        }
    return job_dict


def add_url_params(url, **kwargs):
    url_parts = list(urllib.parse.urlparse(url))
    query = dict(urllib.parse.parse_qsl(url_parts[4]))
    query.update(kwargs)
    url_parts[4] = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(url_parts)


#* There's a page limit on indeed.com of 1000 results per search
async def scrape_search(url: str, max_results: int = 1000) -> List[Dict]:
    log.info(f"Scraping search: {url}")
    result_first_page = await SCRAPFLY.async_scrape(ScrapeConfig(url, **BASE_CONFIG))
    data_first_page = parse_search_page(result_first_page)
    
    results = data_first_page["job_results"]
    total_results = sum(category["jobCount"] for category in data_first_page["search_meta"])
    
    if total_results > max_results:
        total_results = max_results
    log.info(f"Scraping remaining {(total_results - 10) / 10} pages...")
    
    other_pages = [
        ScrapeConfig(add_url_params(url, start=offset), **BASE_CONFIG)
        for offset in range(10, total_results + 10, 10)
    ]
    log.info(f"Found total {math.ceil(total_results / 10)} pages.")
    
    async for result in SCRAPFLY.concurrent_scrape(other_pages):
        if not isinstance(result, SCRAPFLY_ERRORS):
            data = parse_search_page(result)
            results.extend(data["job_results"])
            jobKeys = [job["jobkey"] for job in results]
            log.info(f"Scraped {len(jobKeys)} job positions.")
        else:
            log.error(f"Failed to scrape {result.api_response.config['url']}, got: {result.message}")
            await asyncio.sleep(10)
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
    log.info(f"Scraping {len(job_keys)} job positions...")
    job_key_to_url = {}
    
    if os.path.exists(JOB_DETAILS_FILE):
        with open(JOB_DETAILS_FILE, "r") as f:
            jobDetail_scraped = json.load(f)
            jobKey_scraped = [job["jobkey"] for job in jobDetail_scraped]
            jobKeys_left = [key for key in job_keys if key not in jobKey_scraped]
        job_keys = jobKeys_left
        log.info(f"Scraped jobs: {len(jobDetail_scraped)}; Remaining jobs: {len(jobKeys_left)}")
    else:
        jobDetail_scraped = []
    
    urls = []
    for job_key in job_keys:
        url = f"https://www.indeed.com/viewjob?jk={job_key}"
        urls.append(url)
        job_key_to_url[url] = job_key
    
    to_scrape = [ScrapeConfig(url, **BASE_CONFIG) for url in urls]
    
    async for result in SCRAPFLY.concurrent_scrape(to_scrape):
        if not isinstance(result, SCRAPFLY_ERRORS):
            job_detail = await parse_job_page(result)
            
            if job_detail:
                job_url = result.config["url"]
                job_key = job_key_to_url[job_url]
                job_detail["jobkey"] = job_key
                job_detail.sort(key=lambda r: r["jobkey"])
                jobDetail_scraped.append(job_detail)
                remaining_jobs = len(job_keys) - len(jobDetail_scraped)
                
                with open(JOB_DETAILS_FILE, "w", encoding="utf-8") as f:
                    json.dump(jobDetail_scraped, f, indent=4, ensure_ascii=False)
                
                log.info(f"Scraped jobs: {len(jobDetail_scraped)}; Remaining jobs: {remaining_jobs}")
        else:
            log.error(f"Failed to scrape {result.api_response.config['url']}, got: {result.message}")
            await asyncio.sleep(10)
    
    log.info(f"Successfully scraped {len(jobDetail_scraped)/len(job_keys)} job positions!")
    return jobDetail_scraped


async def main():
    if not os.path.exists(SEARCH_RESULTS_FILE):
        url = "https://www.indeed.com/jobs?q=Data%20Science"
        # url = "https://www.indeed.com/jobs?q=Data%20Scientist"
        # url = "https://www.indeed.com/jobs?q=Data%20Engineer"
        # url = "https://www.indeed.com/jobs?q=Data%20Analyst"
        search_results = await scrape_search(url)
        
        with open(SEARCH_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(search_results, f, indent=4, ensure_ascii=False)
        
        jobKey_list = [job["jobkey"] for job in search_results if "jobkey" in job]
        job_keys = [key for key in jobKey_list if jobKey_list.count(key) == 1]
        
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


if __name__ == "__main__":
    #* File path constants
    BASE_DIR = Path(__file__).resolve().parents[2]
    JOB_KEYS_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_jobKeys.json")
    SEARCH_RESULTS_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_data_science_results.json")
    JOB_DETAILS_FILE = os.path.join(BASE_DIR, "data/raw_data/data_science/indeed_data_science_jobs_detail.json")
    
    #* Scrapfly setup
    SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_API_KEY"], DEFAULT_READ_TIMEOUT=150)
    BASE_CONFIG = {
        "asp": True,
        "cost_budget": 1000,
        "country": "US",
        "render_js": True,
        "retry": True,
        "proxy_pool": "public_residential_pool",
    }
    SCRAPFLY_ERRORS = (
        ScrapflyScrapeError,
        ScrapflyAspError,
        ApiHttpServerError,
        HttpError,
        UpstreamHttpError,
        UpstreamHttpClientError,
        UpstreamHttpServerError,
        ScrapflyProxyError,
        ScrapflyScheduleError,
        ScrapflySessionError,
        ScrapflyThrottleError,
        ErrorFactory,
        ApiHttpClientError,
        ApiHttpServerError,
        EncoderError,
        ReadTimeout,
    )
    
    asyncio.run(main())
