# Scrollhouse AI Content Agent

An autonomous AI agent built for the Scrollhouse internship assignment. It monitors a Google Form in real time, generates short-form video scripts using GPT-4o-mini, logs every output to a Notion database, and sends an email notification — all without any human intervention.

---

## Problem Statement

Content agencies like Scrollhouse receive client briefs through forms. Traditionally, a team member has to:

1. Manually check the form for new submissions
2. Read and interpret the brief
3. Write a script draft
4. Copy it into a project management tool (like Notion)
5. Email the client or internal team about it

This is slow, error-prone, and does not scale. A single missed form submission can delay an entire campaign.

---

## How This Agent Solves It

This agent fully automates the entire pipeline end-to-end:

```
Client fills Google Form
        ↓
Agent polls Google Sheets every 60 seconds
        ↓
New submission detected → Brief parsed automatically
        ↓
GPT-4o-mini generates a structured video script
        ↓
Script + metadata saved to Notion (status: "Draft Ready")
        ↓
Email notification sent with the script and Notion link
        ↓
Submission marked as processed (no duplicates ever)
```

Zero manual steps. Zero missed submissions. Instant turnaround.

---

## Features

| Feature | Description |
|---|---|
| **Auto-polling** | Checks Google Sheets every 60 seconds for new form submissions |
| **Duplicate prevention** | Tracks processed submissions locally in `processed_submissions.json` so a brief is never processed twice |
| **AI script generation** | Uses OpenAI GPT-4o-mini to generate a full short-form video script tailored to the brand, platform, tone, and CTA |
| **Structured JSON output** | The AI returns a structured JSON with an internal brief, script draft, and quality notes |
| **Notion integration** | Creates a new Notion database entry per submission with brand, platform, status, and script |
| **Email notification** | Sends an email with the complete script and a direct Notion link |
| **Cloud-deployable** | Includes a `Procfile` for Heroku/Railway deployment via Gunicorn |
| **Timestamped logging** | Every action is logged with a timestamp for easy debugging |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| AI / LLM | OpenAI GPT-4o-mini |
| Form input | Google Forms → Google Sheets |
| Sheets API | Google Sheets API v4 (service account auth) |
| Project management | Notion API |
| Email | Gmail SMTP via `smtplib` |
| Web server | Flask + Gunicorn |
| Deployment | Heroku / Railway (Procfile included) |
| Config | python-dotenv (`.env` file) |

---

## Project Structure

```
scrollhouse-ai-agent/
│
├── main.py                      # Core agent — polling loop + full pipeline
├── agent_server.py              # Flask server variant (for cloud deployment)
├── credentials.json             # Google service account key (not committed)
├── processed_submissions.json   # Tracks already-processed form submissions
├── Procfile                     # Heroku/Railway process definition
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## How It Works — Detailed Walkthrough

### Step 1 — Google Form Intake

A client fills out a Google Form with the following fields:

- **Brand Name** — the client's brand
- **Target Audience** — who the content is for
- **Platform** — Instagram, TikTok, YouTube Shorts, etc.
- **Campaign Objective** — awareness, conversion, engagement, etc.
- **Key Message** — the core idea to communicate
- **Tone of Voice** — playful, professional, edgy, etc.
- **Call to Action** — what the viewer should do after watching
- **Constraints / Notes** — any dos/don'ts or special requirements

Responses land automatically in a linked Google Sheet.

---

### Step 2 — Polling Loop

The agent runs a continuous loop (`while True`) that wakes up every **60 seconds** and calls the Google Sheets API to fetch all rows. It compares each row's timestamp against `processed_submissions.json`. Only **new** submissions are processed.

```python
# Simplified logic
while True:
    submissions = get_all_submissions()   # Fetch from Sheets
    for sub in submissions:
        if sub["timestamp"] not in processed:
            process_submission(sub)        # Run the full pipeline
            processed.add(sub["timestamp"])
            save_processed(processed)      # Persist to disk
    time.sleep(60)
