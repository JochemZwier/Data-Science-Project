import requests
from bs4 import BeautifulSoup
import time
import os

# Create a directory to store the downloaded tables
download_folder = "downloaded_tables"
os.makedirs(download_folder, exist_ok=True)

# 1. Fetch the main website
url = "https://evenementen.uitslagen.nl/"
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

# 2. Find all event links
target_links = soup.find_all('a')

total_checked = 0
valid_tables = 0

# Note: Added [:10] here to just test the first 10 links. 
# Remove '[:10]' when you are ready to run it on all events!
for link in target_links:
    link_url = link['href']
    
    # Ensure the URL is formatted correctly
    if not link_url.startswith('/'):
        link_url = '/' + link_url
        
    full_link_url = f"https://evenementen.uitslagen.nl{link_url}uitslag.php?on=1&p=1&tl=nl"
    
    try:
        # Fetch the constructed URL
        page_response = requests.get(full_link_url)
        
        # Check if the page exists
        if page_response.status_code == 200:
            
            # Parse the specific event page
            page_soup = BeautifulSoup(page_response.text, 'html.parser')
            
            # Find ALL tables on the page
            tables = page_soup.find_all('table')
            
            if tables:
                # Find the table with the most rows (<tr> tags) to ensure we get the results table
                # and not a layout/menu table
                results_table = max(tables, key=lambda t: len(t.find_all('tr')))
                
                print(f"[SUCCESS] Saving table from: {full_link_url}")
                
                # Create a clean filename
                safe_filename = link_url.strip('/').replace('/', '_')
                if not safe_filename: 
                    safe_filename = "unknown_event"
                    
                filepath = os.path.join(download_folder, f"{safe_filename}.html")
                
                # Save ONLY the table's HTML as a string
                with open(filepath, 'w', encoding='utf-8') as file:
                    file.write(str(results_table))
                    
                valid_tables += 1
            else:
                print(f"[NO TABLE] Page loaded, but no tables found: {full_link_url}")
                
        elif page_response.status_code == 404:
            print(f"[404 SKIPPED] Not Found: {full_link_url}")
            
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to connect to {full_link_url}: {e}")
        
    total_checked += 1
    time.sleep(0.5)

print("\n--- SUMMARY ---")
print(f"Total links checked: {total_checked}")
print(f"Successfully downloaded tables: {valid_tables}")