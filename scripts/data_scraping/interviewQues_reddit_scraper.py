"""
This script scrapes Reddit.com for subreddit data, posts, and comments.
It includes functionality to filter posts by keywords and save the results.

To run this scraper set env variable $SCRAPFLY_KEY with your scrapfly API key:
$ export $SCRAPFLY_KEY="your key from https://scrapfly.io/dashboard"
"""

import os
import json
import time
import asyncio
from typing import Dict, List, Union
from datetime import datetime
from pathlib import Path
from loguru import logger as log
from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

# Initialize ScrapflyClient with API key from environment variable
SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_KEY"])

# Base configuration for Scrapfly requests
BASE_CONFIG = {
    # enable the anti scraping protection
    "asp": True,
    # set the proxy country to US
    "country": "US",
    # bypassing reddit requires enabling JavaScript and using the residential proxy pool
    "render_js": True,
    "proxy_pool": "public_residential_pool",
    # Default values for caching and debugging
    "cache": True,
    "debug": True
}

# Create results directory if it doesn't exist
output = Path(os.path.dirname(os.path.abspath(__file__))) / "results"
output.mkdir(exist_ok=True)


######################## SCRAPING FUNCTIONS  ########################
async def scrape_subreddit(subreddit_id: str, max_pages: int = None) -> Dict:
    base_url = f"https://www.reddit.com/r/{subreddit_id}/"
    response = await SCRAPFLY.async_scrape(ScrapeConfig(base_url, **BASE_CONFIG))
    subreddit_data = {}
    data = parse_subreddit(response)
    subreddit_data["info"] = data["info"]
    subreddit_data["posts"] = data["post_data"]
    cursor = data["cursor"]

    def make_pagination_url(cursor_id: str):
        return f"https://www.reddit.com/svc/shreddit/community-more-posts/hot/?after={cursor_id}%3D%3D&t=DAY&name={subreddit_id}&feedLength=3"
        
    while cursor and (max_pages is None or max_pages > 0):
        url = make_pagination_url(cursor)
        response = await SCRAPFLY.async_scrape(ScrapeConfig(url, **BASE_CONFIG))
        data = parse_subreddit(response)
        cursor = data["cursor"]

        post_data = data["post_data"]
        subreddit_data["posts"].extend(post_data)
        if max_pages is not None:
            max_pages -= 1
    log.success(f"scraped {len(subreddit_data['posts'])} posts from the subreddit: r/{subreddit_id}")
    return subreddit_data


def parse_subreddit(response: ScrapeApiResponse) -> Dict:
    selector = response.selector
    url = response.context["url"]
    info = {}
    info["id"] = url.split("/r")[-1].replace("/", "")
    info["description"] = selector.xpath("//shreddit-subreddit-header/@description").get()
    members = selector.xpath("//shreddit-subreddit-header/@subscribers").get()
    rank = selector.xpath("//strong[@id='position']/text()").get()
    info["rank"] = rank.strip() if rank else None
    info["members"] = int(members) if members else None
    info["bookmarks"] = {}
    for item in selector.xpath("//div[faceplate-tracker[@source='community_menu']]/faceplate-tracker"):
        name = item.xpath(".//a/span/span/span/text()").get()
        link = item.xpath(".//a/@href").get()
        info["bookmarks"][name] = link

    info["url"] = url
    post_data = []
    for box in selector.xpath("//article"):
        link = box.xpath(".//a/@href").get()
        post_label = box.xpath(".//faceplate-tracker[@source='post']/a/span/div/text()").get()
        upvotes = box.xpath(".//shreddit-post/@score").get()
        comment_count = box.xpath(".//shreddit-post/@comment-count").get()
        attachment_type = box.xpath(".//shreddit-post/@post-type").get()
        if attachment_type and attachment_type == "image":
            attachment_link = box.xpath(".//div[contains(@class, 'img')]/*/@src").get()
        elif attachment_type == "video":
            attachment_link = box.xpath(".//shreddit-player/@preview").get()
        else:
            attachment_link = None
            
        # Ensure the link is a fully qualified URL that can be directly used by scrape_post
        post_link = link
        if post_link and not post_link.startswith("http"):
            if post_link.startswith("/"):
                post_link = "https://www.reddit.com" + post_link
            else:
                post_link = "https://www.reddit.com/" + post_link
                
        post_data.append({         
            "title": box.xpath("./@aria-label").get(),
            "link": post_link,  # Use the processed link
            "postId": box.xpath(".//shreddit-post/@id").get(),
            "postLabel": post_label.strip() if post_label else None,
            "postUpvotes": int(upvotes) if upvotes else None,
            "commentCount": int(comment_count) if comment_count else None,
            "attachmentType": attachment_type,
            "attachmentLink": attachment_link,
        })
    # id for the next posts batch
    cursor_id = selector.xpath("//shreddit-post/@more-posts-cursor").get()
    return {"post_data": post_data, "info": info, "cursor": cursor_id}


