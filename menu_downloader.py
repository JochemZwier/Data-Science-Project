import requests, time, csv
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import os
import shutil

result_folder = "result_folder"
if os.path.exists(result_folder):
    shutil.rmtree(result_folder)
os.makedirs(result_folder, exist_ok=True)

session = requests.Session()
base_url = "https://evenementen.uitslagen.nl/"
soup = BeautifulSoup(session.get(base_url).text, 'lxml')
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
    # 1. The 15/25/35 etc
    '15 km', '15km', '15 kilometer', '15.0', '15,0', '15000', '15.000', '15 van',
    '25 km', '25km', '25 kilometer', '25.0', '25,0', '25000', '25.000', '25 van',
    '35 km', '35km', '35 kilometer', '35.0', '35,0', '35000', '35.000', '35 van',
    '45 km', '45km', '45 kilometer', '45.0', '45,0', '45000', '45.000', '45 van',
    '55 km', '55km', '55 kilometer', '55.0', '55,0', '55000', '55.000', '55 van',

    # 2. Decimals & Fractions
    '0.5', '0,5', '1.5', '1,5', '2.5', '2,5', '3.5', '3,5', '4.5', '4,5',
    '6.5', '6,5', '7.5', '7,5', '8.5', '8,5', '9.5', '9,5', '10.5', '10,5',
    '11.5', '11,5', '12.5', '12,5', '13.5', '13,5', '14.5', '14,5',
    '15.5', '15,5', '16.5', '16,5', '17.5', '17,5', '18.5', '18,5', '19.5', '19,5',
    '.75', ',75', '.25', ',25', 

    # 3. Miles / Engelse Mijl
    '5 em', '10 em', '4 em', '2 em', '15 em', '16.1 km', '16,1 km',
    ' engelse mijl', ' mijl', ' miles',

    # 4. Ultra & Fractional Marathons
    'mini-marathon','mini marathon','mini', 'bruto', 'kwart', 'ultra', '50 km', '60 km', '100 km', '120 km',

    # 5. Off-road / Alternatives
    'cross', 'trail', 'strandrace', 'beach', 'boscross',

    # 6. Walking
    'wandel', 'wandelen', 'walk', 'nordic',
    
    # 7. Corporate & Team events 
    'bedrijf', 'bedrijven', 'business', 'team', 'estafette', 'relay', 'duo', 'koppel',
    
    # 8. Youth & Kids races 
    'jeugd', 'kids', 'scholieren', 'school', 'kinder', 'pupillen', 'bambino', 'peuter',
    
    # 9. Other sports/categories
    'handbike', 'rolstoel', 'wheel', 'skate', 'inline', 'fiets', 'frame', 'wheeler',
    
    # 10. Dog runs
    'canicross', 'hond','bigg'
]

# Keep track of all the accepted and rejected categories 
rejected_categories = []
accepted_categories = []

# Loops through all events 
for link in soup.find_all('a'):
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
        event_soup = BeautifulSoup(session.get(event_url).text, 'lxml')
        umenu = event_soup.find('frame', attrs={'name': 'umenu'})

        if umenu:
            # Fetch the actual menu file
            menu_url = urljoin(event_url, umenu.get('src'))

            # Go to the events menu and download it.
            menu_soup = BeautifulSoup(session.get(menu_url).text, 'lxml')

            # Loop trough all menu options (and always skip the first one, since it says "Selecteer afstand" or some variation of that)
            for opt in menu_soup.find_all('option')[1:]:
                val = opt.get('value')
                category = opt.get_text(strip=True).lower()
                inclusion = any(word in category for word in overall_inclusion)
                exclusion = any(word in category for word in exclusion_words)
                decision = inclusion and not exclusion

                # Check if we should(n't) accept a category based on white- and blacklisted words
                if decision:
                    
                    # Check what kind of event length it was accepted as
                    if any(word in category for word in inclusion_words_5k):
                        distance_class = "5K"
                    elif any(word in category for word in inclusion_words_10k):
                        distance_class = "10K"
                    elif any(word in category for word in inclusion_words_21k):
                        distance_class = "21K"
                    elif any(word in category for word in inclusion_words_42k):
                        distance_class = "42K"

                    accepted_categories.append(f"{category} as {distance_class}")
                    
                    # Create the filename and print it
                    file_name = f"{event_date}_{distance_class}_{path[6:-1]}.csv"
                    file_path = os.path.join(result_folder, file_name) 
                    print(file_name)

                    base_category_url = urljoin(event_url,val)
                    i = i+1
                    all_pages_data = []
                    page_num = 1
                    num_rows = 0
                    current_distance_rows = []

                    while True:
                        resp = session.get(f"{base_category_url}&p={page_num}")
                        page_soup = BeautifulSoup(resp.text, 'lxml')
                        all_tables = page_soup.find_all('table')
                        results_table = None
                        
                        for table in all_tables:
                            table_text = table.get_text(strip=True).lower()

                            time_words = ['tijd', 'time', 'netto', 'bruto', 'finish','resultaat']
                            # Check if the table is a results table by checking if it mentions 'naam' and something like a time somewhere
                            if 'naam' in table_text and any(word in table_text for word in time_words) and not table.find('table'):
                                results_table = table
                                break

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

                    with open(file_path, "a", encoding="utf-8-sig", newline="") as file:
                        writer = csv.writer(file)
                        
                        for row in current_distance_rows:
                            # 1. Grab all the cells in this specific row (both headers and data)
                            cells = row.find_all(['th', 'td'])
                            
                            # 2. Extract just the clean text from each cell into a list
                            clean_row_data = [cell.get_text(strip=True) for cell in cells]
                            
                            # 3. Write that list to the file as a perfect CSV row!
                            writer.writerow(clean_row_data)
                      
                else:
                    rejected_categories.append(category)
                
    except:
        print('something went wrong.')
        pass

    #time.sleep(0.5) # Prevent overloading the server
with open("accepted_categories.txt", "w", encoding="utf-8") as file:
    for category in accepted_categories:
        file.write(f"{category}\n")

with open("rejected_categories.txt", "w", encoding="utf-8") as file:
    for category in rejected_categories:
        file.write(f"{category}\n")

print(f"\nSaved {len(accepted_categories)} accepted categories to 'accepted_categories.txt'")
print(f"\nSaved {len(rejected_categories)} rejected categories to 'rejected_categories.txt'")