```

---

### Step 3 — AI Script Generation

Each new submission is sent to **GPT-4o-mini** with a carefully engineered prompt that instructs it to act as Scrollhouse's creative strategist. The model returns **strict JSON** with three sections:

```json
{
  "internal_brief": {
    "brand_name": "...",
    "target_audience": "...",
    "platform": "...",
    "campaign_objective": "...",
    "key_message": "...",
    "tone_of_voice": "...",
    "call_to_action": "...",
    "constraints": "..."
  },
  "script_draft": "Full video script here...",
  "quality_notes": "Notes on creative decisions..."
}
```

The structured JSON format ensures the output is machine-readable, so every field can be mapped directly to Notion properties without any text parsing.

---

### Step 4 — Notion Page Creation

A new page is created in the Notion database with the following properties automatically populated:

| Notion Field | Source |
|---|---|
| Brand | `internal_brief.brand_name` |
| Platform | `internal_brief.platform` |
| Status | Hardcoded → `"Draft Ready"` |
| Script | `script_draft` |

The page URL is returned and used in the email notification.

---

### Step 5 — Email Notification

A plain-text email is sent via Gmail SMTP containing:

- The brand name
- The full generated script
- A direct link to the Notion page

This gives the team an instant alert so they can review and publish.

---

### Step 6 — Duplicate Prevention

After processing, the submission's timestamp is saved to `processed_submissions.json`:

```json
["2026-03-05 10:34:00", "2026-03-05 11:02:15"]
```

On every future poll, these timestamps are skipped. Even if the server restarts, the file persists on disk and no submission is ever processed twice.

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/scrollhouse-ai-agent.git
cd scrollhouse-ai-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=sk-...
NOTION_API_KEY=secret_...
EMAIL_ADDRESS=your@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

> For `EMAIL_APP_PASSWORD`, generate a Gmail App Password from your Google Account → Security → 2-Step Verification → App Passwords.

### 4. Add Google credentials

Place your Google service account key file as `credentials.json` in the root directory.  
Share your Google Sheet with the service account email (e.g. `agent@project.iam.gserviceaccount.com`) with **Viewer** access.

### 5. Update config values

In `main.py`, set your own:

```python
SPREADSHEET_ID = "your-google-sheet-id"
NOTION_DATABASE_ID = "your-notion-database-id"
```

### 6. Run the agent

```bash
python main.py
```

The agent will start polling immediately and log all activity to the console.

---

## Deployment (Heroku / Railway)

The `Procfile` is already configured:

```
web: gunicorn agent_server:app
```

Set all environment variables (`OPENAI_API_KEY`, `NOTION_API_KEY`, `EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD`) in your platform's dashboard and deploy. The agent will run 24/7 in the cloud.

---

## Environment Variables Reference

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `NOTION_API_KEY` | Your Notion integration secret |
| `EMAIL_ADDRESS` | Gmail address used to send notifications |
| `EMAIL_APP_PASSWORD` | Gmail App Password (not your main password) |

---

## Key Design Decisions

**Why poll instead of webhooks?**  
Google Forms does not support native webhooks. Polling every 60 seconds is a simple, reliable, and dependency-free solution that works without any third-party trigger service.

**Why save processed IDs to a JSON file?**  
A lightweight flat file is sufficient for this scale. It survives server restarts and requires no database infrastructure, keeping the setup simple and portable.

**Why GPT-4o-mini?**  
It offers a strong balance of quality and cost for structured content generation. The strict JSON output instruction makes it reliable enough for fully automated downstream processing.

**Why two files (`main.py` and `agent_server.py`)?**  
`main.py` is the clean, well-structured version with richer AI output (full JSON schema). `agent_server.py` wraps the logic in a Flask app for cloud deployment compatibility with Gunicorn.

---

## Sample Output

**Generated Script (example)**

```
[HOOK - 0:00-0:03]
"What if your skincare routine was doing more harm than good?"

[PROBLEM - 0:03-0:10]
Most people don't realize how many harsh chemicals are hiding in their daily products.

[SOLUTION - 0:10-0:20]
That's why [Brand] uses only clean, dermatologist-approved ingredients — because your skin deserves better.

[CTA - 0:20-0:25]
Tap the link in bio and try your first bottle risk-free.
```

**Notion Entry**

| Field | Value |
|---|---|
| Brand | Glow Labs |
| Platform | Instagram |
| Status | Draft Ready |
| Script | *(full script above)* |

---

## What This Demonstrates

- **API integration** — Google Sheets API, OpenAI API, Notion API, Gmail SMTP all wired together
- **Autonomous agent design** — the agent makes decisions, takes actions, and self-corrects without human input
- **Prompt engineering** — structured JSON prompt design for reliable machine-readable AI output
- **Production readiness** — idempotent processing, persistent state, error handling, cloud deployment config
- **Real business value** — directly eliminates a manual, repetitive workflow inside a content agency

---

## Author

Built as an internship assignment submission for **Scrollhouse**.
