import os
import json
import time
import feedparser
import requests
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from groq import Groq
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# --- 1. Define Structured Schemas ---
class ExtractedLink(BaseModel):
    title: str = Field(description="The clear title of the latest engineering/technical article found.")
    link: str = Field(description="The absolute URL to the full article.")

class FilterDecision(BaseModel):
    is_technical_ai_ml: bool = Field(description="True if the post covers core AI/ML, engineering infrastructure, or systems architecture.")
    confidence_score_1_to_10: int = Field(description="Confidence in this decision.")
    reasoning: str = Field(description="Brief 1-sentence engineering justification.")

class BlogExtraction(BaseModel):
    summary_bullets: list[str] = Field(description="3 highly technical summary bullets focusing on architectural metrics.")
    core_frameworks: list[str] = Field(description="Frameworks or libraries mentioned or implied.")
    infrastructure: list[str] = Field(description="Hardware or cloud infrastructure mentioned.")

# --- 2. Configuration & Initialization ---
FEEDS = {
    "Meta": "https://engineering.fb.com/feed/",
    "Apple": "https://machinelearning.apple.com/",
    "Google AI": "https://research.google/blog/",
    "Netflix": "https://research.netflix.com/archive",
    "Airbnb": "https://medium.com/airbnb-engineering/subpage/fa81dc8a53b3", #"https://airbnb.tech/",
    "Thinking Machines": "https://thinkingmachines.ai/blog/",
    "Deepmind": "https://deepmind.google/blog/",
    "Anthropic": "https://www.anthropic.com/engineering",
}
HISTORY_FILE = "history.json"

groq_key = os.getenv("GROQ_API_KEY")
if not groq_key:
    raise ValueError("🚨 CRITICAL ERROR: GROQ_API_KEY is blank!")

client = Groq(api_key=groq_key)

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")
if not SLACK_WEBHOOK:
    raise ValueError("🚨 CRITICAL ERROR: SLACK_WEBHOOK_URL is blank!")

MODEL_NAME = "llama-3.3-70b-versatile"

print("\n" + "="*60)
print("⚙️  STAGE 1: INITIALIZING SYSTEM PIPELINE CONTEXT")
print("="*60)
print("📦 Initializing Vector Database Client...")

print("\n⚡ [LAZY INITIALIZATION] New content detected. Spinning up local embedding models...")
# Force telemetry off in the settings
chroma_client = chromadb.PersistentClient(path="./vector_db", settings=Settings(anonymized_telemetry=False))

# chroma_client = chromadb.PersistentClient(path="./vector_db")
print("🧠 Initializing Local Embedding Model (SentenceTransformer)...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
vector_collection = chroma_client.get_or_create_collection(name="engineering_blogs")
print("✅ Initialization Sequence Complete.")
print("="*60 + "\n")

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

# --- 3. Dynamic LLM-Scraper Node ---
def dynamic_llm_scraper(company, url) -> dict | None:
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links_data = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if text and len(href) > 5:
                if href.startswith("/"):
                    base_url = "/".join(url.split("/")[:3])
                    href = f"{base_url}{href}"
                links_data.append({"text": text, "url": href})
        
        sample_links = links_data[:50]
        
        prompt = f"""Analyze this list of HTML links found on the {company} blog page. Identify the SINGLE newest specific engineering or research article post.
        
        CRITICAL RULES:
        1. DO NOT return generic homepage links, 'About' pages, or author profiles.
        2. DO NOT return the publication name or site header (e.g., 'The Airbnb Tech Blog', 'Netflix Technology Blog').
        3. The selected link MUST point to a specific, deeply-linked, uniquely titled technical article.
        
        Return its accurate title and full absolute URL.
        Links:
        {json.dumps(sample_links)}"""

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": f"You are a web parsing agent. You must output JSON matching this strict schema: {ExtractedLink.model_json_schema()}"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        data = json.loads(completion.choices[0].message.content)
        return {"title": data["title"], "link": data["link"], "content": data["title"]}
    except Exception as e:
        print(f"   ⚠️ Dynamic Scraper failed for {company}: {e}")
        return None

# --- 4. Cognitive Agent Nodes ---
def agent_triage_filter(title, content) -> FilterDecision:
    prompt = f"Evaluate this article for technical engineering depth in AI/ML or systems architecture.\nTitle: {title}\nContent: {content}"
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": f"You are an engineering filter agent. Output JSON matching this schema: {FilterDecision.model_json_schema()}"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    return FilterDecision(**json.loads(completion.choices[0].message.content))

def agent_data_extractor(content) -> BlogExtraction:
    prompt = f"Perform deep technical data extraction on this validated post:\n\n{content}"
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": f"You are a structured data extractor. Output JSON matching this schema: {BlogExtraction.model_json_schema()}"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    return BlogExtraction(**json.loads(completion.choices[0].message.content))

# --- 5. Vector Indexing Function ---
def index_to_vector_db(company, title, extract_data: BlogExtraction, link):
    text_to_embed = f"Company: {company}. Title: {title}. Summary: {' '.join(extract_data.summary_bullets)}. Frameworks: {', '.join(extract_data.core_frameworks)}. Infrastructure: {', '.join(extract_data.infrastructure)}."
    embedding = embedding_model.encode(text_to_embed).tolist()
    
    vector_collection.add(
        ids=[link],
        embeddings=[embedding],
        documents=[text_to_embed],
        metadatas=[{
            "company": company,
            "title": title,
            "link": link,
            "frameworks": json.dumps(extract_data.core_frameworks),
            "infrastructure": json.dumps(extract_data.infrastructure)
        }]
    )
    print(f"   💾 Vector database updated successfully for: {title}")

# --- 6. Delivery Layer ---
def send_to_slack(company, title, filter_data: FilterDecision, extract_data: BlogExtraction, link):
    bullets = "\n".join([f"• {b}" for b in extract_data.summary_bullets])
    frameworks = ", ".join(extract_data.core_frameworks) if extract_data.core_frameworks else "None mentioned"
    infra = ", ".join(extract_data.infrastructure) if extract_data.infrastructure else "None mentioned"
    
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚀 New {company} AI/ML Engineering Post"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n\n{bullets}"}
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Frameworks:* {frameworks} | *Infra:* {infra}\n*Gatekeeper Reason:* _{filter_data.reasoning}_"}
                ]
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

