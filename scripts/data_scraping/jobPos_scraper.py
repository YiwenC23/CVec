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
    html = html[0]
    html = json.loads(html)
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
    # there's a page limit on indeed.com of 1000 results per search
    if total_results > max_results:
        total_results = max_results

    print(f"scraping remaining {(total_results - 10) / 10} pages")
    other_pages = [
        ScrapeConfig(add_url_params(url, start=offset), **BASE_CONFIG)
        for offset in range(10, total_results + 10, 10)
    ]
    log.info("found total pages {} search pages", math.ceil(total_results / 10))
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
    return {
        "description": data['sanitizedJobDescription'],
        **data["jobMetadataHeaderModel"],
        **(data["jobTagModel"] or {}),
        **data["jobInfoHeaderModel"],
    }


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
    url = "https://www.indeed.com/jobs?q=Data+Scientist&l=Los+Angeles%2C+CA"
    search_results = await scrape_search(url, max_results=100)
    
    with open(os.path.join(BASE_DIR, "data/processed_data/indeed_search_results.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(search_results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parents[2]
    SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_API_KEY"])
    BASE_CONFIG = {
        "asp": True,
        "country": "US",
    }
    
    asyncio.run(main())

