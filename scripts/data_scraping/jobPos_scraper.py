import os
import re
import json
import math
import urllib
import asyncio

from pathlib import Path
from typing import Dict, List
from loguru import logger as log
from scrapfly import ScrapeApiResponse, ScrapeConfig, ScrapflyClient, ScrapflyScrapeError


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
    log.info(f"scraping search: {url}")
    result_first_page = await SCRAPFLY.async_scrape(ScrapeConfig(url, **BASE_CONFIG))
    data_first_page = parse_search_page(result_first_page)
    
    results = data_first_page["job_results"]
    total_results = sum(category["jobCount"] for category in data_first_page["search_meta"])
    
    if total_results > max_results:
        total_results = max_results
    print(f"scraping remaining {(total_results - 10) / 10} pages")
    
    other_pages = [
        ScrapeConfig(add_url_params(url, start=offset), **BASE_CONFIG)
        for offset in range(10, total_results + 10, 10)
    ]
    log.info(f"found total pages {math.ceil(total_results / 10)} search pages")
    
    async for result in SCRAPFLY.concurrent_scrape(other_pages):
        if not isinstance(result, ScrapflyScrapeError):
            data = parse_search_page(result)
            results.extend(data["job_results"])
        else:
            log.error(f"failed to scrape {result.api_response.config['url']}, got: {result.message}")
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
    """
    Scrape job details and return both successful results and failed job keys
    """
    log.info(f"scraping {len(job_keys)} job listings")
    successful_results = []
    failed_job_keys = []
    job_key_to_url = {}
    
    urls = []
    for job_key in job_keys:
        url = f"https://www.indeed.com/viewjob?jk={job_key}"
        urls.append(url)
        job_key_to_url[url] = job_key
    
    to_scrape = [ScrapeConfig(url, **BASE_CONFIG) for url in urls]
    
    async for result in SCRAPFLY.concurrent_scrape(to_scrape):
        job_detail = await parse_job_page(result)
        if job_detail:
            job_url = result.config["url"]
            job_key = job_key_to_url[job_url]
            job_detail["jobkey"] = job_key
            successful_results.append(job_detail)
        else:
            failed_url = result.config["url"]
            failed_job_key = job_key_to_url[failed_url]
            failed_job_keys.append(failed_job_key)
    
    return {
        "successful_results": successful_results,
        "failed_job_keys": failed_job_keys
    }


async def main():
    url = "https://www.indeed.com/jobs?q=Data+Science%2C+Data+Scientist%2C+Data+Engineer"
    search_results = await scrape_search(url, max_results=1000)
    
    with open(os.path.join(BASE_DIR, "data/processed_data/indeed_search_results.json"), "w", encoding="utf-8") as f:
        json.dump(search_results, f, indent=4, ensure_ascii=False)
    
    job_keys = [job["jobkey"] for job in search_results if "jobkey" in job]
    
    with open(os.path.join(BASE_DIR, "data/processed_data/indeed_jobKeys.json"), "w", encoding="utf-8") as f:
        json.dump(job_keys, f, indent=4, ensure_ascii=False)
    
    if job_keys:
        scrape_result = await scrape_jobs(job_keys)
        job_details = scrape_result["successful_results"]
        failed_keys = scrape_result["failed_job_keys"]
        
        if job_details:
            with open(os.path.join(BASE_DIR, "data/processed_data/indeed_job_details.json"), "w", encoding="utf-8") as f:
                json.dump(job_details, f, indent=4, ensure_ascii=False)
        
        if failed_keys:
            log.warning(f"Failed to scrape {len(failed_keys)} jobs. Saving for later retry.")
            with open(os.path.join(BASE_DIR, "data/processed_data/indeed_failed_jobKeys.json"), "w", encoding="utf-8") as f:
                json.dump(failed_keys, f, indent=4, ensure_ascii=False)
        
        job_details_dict = {
            detail.get("jobkey"): detail
            for detail in job_details
            if detail.get("jobkey")
        }
        
        for job in search_results:
            key = job.get("jobkey")
            if key and key in job_details_dict:
                job.update(job_details_dict[key])
    
    with open(os.path.join(BASE_DIR, "data/processed_data/indeed_jobs_final.json"), "w", encoding="utf-8") as f:
        json.dump(search_results, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parents[2]
    SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_API_KEY"])
    BASE_CONFIG = {
        "asp": True,
        "cost_budget": 1000,
        "country": "US",
        "render_js": True,
        "proxy_pool": "public_residential_pool",
        "debug": True,
    }
    
    asyncio.run(main())
