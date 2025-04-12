#!/usr/bin/env python3
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import urljoin
from webdriver_manager.chrome import ChromeDriverManager

def scrape_kaggle_search(url, min_upvotes=20, max_pages=30):
    # Configure Chrome options
    options = Options()
    options.add_argument("--headless") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # Initialize the browser
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    all_results = []
    current_page = 1
    
    try:
        # Load the initial page
        print(f"Loading URL: {url}")
        driver.get(url)
        
        # Wait for initial content to load
        print("Waiting for page to load...")
        time.sleep(5)
        
        while current_page <= max_pages:
            print(f"Processing page {current_page}...")
            
            # Wait for list items to appear
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.MuiListItem-root"))
                )
                print("List items loaded successfully")
            except Exception as e:
                print(f"Timeout waiting for list items: {e}")
                break
            
            # Scroll down to load all results on current page
            print("Scrolling to load all results on current page...")
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while scroll_attempts < max_scroll_attempts:
                # Scroll down to bottom
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Wait to load page
                time.sleep(2)
                
                # Calculate new scroll height and compare with last scroll height
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    # Try one more scroll to be sure
                    scroll_attempts += 1
                else:
                    # Reset if the height changed
                    scroll_attempts = 0
                    last_height = new_height
            
            # Get the fully rendered HTML
            html = driver.page_source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find list items
            list_items = soup.select('li.MuiListItem-root.MuiListItem-gutters.MuiListItem-divider')
            if not list_items:
                # Fallback selectors
                list_items = soup.select('li.MuiListItem-root') or soup.select('li[aria-label*="List Item"]')
            
            print(f"Found {len(list_items)} list items on page {current_page}")
            
            # Process items on current page
            page_results = []
            for item in list_items:
                try:
                    # Find the specific anchor tag that contains the discussion link
                    link_elem = item.select_one('a[href*="/discussions/"]')
                    if not link_elem:
                        continue
                    
                    # Get the link
                    link = link_elem['href']
                    if not link.startswith('http'):
                        link = urljoin("https://www.kaggle.com", link)
                    
                    # Skip if we've already processed this link
                    if any(r['link'] == link for r in all_results):
                        continue
                    
                    # Get the correct title from the anchor tag's aria-label 
                    title = link_elem.get('aria-label', '').strip()
                    
                    # If title is empty, try getting it from the text content
                    if not title:
                        title = link_elem.get_text().strip()
                    
                    # Extract upvotes
                    upvotes = 0
                    
                    # Method 1: Look for span with aria-label containing "votes"
                    vote_spans = item.select('span[aria-label*="votes"]')
                    if vote_spans:
                        for span in vote_spans:
                            vote_text = span.get_text().strip()
                            try:
                                upvotes = int(vote_text)
                                break
                            except ValueError:
                                # Handle cases like "1.2k"
                                if 'k' in vote_text.lower():
                                    try:
                                        upvotes = int(float(vote_text.lower().replace('k', '')) * 1000)
                                        break
                                    except ValueError:
                                        pass
                    
                    # Method 2: Look for direct upvote number in the aria-label attribute
                    if upvotes == 0:
                        for span in item.select('span[aria-label]'):
                            aria_label = span.get('aria-label', '')
                            if 'votes' in aria_label:
                                # Extract number from something like "45 votes"
                                match = re.search(r'(\d+)\s+votes', aria_label)
                                if match:
                                    upvotes = int(match.group(1))
                                    break
                    
                    # Method 3: Look for button with data-testid="upvotebutton__upvote"
                    if upvotes == 0:
                        upvote_button = item.select_one('[data-testid="upvotebutton__upvote"]')
                        if upvote_button:
                            # Check the next sibling span which might contain the vote count
                            vote_span = upvote_button.find_next('span')
                            if vote_span:
                                vote_text = vote_span.get_text().strip()
                                try:
                                    upvotes = int(vote_text)
                                except ValueError:
                                    pass
                    
                    # Fallback methods from previous versions
                    if upvotes == 0:
                        # Look for any span that might contain just a number
                        for span in item.select('span'):
                            text = span.get_text().strip()
                            if text.isdigit():
                                upvotes = int(text)
                                break
                    
                    # Determine the type based on the URL
                    result_type = "discussion" if "/discussions/" in link else "unknown"
                    
                    # Extract discussion ID from the URL
                    discussion_id = None
                    match = re.search(r'/discussions/[^/]+/(\d+)', link)
                    if match:
                        discussion_id = match.group(1)
                    
                    page_results.append({
                        'title': title,
                        'link': link,
                        'upvotes': upvotes,
                        'type': result_type,
                        'id': discussion_id,
                        'page': current_page
                    })
                    
                except Exception as e:
                    print(f"Error parsing item: {e}")
            
            print(f"Extracted {len(page_results)} discussion links from page {current_page}")
            all_results.extend(page_results)
            
            # Stop if we've reached the last page
            if current_page >= max_pages:
                print(f"Reached maximum number of pages ({max_pages})")
                break
                
            # Try multiple methods to find and click the pagination controls
            print("Looking for pagination controls...")
            
            # Method 1: Use CSS selector for pagination
            pagination_found = False
            try:
                # Find all pagination buttons
                pagination_buttons = driver.find_elements(By.CSS_SELECTOR, "nav[aria-label='pagination navigation'] button")
                print(f"Found {len(pagination_buttons)} pagination buttons")
                
                # Look for the "Next" button
                for button in pagination_buttons:
                    try:
                        aria_label = button.get_attribute("aria-label")
                        if aria_label and "next" in aria_label.lower():
                            print("Found 'Next' button with aria-label")
                            if button.is_enabled():
                                print("Clicking 'Next' button...")
                                driver.execute_script("arguments[0].scrollIntoView(true);", button)
                                time.sleep(1)
                                button.click()
                                pagination_found = True
                                current_page += 1
                                time.sleep(5)  # Wait for next page to load
                                break
                            else:
                                print("'Next' button is disabled")
                                break
                    except Exception as e:
                        print(f"Error checking pagination button: {e}")
            
            except Exception as e:
                print(f"Error with pagination method 1: {e}")
            
            # Method 2: Try direct page number buttons if Method 1 failed
            if not pagination_found:
                try:
                    # Look for button with next page number
                    next_page_button = driver.find_element(By.XPATH, f"//button[text()='{current_page + 1}']")
                    print(f"Found button for page {current_page + 1}")
                    driver.execute_script("arguments[0].scrollIntoView(true);", next_page_button)
                    time.sleep(1)
                    next_page_button.click()
                    pagination_found = True
                    current_page += 1
                    time.sleep(5)  # Wait for next page to load
                except Exception as e:
                    print(f"Error with pagination method 2: {e}")
            
            # Method 3: Try finding the "Next" text button
            if not pagination_found:
                try:
                    next_button = driver.find_element(By.XPATH, "//button[.//span[text()='Next']]")
                    print("Found 'Next' text button")
                    driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    time.sleep(1)
                    next_button.click()
                    pagination_found = True
                    current_page += 1
                    time.sleep(5)  # Wait for next page to load
                except Exception as e:
                    print(f"Error with pagination method 3: {e}")
            
            # Method 4: Last resort - look for any button that might contain "Next"
            if not pagination_found:
                try:
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for button in buttons:
                        button_text = button.text.lower()
                        if "next" in button_text:
                            print(f"Found 'Next' in button text: '{button_text}'")
                            driver.execute_script("arguments[0].scrollIntoView(true);", button)
                            time.sleep(1)
                            button.click()
                            pagination_found = True
                            current_page += 1
                            time.sleep(5)  # Wait for next page to load
                            break
                except Exception as e:
                    print(f"Error with pagination method 4: {e}")
            
            # If we couldn't find pagination, stop
            if not pagination_found:
                print("Couldn't find pagination controls, stopping")
                break
        
        # Filter by upvotes and sort
        filtered = [r for r in all_results if r['upvotes'] > min_upvotes]
        sorted_results = sorted(filtered, key=lambda x: x['upvotes'], reverse=True)
        
        print(f"Total results collected: {len(all_results)}")
        print(f"Results with more than {min_upvotes} upvotes: {len(filtered)}")
        
        return sorted_results
        
    except Exception as e:
        print(f"Error: {e}")
        return []
    finally:
        # Close the browser
        driver.quit()
        print("Browser closed")

if __name__ == "__main__":
    search_url = "https://www.kaggle.com/search?q=data+science+interview+questions"
    results = scrape_kaggle_search(search_url, min_upvotes=20, max_pages=5)
    
    # Print results
    print(f"\nFound {len(results)} results with >20 upvotes:")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']} - {result['upvotes']} upvotes")
        print(f"   Link: {result['link']}")
        print()
    
    # Save to CSV
    if results:
        pd.DataFrame(results).to_csv('kaggle_results.csv', index=False)
        print(f"Saved {len(results)} results to kaggle_results.csv")