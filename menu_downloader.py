import requests, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import os
import shutil

result_folder = "result_folder"
if os.path.exists(result_folder):
    shutil.rmtree(result_folder)
os.makedirs(result_folder, exist_ok=True)


base_url = "https://evenementen.uitslagen.nl/"
soup = BeautifulSoup(requests.get(base_url).text, 'html.parser')
i = 0
# 5K variations
inclusion_words_5k = [
    '5 km', '5km', '5 kilometer', '5.0 km', '5,0 km', '5000m', '5000 meter', '5.000m', 
    '5 van ', 'de 5 van'
]

# 10K variations
inclusion_words_10k = [
    '10 km', '10km', '10 kilometer', '10.0 km', '10,0 km', '10000m', '10000 meter', '10.000m',
    '10 van ', 'de 10 van'
]

# Half Marathon variations
inclusion_words_21k= [
    'halve marathon', 'half marathon', 
    '21.1', '21,1', '21 km', '21km', '21 kilometer', 
    '21.097', '21,097', '21.0975', '21,0975', '21097',
    '21 van ', 'de 21 van'
]

# Full Marathon variations
inclusion_words_42k = [
    'marathon', 
    '42.2', '42,2', '42 km', '42km', '42 kilometer', 
    '42.195', '42,195', '42195',
    '42 van ', 'de 42 van'
]
overall_inclusion = (inclusion_words_5k + inclusion_words_10k + inclusion_words_21k + inclusion_words_42k)
exclusion_words = [
    # So 2.5km does not get included since it contains '5km' etc. (and no i cant check for '0.5' or '0,5' since a full marathon is 42.195
    '0.5', '0,5',
    '1.5', '1,5',
    '2.5', '2,5',
    '3.5', '3,5',
    '4.5', '4,5',
    '6.5', '6,5',
    '7.5', '7,5',
    '8.5', '8,5',
    '9.5', '9,5',
    '10.5', '10,5',
    '12.5', '12,5',
    '17.5', '17,5',

    # Walking
    'wandel', 'wandelen', 'walk', 'nordic',
    
    # Corporate & Team events 
    'bedrijf', 'bedrijven', 'business', 'team', 'estafette', 'relay', 'duo', 'koppel',
    
    # Youth & Kids races 
    'jeugd', 'kids', 'scholieren', 'school', 'kinder', 'pupillen', 'bambino', 'peuter',
    
    # Other sports/categories mixed into running events
    'handbike', 'rolstoel', 'wheelchair', 'skate', 'inline', 'fiets','framerunner','wheeler'
    
    # Dog runs
    'canicross', 'hond'
]

rejected_categories = []

# Loops through all events 
for link in soup.find_all('a')[0:100]:
    path = link.get('href')

    # Get the date
    event_date = "Unknown"
    img_tag = link.find('img')
    if img_tag and img_tag.get('src'):
        image_url = img_tag.get('src')               # e.g., "/img/knop/2026-03-28 A.png"
        filename = image_url.split('/')[-1]          # e.g., "2026-03-28 A.png"
        event_date = filename[0:10]                  # e.g., "2026-03-28"

    # Safely construct the event URL
    event_url = urljoin(base_url, path)
    print(f"--------------------{path[6:-1]}----{event_date}------------------------------------- \n")

    try:
        # Go to the specific event and download the page
        event_soup = BeautifulSoup(requests.get(event_url).text, 'html.parser')
        umenu = event_soup.find('frame', attrs={'name': 'umenu'})

        if umenu:
            # Fetch the actual menu file
            menu_url = urljoin(event_url, umenu.get('src'))

            # Go to the events menu and download it.
            menu_soup = BeautifulSoup(requests.get(menu_url).text, 'html.parser')

            # Print all valid options (and always skip the first one, since it says "Selecteer afstand" or some variation of that)
            for opt in menu_soup.find_all('option')[1:]:
                val = opt.get('value')
                category = opt.get_text(strip=True).lower()
                inclusion = any(word in category for word in overall_inclusion)
                exclusion = any(word in category for word in exclusion_words)
                decision = inclusion and not exclusion

                if decision:
                    if any(word in category for word in inclusion_words_5k):
                        distance_class = "5K"
                    elif any(word in category for word in inclusion_words_10k):
                        distance_class = "10K"
                    elif any(word in category for word in inclusion_words_21k):
                        distance_class = "21K"
                    elif any(word in category for word in inclusion_words_42k):
                        distance_class = "42K"

                    file_name = f"{event_date}_{distance_class}_{path[6:-1]}.txt"
                    file_path = os.path.join(result_folder, file_name) # Create the full path here
                    print(file_name)

                    base_category_url = urljoin(event_url,val)
                    i = i+1
                    all_pages_data = []
                    page_num = 1
                    num_rows = 0
                    current_distance_rows = []

                    while True:
                        resp = requests.get(f"{base_category_url}&p={page_num}")
                        page_soup = BeautifulSoup(resp.text, 'html.parser')
                        all_tables = page_soup.find_all('table')
                        results_table = None
                        
                        for table in all_tables:
                            table_text = table.get_text(strip=True).lower()

                            # Check if the table is a results table by checking if it mentions 'naam' somewhere
                            if 'naam' in table_text:
                                results_table = table

                        if page_num == 1 and not os.path.exists(file_path):
                            page_table_rows = results_table.find_all('tr')
                        else:
                            page_table_rows = results_table.find_all('tr')[1:]

                        current_distance_rows.extend(page_table_rows[:])
                        num_page_rows = len(page_table_rows)

                        num_rows = num_rows + num_page_rows
                        if num_page_rows < 2: 
                            break
                        
                        page_num = page_num + 1  
                    
                    with open(os.path.join(result_folder, file_name), "a", encoding="utf-8") as file:
                        for row in current_distance_rows:
                            #.get_text(separator="\t", strip=True)
                            file.write(f"{row}\n")
                    

                else:
                    rejected_categories.append(category)

    except:
        print('something went wrong.')
        pass

    #time.sleep(0.5) # Prevent overloading the server


with open("rejected_categories.txt", "w", encoding="utf-8") as file:
    for category in rejected_categories:
        file.write(f"{category}\n")

print(f"\nSaved {len(rejected_categories)} rejected categories to 'rejected_categories.txt'")
print(i)    