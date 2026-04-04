import requests
from bs4 import BeautifulSoup

# 1. Fetch the website
url = "https://evenementen.uitslagen.nl/"
response = requests.get(url)

# 2. Parse the HTML content
soup = BeautifulSoup(response.text, 'html.parser')

# 3. Find all <a> tags
target_links = soup.find_all('a')[0:10]
i = 0

# 4. Extract and print the data
for link in target_links:
    link_text = link.get_text(strip=False)
    link_url = link['href']
    full_link_url = "https://evenementen.uitslagen.nl" + link_url + "uitslag.php?on=1&p=1&tl=nl"
    print(full_link_url)
    i = i+1
    #print(f"Link:  {link_url}")
    
print(i)