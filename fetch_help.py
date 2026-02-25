import requests
from bs4 import BeautifulSoup

url = "https://help.medium.com/hc/en-us/articles/214874118-Using-RSS-feeds-of-profiles-publications-and-topics"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
try:
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        # Extract the main article content
        article = soup.find("article")
        if article:
            print(article.get_text(separator="\n"))
        else:
            print(soup.get_text(separator="\n"))
    else:
        print(f"Failed to fetch: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