def parse_post_info(response: ScrapeApiResponse) -> Dict:
    selector = response.selector
    info = {}
    label = selector.xpath("//faceplate-tracker[@source='post']/a/span/div/text()").get()
    comments = selector.xpath("//shreddit-post/@comment-count").get()
    upvotes = selector.xpath("//shreddit-post/@score").get()
    info["authorId"] = selector.xpath("//shreddit-post/@author-id").get()
    info["author"] = selector.xpath("//shreddit-post/@author").get()
    info["authorProfile"] = "https://www.reddit.com/user/" + info["author"] if info["author"] else None
    info["subreddit"] = selector.xpath("//shreddit-post/@subreddit-prefixed-name").get().replace("r/", "")
    info["postId"] = selector.xpath("//shreddit-post/@id").get()
    info["postLabel"] = label.strip() if label else None
    info["publishingDate"] = selector.xpath("//shreddit-post/@created-timestamp").get()
    info["postTitle"] = selector.xpath("//shreddit-post/@post-title").get()
    info["postLink"] = selector.xpath("//shreddit-canonical-url-updater/@value").get()
    info["commentCount"] = int(comments) if comments else None
    info["upvoteCount"] = int(upvotes) if upvotes else None
    info["attachmentType"] = selector.xpath("//shreddit-post/@post-type").get()
    info["attachmentLink"] = selector.xpath("//shreddit-post/@content-href").get()
    return info


def parse_post_comments(response: ScrapeApiResponse) -> List[Dict]:
    def parse_comment(parent_selector) -> Dict:
        """parse a comment object"""
        author = parent_selector.xpath("./@data-author").get()
        link = parent_selector.xpath("./@data-permalink").get()
        dislikes = parent_selector.xpath(".//span[contains(@class, 'dislikes')]/@title").get()
        upvotes = parent_selector.xpath(".//span[contains(@class, 'likes')]/@title").get()
        downvotes = parent_selector.xpath(".//span[contains(@class, 'unvoted')]/@title").get()        
        return {
            "authorId": parent_selector.xpath("./@data-author-fullname").get(),
            "author": author,
            "authorProfile": "https://www.reddit.com/user/" + author if author else None,
            "commentId": parent_selector.xpath("./@data-fullname").get(),
            "link": "https://www.reddit.com" + link if link else None,
            "publishingDate": parent_selector.xpath(".//time/@datetime").get(),
            "commentBody": parent_selector.xpath(".//div[@class='md']/p/text()").get(),
            "upvotes": int(upvotes) if upvotes else None,
            "dislikes": int(dislikes) if dislikes else None,
            "downvotes": int(downvotes) if downvotes else None,            
        }

    def parse_replies(what) -> List[Dict]:
        """recursively parse replies"""
        replies = []
        for reply_box in what.xpath(".//div[@data-type='comment']"):
            reply_comment = parse_comment(reply_box)
            child_replies = parse_replies(reply_box)
            if child_replies:
                reply_comment["replies"] = child_replies
            replies.append(reply_comment)
        return replies

    selector = response.selector
    data = []
    for item in selector.xpath("//div[@class='sitetable nestedlisting']/div[@data-type='comment']"):
        comment_data = parse_comment(item)
        replies = parse_replies(item)
        if replies:
            comment_data["replies"] = replies
        data.append(comment_data)            
    return data


async def scrape_post(url: str, sort: Union["old", "new", "top"]) -> Dict:
    response = await SCRAPFLY.async_scrape(ScrapeConfig(url, **BASE_CONFIG))
    post_data = {}
    post_data["info"] = parse_post_info(response)
    
    # Handle case where postLink is None
    post_link = post_data["info"].get("postLink")
    if post_link is None:
        # If postLink is None, use the original URL for comment scraping
        # Make sure it's in the old.reddit.com format
        if "old.reddit.com" not in url:
            bulk_comments_page_url = url.replace("www.reddit.com", "old.reddit.com") + f"?sort={sort}&limit=500"
        else:
            bulk_comments_page_url = url + f"?sort={sort}&limit=500"
    else:
        # Use the postLink as originally intended
        bulk_comments_page_url = post_link.replace("www", "old") + f"?sort={sort}&limit=500"
    
    try:
        response = await SCRAPFLY.async_scrape(ScrapeConfig(bulk_comments_page_url, **BASE_CONFIG))
        post_data["comments"] = parse_post_comments(response)
        log.success(f"scraped {len(post_data['comments'])} comments from the post {url}")
    except Exception as e:
        log.error(f"Failed to scrape comments for {url}: {str(e)}")
        post_data["comments"] = []
    
    return post_data