# --- 7. Pipeline Orchestration ---
def main():
    history = load_history()
    new_articles_processed = False
    candidates = []

    print("="*60)
    print("📡 STAGE 2: GATHERING AND PARSING RAW TARGET INGESTION")
    print("="*60)

    for company, url in FEEDS.items():
        print(f"🔄 Processing source node: {company}...")
        
        # Suppress the annoying yellow "InsecureRequest" warnings in your terminal
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Strategy A: RSS Stream
        if "feed" in url or "xml" in url:
            try:
                # Force requests to bypass Mac SSL blocks, then hand the text to feedparser
                headers = {"User-Agent": "Mozilla/5.0"}
                raw_feed = requests.get(url, headers=headers, verify=False, timeout=10).text
                feed = feedparser.parse(raw_feed)
                
                if feed.entries:
                    latest = feed.entries[0]
                    candidates.append({
                        "company": company,
                        "title": latest.title,
                        "link": latest.link,
                        "content": latest.summary if 'summary' in latest else latest.title
                    })
                    print(f"   ✅ [RSS Stream] Successfully parsed latest article.")
                    continue
            except Exception as e:
                print(f"   ⚠️ RSS Parse failed for {company}: {e}")
        
        # Strategy B: Dynamic LLM Scraper (Ensure verify=False is here too!)
        scraped_data = dynamic_llm_scraper(company, url)
        if scraped_data and scraped_data["link"]:
            candidates.append({
                "company": company,
                "title": scraped_data["title"],
                "link": scraped_data["link"],
                "content": scraped_data["content"]
            })
            print(f"   🤖 [LLM Scraper] Successfully bypassed layout block using Llama-3.3.")
            time.sleep(1)

    print("\n" + "="*60)
    print("🕵️‍♂️ STAGE 3: COGNITIVE AGENT FILTRATION AND EXECUTION SEQUENCE")
    print("="*60)
    
    total_candidates = len(candidates)
    if total_candidates == 0:
        print("No candidates available for inspection.")
        return

    # Execute Agent Coordination Loop with Manual Progress Bar Calculation
    for index, item in enumerate(candidates, start=1):
        percent_complete = int((index / total_candidates) * 100)
        
        # Simple string multiplication to construct a visual progress bar [████░░░░]
        bar_length = 20
        filled_length = int(bar_length * index // total_candidates)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print(f"\n[{bar}] {percent_complete}% | Item {index}/{total_candidates} | Ingesting: {item['company']}")
        
        if item["link"] in history:
            print(f"   ⏩ Skipping: Article tracking link already exists in indexed history.")
            continue
            
        print(f"   Processing entry: '{item['title']}'")
        
        print(f"   ├─ Running Agent 1 (Triage Filter)...")
        decision = agent_triage_filter(item["title"], item["content"])
        print(f"   ├─ Filter Result: Keep={decision.is_technical_ai_ml} (Confidence: {decision.confidence_score_1_to_10}/10)")
        print(f"   └─ Reason: {decision.reasoning}")
        
        if decision.is_technical_ai_ml:
            print(f"   ├─ Running Agent 2 (Technical Extractor)...")
            extracted_data = agent_data_extractor(item["content"])
            
            print(f"   ├─ Pushing notification packets up to Slack Webhook channel...")
            send_to_slack(item["company"], item["title"], decision, extracted_data, item["link"])
            
            print(f"   └─ Writing records down to local Chroma database collection...")
            index_to_vector_db(item["company"], item["title"], extracted_data, item["link"])
            
            time.sleep(2) 
        else:
            print(f"   ⏩ Dropping post: Classified as low-value/marketing content.")
        
        history.append(item["link"])
        new_articles_processed = True

    if new_articles_processed:
        save_history(history)
        
    print("\n" + "="*60)
    print("🏁 PIPELINE EXECUTION SEQUENCE COMPLETED.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()