import os
import json
import feedparser
import requests
import time
from urllib.parse import urlparse, urlunparse
import google.generativeai as genai

# 1. Configuration
FEEDS = {
    "Meta": "https://engineering.fb.com/feed/",
    "Netflix": "https://netflixtechblog.com/feed",
    "Distill": "https://distill.pub/rss.xml",
    "AWS Machine Learning": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "Apple Machine Learning": "https://machinelearning.apple.com/rss.xml",
    "OpenAI": "https://openai.com/news/rss.xml",
    "NVIDIA": "https://developer.nvidia.com/blog/feed/",
    "Airbnb": "https://medium.com/feed/airbnb-engineering"
}
HISTORY_FILE = "history.json"

# Set up API keys (These will be pulled from GitHub Secrets or local .env)
api_key = os.getenv("GEMINI_API_KEY")
print(f"DEBUG: Did we find the Gemini Key? {'YES' if api_key else 'NO - It is completely blank!'}")

genai.configure(api_key=api_key)
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")
model = genai.GenerativeModel('gemini-2.5-flash')

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def get_entry_id(entry):
    # Use entry.id (GUID) if available and not empty, otherwise fallback to entry.link
    identifier = getattr(entry, 'id', None) or getattr(entry, 'link', '')
    
    # If it's a URL, normalize it by removing query parameters and fragments
    if identifier.startswith("http://") or identifier.startswith("https://"):
        try:
            parsed = urlparse(identifier)
            # Reconstruct without query parameters or fragment
            identifier = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, '', ''))
        except Exception:
            pass
    return identifier.strip()

def generate_summary(text):
    prompt = f"Summarize this engineering blog post in 3-4 crisp bullet points. Focus on the core tech and ML takeaways:\n\n{text}"
    response = model.generate_content(prompt)
    return response.text

def send_to_slack(company, title, summary, link):
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚀 New {company} AI/ML Blog"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n\n{summary}"}
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Read Full Article"}, "url": link}
                ]
            }
        ]
    }
    requests.post(SLACK_WEBHOOK, json=payload)

def main():
    # Load old history just to check for duplicates on this run
    old_history = load_history()
    
    # This will hold ONLY the latest articles from today's run
    current_history = []
    new_articles_processed = False
    
    for company, url in FEEDS.items():
        feed = feedparser.parse(url)
        
        for latest in feed.entries[:5]:
            entry_id = get_entry_id(latest)
            title = latest.title.strip() if latest.title else ""
            link = latest.link
            
            title_key = f"title:{title}"
            
            # Always track the latest articles for the next run's memory
            current_history.append(entry_id)
            current_history.append(title_key)
            
            # Only process and send to Slack if it wasn't seen in the previous run
            if entry_id not in old_history and title_key not in old_history:
                print(f"Processing new article from {company}: {title}")
                
                content = latest.summary if 'summary' in latest else title
                summary = generate_summary(content)
                
                send_to_slack(company, title, summary, link)
                new_articles_processed = True
                
                print("Sleeping for 20 seconds...")
                time.sleep(20)

    # Overwrite history.json with ONLY today's top articles
    save_history(current_history)
    print("history.json has been refreshed with only the latest articles.")

if __name__ == "__main__":
    main()
