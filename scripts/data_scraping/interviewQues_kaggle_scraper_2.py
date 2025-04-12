#!/usr/bin/env python3
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
from webdriver_manager.chrome import ChromeDriverManager
import os

def parse_discussion_content(links_csv, output_json):
    # Configure Chrome options
    options = Options()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # Initialize the browser
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Load the CSV with links
    try:
        # Use the full path or relative path from the script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        links_csv_path = os.path.join(script_dir, links_csv)
        
        # Read the CSV file manually since we're removing pandas dependency
        import csv
        links = []
        with open(links_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                links.append(row)
        
        print(f"Loaded {len(links)} links from {links_csv_path}")
    except Exception as e:
        print(f"Error loading CSV: {e}")
        driver.quit()
        return
    
    # Create a list to store the parsed content
    all_discussions = []
    
    try:
        # Process each link
        for index, row in enumerate(links):
            try:
                link = row['link']
                title = row['title']
                
                print(f"Processing {index+1}/{len(links)}: {title}")
                
                # Load the discussion page
                driver.get(link)
                print(f"  Loading URL: {link}")
                
                # Wait for content to load
                time.sleep(5)
                
                # Wait for the main content to appear
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".sc-bqEkgP.carXiy"))
                    )
                    print("  Content loaded successfully")
                except Exception as e:
                    print(f"  Timeout waiting for content: {e}")
                
                # Get the page source after it's fully loaded
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract title from the specified class
                page_title = title
                title_elem = soup.select_one(".sc-Rjrgp.bQ0hBK.sc-itBlat.dhGHCm")
                if title_elem:
                    page_title = title_elem.get_text(strip=True)
                
                # Extract the main post content from the specified class
                main_content = ""
                content_items = []
                
                # Find the main content container with the specified class
                main_content_elem = soup.select_one(".sc-bqEkgP.carXiy")
                
                if main_content_elem:
                    # Get the full text content
                    main_content = main_content_elem.get_text(separator="\n", strip=True)
                    
                    # Extract only the specified tags
                    valid_tags = main_content_elem.find_all(['h1', 'h2', 'h3', 'p', 'a', 'ol', 'ul', 'li', 'code', 'span'])
                    
                    # Filter out nested elements to avoid duplication
                    top_level_elements = []
                    for tag in valid_tags:
                        # Check if any parent of this tag is also in valid_tags
                        parent_in_list = False
                        for parent in tag.parents:
                            if parent in valid_tags:
                                parent_in_list = True
                                break
                        
                        if not parent_in_list:
                            top_level_elements.append(tag)
                    
                    # Process each element sequentially
                    for elem in top_level_elements:
                        element_text = ""
                        element_type = elem.name
                        
                        if elem.name in ['h1', 'h2', 'h3']:
                            element_text = elem.get_text(strip=True)
                        elif elem.name == 'a' and elem.has_attr('href'):
                            # Handle links
                            link_text = elem.get_text(strip=True)
                            href = elem['href']
                            element_text = f"{link_text} [Link: {href}]"
                        elif elem.name in ['ol', 'ul']:
                            # Handle lists
                            list_items = []
                            for li in elem.find_all('li', recursive=True):
                                list_items.append(f"• {li.get_text(strip=True)}")
                            element_text = "\n".join(list_items)
                        elif elem.name in ['code', 'span']:
                            # Handle code or span
                            code_text = elem.get_text(strip=False)
                            if elem.name == 'code':
                                element_text = f"`{code_text}`"
                            else:
                                element_text = code_text
                        elif elem.name == 'p':
                            # Handle paragraphs
                            element_text = elem.get_text(strip=True)
                        
                        # Only add non-empty elements
                        if element_text.strip():
                            content_items.append({
                                "type": element_type,
                                "content": element_text.strip()
                            })
                
                # Add to our results
                discussion_data = {
                    "title": page_title,
                    "link": link,
                    "main_content": main_content,
                    "content_items": content_items
                }
                
                all_discussions.append(discussion_data)
                print(f"  Extracted content with {len(content_items)} content items")
                
                # Sleep between requests to avoid overloading the server
                time.sleep(2)
                
            except Exception as e:
                print(f"Error processing link {index+1}: {e}")
        
        # Save the parsed content as JSON only
        save_results(all_discussions, output_json)
        
    except Exception as e:
        print(f"Error during processing: {e}")
    finally:
        # Close the browser
        driver.quit()
        print("Browser closed")

def save_results(all_discussions, output_json):
    """Save the results to JSON file"""
    # Create output path relative to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_json_path = os.path.join(script_dir, output_json)
    
    # Save complete structured data as JSON
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_discussions, f, indent=2, ensure_ascii=False)
    print(f"Saved complete structured data to {output_json_path}")

if __name__ == "__main__":
    input_csv = "kaggle_sublinks.csv"  # CSV file with links
    output_json = "kaggle_discussion_content.json"  # Where to save the parsed content
    
    parse_discussion_content(input_csv, output_json)