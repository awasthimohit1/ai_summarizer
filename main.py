import os
import json
import feedparser
import requests
import time
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
    history = load_history()
    new_articles_processed = False

    for company, url in FEEDS.items():
        feed = feedparser.parse(url)
        
        # Check the latest article in the feed
        if feed.entries:
            latest = feed.entries[0]
            link = latest.link
            
            if link not in history:
                print(f"Processing new article from {company}: {latest.title}")
                
                # Some feeds put content in 'summary', others in 'content'
                content = latest.summary if 'summary' in latest else latest.title
                summary = generate_summary(content)
                
                send_to_slack(company, latest.title, summary, link)
                
                history.append(link)
                new_articles_processed = True
                
                # Pause for 20 seconds to respect Gemini free tier rate limits
                print("Sleeping for 20 seconds...")
                time.sleep(20)

    if new_articles_processed:
        save_history(history)
    else:
        print("No new articles today.")

if __name__ == "__main__":
    main()
