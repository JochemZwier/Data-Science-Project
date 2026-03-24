import requests
from bs4 import BeautifulSoup
import time

base_domain = "https://evenementen.uitslagen.nl"

# 1. Fetch the main website
response = requests.get(f"{base_domain}/")
soup = BeautifulSoup(response.text, 'html.parser')

# 2. Find all event links
target_links = soup.find_all('a')
total_events = len(target_links)

events_with_umenu = 0
# NEW: Create a list to store the URLs that fail the check
missing_umenu_urls = [] 

print(f"Found {total_events} total events. Starting the check...\n")

for link in target_links: 
    event_path = link.get('href')
    event_name = link.get_text(strip=True)
    
    # Skip empty or invalid links
    if not event_path or event_path.startswith('javascript'):
        continue
        
    # Ensure correct URL formatting
    if not event_path.startswith('/'):
        event_path = '/' + event_path
        
    # This is the main shell URL (e.g., /2017/bredasesingelloop/)
    event_main_url = f"{base_domain}{event_path}"
    
    try:
        # 3. Fetch the event's frameset page
        event_response = requests.get(event_main_url)
        event_soup = BeautifulSoup(event_response.text, 'html.parser')
        
        # 4. Search specifically for the frame named 'umenu'
        umenu_frame = event_soup.find('frame', attrs={'name': 'umenu'})
        
        if umenu_frame:
            events_with_umenu += 1
            src_file = umenu_frame.get('src')
            print(f"[YES] {event_name} -> Found 'umenu' (File: {src_file})")
        else:
            # UPDATED: Print the full URL inline
            print(f"[NO]  {event_name} -> No 'umenu' frame found. URL: {event_main_url}")
            # NEW: Add the full URL to our tracking list
            missing_umenu_urls.append(event_main_url)
            
    except Exception as e:
        print(f"[ERROR] Could not process {event_name}: {e}")
        
    # Be polite to their server
    time.sleep(0.5)

print("\n--- SUMMARY ---")
print(f"Events checked: {total_events}") # Fixed the extra parenthesis here from the previous code
print(f"Events with a 'umenu' frame: {events_with_umenu}")
print(f"Events missing a 'umenu' frame: {len(missing_umenu_urls)}")

# NEW: Print all the collected missing URLs at the very end
if missing_umenu_urls:
    print("\n--- URLs MISSING 'umenu' ---")
    for url in missing_umenu_urls:
        print(url)

"""
Both of these were cancelled and don't have results
https://evenementen.uitslagen.nl/2010/egmondhalvemarathon/
https://evenementen.uitslagen.nl/2010/egmondpieregmond/

This one needs an exception:
https://evenementen.uitslagen.nl/2003/amsterdammarathon/

Aswell as this one:
https://evenementen.uitslagen.nl/2010/warandeloop/

"""