import os
import re
import json
import math
import urllib

from typing import Dict, List
from loguru import logger as log
from scrapfly import ScrapeApiResponse, ScrapeConfig, ScrapflyClient, ScrapflyScrapeError


def parse_search_page(result):
    """
    Find hidden web data of search results in Indeed.com search page HTML.
    """
    data = re.findall(r'window.mosaic.providerData\["mosaic-provider-jobcards"\]=(\{.+?\});', result.content)
    data = json.loads(data[0])
    search_page = {
        "results": data["metaData"]["mosaicProviderJobCards"]["results"],
        "meta": data["metaData"]["mosaicProviderJobCardsModel"]["tierSummaries"],
    }
    return search_page


def get_job_positions(client: ScrapflyClient, url: str) -> str:
    r = client.scrape(ScrapeConfig(url=url, **BASE_CONFIG))
    return r


def main():
    url_indeed = "https://www.indeed.com/jobs?q=data%20science&l="
    get_job_positions(SCRAPFLY, url_indeed)


if __name__ == "__main__":
    SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_API_KEY"])
    BASE_CONFIG = {
        "asp": True,
        "country": "US",
    }
    
    main()