######################## POST FILTERING UTILITY ########################
def filter_posts_by_keywords(posts, keywords, search_fields=None, match_all=False):
    if search_fields is None:
        search_fields = ['title']
    
    # Convert keywords to lowercase for case-insensitive matching
    keywords_lower = [k.lower() for k in keywords]
    
    filtered_posts = []
    for post in posts:
        # Combine all specified fields into a single text for searching
        combined_text = " ".join([str(post.get(field, "")).lower() for field in search_fields if post.get(field)])
        
        if match_all:
            # All keywords must be present
            if all(keyword in combined_text for keyword in keywords_lower):
                filtered_posts.append(post)
        else:
            # Any keyword will match
            if any(keyword in combined_text for keyword in keywords_lower):
                filtered_posts.append(post)
    
    return filtered_posts


######################## MAIN EXECUTION LOGIC ########################

async def run(subreddit_id="datascience", keywords=None, search_fields=None, match_all=False, max_pages=None):
    # Set default values if not provided
    if keywords is None:
        keywords = ["interview", "prepare"]
    if search_fields is None:
        search_fields = ["title"]
    
    filtering_description = f"posts containing {' ALL of ' if match_all else ' ANY of '} these keywords: {', '.join(keywords)}"
    print(f"Running Reddit scraper, filtering for {filtering_description}")
    print(f"Searching in fields: {', '.join(search_fields)}")
    print("Saving results to ./results directory")
    
    # 1. First scrape the subreddit
    print(f"Scraping subreddit: r/{subreddit_id} with {'no page limit' if max_pages is None else f'max {max_pages} pages'}")
    subreddit_data = await scrape_subreddit(
        subreddit_id=subreddit_id,
        max_pages=max_pages
    )
    
    # 2. Filter posts that contain the specified keywords
    filtered_posts = filter_posts_by_keywords(
        posts=subreddit_data["posts"],
        keywords=keywords,
        search_fields=search_fields,
        match_all=match_all
    )
    
    print(f"Found {len(filtered_posts)} posts matching the criteria out of {len(subreddit_data['posts'])} total posts")
    
    # Create a filtered subreddit data object
    filtered_subreddit_data = {
        "info": subreddit_data["info"],
        "posts": filtered_posts
    }
    
    # Create a descriptive filename
    keyword_str = "-".join(keywords)
    match_type = "all" if match_all else "any"
    fields_str = "-".join(search_fields)
    filtered_filename = f"{subreddit_id}_filtered_{match_type}_{keyword_str}_in_{fields_str}.json"
    
    # Save the filtered subreddit data
    with open(output.joinpath(filtered_filename), "w", encoding="utf-8") as file:
        json.dump(filtered_subreddit_data, file, indent=2, ensure_ascii=False)
    
    # 3. Extract post links from the filtered subreddit data
    post_links = [post["link"] for post in filtered_posts if post["link"] is not None]
    print(f"Found {len(post_links)} valid links to scrape")
    
    # 4. Scrape ALL filtered posts
    all_post_data = []
    for i, post_link in enumerate(post_links):
        try:
            print(f"Scraping post {i+1}/{len(post_links)}: {post_link}")
            post_data = await scrape_post(
                url=post_link,
                sort="top",
            )
            all_post_data.append(post_data)
            
            # Extract a safe filename from the post ID or URL
            if post_data["info"].get("postId"):
                post_id = post_data["info"]["postId"]
            else:
                # Create a safe filename from the URL if postId is not available
                post_id = post_link.split("/")[-2] if len(post_link.split("/")) >= 3 else f"post_{i}"
            
            # Save individual post data 
            post_filename = f"{subreddit_id}_{keyword_str}_post_{post_id}.json"
            with open(output.joinpath(post_filename), "w", encoding="utf-8") as file:
                json.dump(post_data, file, indent=2, ensure_ascii=False)
                
            # Add a small delay between requests to avoid rate limiting
            if i < len(post_links) - 1:  # Don't delay after the last request
                time.sleep(1)  # 1 second delay
                
        except Exception as e:
            log.error(f"Failed to scrape post {post_link}: {str(e)}")
            # Continue with the next post instead of stopping the entire process
    
    # 5. Save all post data to a single file
    all_posts_filename = f"{subreddit_id}_{keyword_str}_all_posts.json"
    with open(output.joinpath(all_posts_filename), "w", encoding="utf-8") as file:
        json.dump(all_post_data, file, indent=2, ensure_ascii=False)
    
    print(f"Completed scraping {len(all_post_data)} posts out of {len(post_links)} attempted")


if __name__ == "__main__":
    # You can modify these parameters to customize the scraping
    asyncio.run(run(
        subreddit_id="datascience",  # Subreddit to scrape
        keywords=["interview", "prepare"],  # Keywords to filter posts
        search_fields=["title"],  # Fields to search for keywords
        match_all=False,  # Whether all keywords must be present (True) or any (False)
        max_pages=None  # Maximum number of pages to scrape (None for no limit)
    ))