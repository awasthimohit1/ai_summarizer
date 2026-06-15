import requests
from bs4 import BeautifulSoup

def scrape_anthropic_engineering():
    """Scrapes the latest article from Anthropic's Engineering page."""
    url = "https://www.anthropic.com/engineering"
    
    # Pretend to be a real web browser to avoid getting blocked by anti-bot walls
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.find_all('a', href=True)
        
        latest_article = None
        for a in articles:
            href = a['href']
            # Look specifically for links that point to deep engineering posts
            # We check length > 13 to ignore the main "/engineering" link itself
            if href.startswith('/engineering/') and len(href) > 13: 
                # Extract the title (usually nested inside the link tag)
                title = a.get_text(strip=True)
                
                # Sometimes websites use invisible links for images. We only want links with text.
                if title:
                    latest_article = {
                        "title": title,
                        "link": f"https://www.anthropic.com{href}"
                    }
                    break # We found the newest one, so stop the loop!
                    
        return latest_article

    except Exception as e:
        print(f"Scraping failed: {e}")
        return None

# Test it locally
if __name__ == "__main__":
    print("Scraping Anthropic Engineering...")
    data = scrape_anthropic_engineering()
    if data:
        print(f"✅ Found: {data['title']}")
        print(f"🔗 Link: {data['link']}")
    else:
        print("❌ Could not find any articles. The HTML structure might be different, or they are blocking bots.")