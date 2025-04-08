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


async def scrape_search(url: str, max_results: int = 1000) -> List[Dict]:
    log.info(f"scraping search: {url}")
    result_first_page = await SCRAPFLY.async_scrape(ScrapeConfig(url, **BASE_CONFIG))
    data_first_page = parse_search_page(result_first_page)
    
    results = data_first_page["job_results"]
    total_results = sum(category["jobCount"] for category in data_first_page["search_meta"])
    
    #* there's a page limit on indeed.com of 1000 results per search
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


def parse_job_page(response: ScrapeApiResponse):
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


async def scrape_jobs(job_keys: List[str]):
    """
    Scrape job details (hidden data) from job page using job_key elements
    """
    log.info(f"scraping {len(job_keys)} job listings")
    results = []
    urls = [
        f"https://www.indeed.com/viewjob?jk={job_key}" 
        for job_key in job_keys
    ]
    to_scrape = [ScrapeConfig(url, **BASE_CONFIG) for url in urls]
    async for result in SCRAPFLY.concurrent_scrape(to_scrape):
        results.append(parse_job_page(result))
    return results


async def main():
    url = "https://www.indeed.com/jobs?q=Data+Science&l=Los+Angeles%2C+CA"
    search_results = await scrape_search(url, max_results=100)
    
    job_keys = [job["jobkey"] for job in search_results if "jobkey" in job]
    if job_keys:
        job_details = await scrape_jobs(job_keys)
        
        job_details_dict = {
            detail.get("jobkey"): detail
            for detail in job_details
            if detail.get("jobkey")
        }
    
    for job in search_results:
        key = job.get("jobkey")
        if key and key in job_details_dict:
            job.update(job_details_dict[key])
    
    with open(os.path.join(BASE_DIR, "data/processed_data/indeed_search_results2.json"), "w", encoding="utf-8") as f:
        json.dump(search_results, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parents[2]
    SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_API_KEY"])
    BASE_CONFIG = {
        "asp": True,
        "country": "US",
        "render_js": True,
        "proxy_pool": "public_residential_pool",
    }
    
    asyncio.run(main())
