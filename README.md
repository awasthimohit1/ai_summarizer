# 🚀 Daily AI/ML Blog Summarizer

A lightweight, serverless Python script that automatically monitors top AI/ML and engineering blogs, generates crisp bullet-point summaries using the Gemini API, and posts them to a Slack channel. Powered by GitHub Actions for daily automated runs.

---

## 🛠️ Features

- **Automated Monitoring**: Checks RSS/Atom feeds from top technology teams:
  - Meta Engineering
  - Netflix Tech Blog
  - Distill.pub
  - AWS Machine Learning
  - Apple Machine Learning Research
  - OpenAI News
  - NVIDIA Developer Blog
  - Airbnb Tech Blog
- **Gemini Summaries**: Summarizes articles using `gemini-2.5-flash` with a focus on core tech and ML takeaways.
- **Slack Integration**: Formats and delivers beautiful rich-text summaries directly to your Slack workspace.
- **Serverless & Stateless**: Runs on a daily schedule using GitHub Actions.
- **No Duplicates**: Automatically tracks processed articles using a normalized `history.json` database committed back to the repository.

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- A Gemini API Key (Get one from [Google AI Studio](https://aistudio.google.com/))
- A Slack Webhook URL (Setup an [Incoming Webhook](https://api.slack.com/messaging/webhooks) for your channel)

### 2. Local Setup
1. Clone this repository:
   ```bash
   git clone <your-repo-url>
   cd ai_blog_summarizer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   SLACK_WEBHOOK_URL=your_slack_webhook_url_here
   ```

4. Run the script:
   ```bash
   python main.py
   ```

---

## 🤖 GitHub Actions Deployment

The workflow in `.github/workflows/summarizer.yml` is configured to run automatically every day at **02:30 UTC** (08:00 AM IST) and can also be triggered manually.

### Required Secrets
To make the GitHub Actions runner work, add the following secrets to your GitHub repository (**Settings > Secrets and variables > Actions > Repository secrets**):

| Secret Name | Description |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API Key from Google AI Studio |
| `SLACK_WEBHOOK_URL` | The Incoming Webhook URL for your Slack channel |

### Workflow Permissions
The workflow writes state back to `history.json` to prevent duplicate posts. Make sure GitHub Actions has write permissions:
1. Go to **Settings > Actions > General**.
2. Under **Workflow permissions**, select **Read and write permissions**.
3. Click **Save**.