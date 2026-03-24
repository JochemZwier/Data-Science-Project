import requests
from bs4 import BeautifulSoup

# 1. Fetch the website
url = "https://evenementen.uitslagen.nl/"
response = requests.get(url)

# 2. Parse the HTML content
soup = BeautifulSoup(response.text, 'html.parser')

# 3. Find all <a> tags
target_links = soup.find_all('a')
i = 0
# 4. Extract and print the data
for link in target_links:
    link_text = link.get_text(strip=True)
    link_url = link['href']
    i = i+1
    #print(f"Link:  {link_url}")
    
print(i)