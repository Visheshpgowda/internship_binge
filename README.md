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
├── main.py                      # Core agent — polling loop + full pipeline (run this)
├── agent_server.py              # Flask server variant (for cloud deployment)
├── credentials.json             # Google service account key (not committed to git)
├── processed_submissions.json   # Persistent state — tracks every processed submission
├── .env                         # Secret keys (not committed to git)
├── .env.example                 # Template for .env — safe to commit
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

### Step 6 — State Tracking & Duplicate Prevention

After every successful Notion page creation, the submission is persisted to `processed_submissions.json` **before** the email is sent. This ordering is deliberate — if email fails the submission is still marked done and won't be re-processed.

The state file stores rich metadata, not just a timestamp:

```json
{
  "3/4/2026 20:10:05": {
    "brand":        "Nike",
    "processed_at": "2026-03-04 20:10:12",
    "notion_url":   "https://notion.so/..."
  },
  "3/4/2026 20:15:22": {
    "brand":        "Glow Labs",
    "processed_at": "2026-03-04 20:15:29",
    "notion_url":   "https://notion.so/..."
  }
}
```

This prevents:
- Duplicate Notion pages
- Duplicate email notifications
- Wasted OpenAI API calls (and cost)
- Re-processing after server restarts (file survives restarts)

The file is written **atomically** — first to a temp file, then renamed — so a crash mid-write never corrupts it. On startup the agent auto-migrates any old list-format state files to this dict format automatically, so no data is ever lost.

Each poll cycle prints a clear summary:

```
[2026-03-05 10:34:01] 📊 Sheet: 5 row(s) | 4 already done | 1 new
```

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

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
OPENAI_API_KEY=sk-...
NOTION_API_KEY=secret_...
EMAIL_ADDRESS=your@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

> For `EMAIL_APP_PASSWORD`, go to Google Account → Security → 2-Step Verification → App Passwords and generate one for "Mail".
> **Never commit your `.env` file.** Add it to `.gitignore`.

### 4. Add Google service account credentials

Place your Google service account JSON key file as `credentials.json` in the root directory.
Share your Google Sheet with the service account email (e.g. `agent@project.iam.gserviceaccount.com`) with **Viewer** access.

### 5. Update config constants (if needed)

In `main.py`, confirm these match your actual resources:

```python
SPREADSHEET_ID     = "your-google-sheet-id"
NOTION_DATABASE_ID = "your-notion-database-id"
```

### 6. Run the agent

```bash
python main.py
```

The agent starts polling immediately. Example startup output:

```
==================================================
🚀 Scrollhouse AI Agent Starting
   Poll interval : 60s
   State file    : processed_submissions.json
   Email         : your@gmail.com
==================================================
📂 Loaded 2 previously processed submission(s)

[2026-03-05 10:34:01] 📊 Sheet: 5 row(s) | 4 already done | 1 new
──────────────────────────────────────────────────
[2026-03-05 10:34:01] 🆕 Processing: [3/5/2026 10:33:45] — Glow Labs
[2026-03-05 10:34:02] 🤖 Generating script with OpenAI (attempt 1/3)
[2026-03-05 10:34:04] 📝 Creating Notion page (attempt 1/3)
[2026-03-05 10:34:05] ✅ Notion page created: https://notion.so/...
[2026-03-05 10:34:05] 📧 Sending email notification
[2026-03-05 10:34:06] ✅ Email sent
[2026-03-05 10:34:06] ✅ Completed: Glow Labs
[2026-03-05 10:34:06] 😴 Sleeping 60s...
```

---

## Google Form — Required Setup

> **Yes, you need to configure your Google Form correctly for the agent to work.**

The agent reads column headers from the sheet to map data. Your Google Form questions must use **these exact names** (case-insensitive, the agent lowercases them):

| Google Form Question | Maps To |
|---|---|
| `Timestamp` | Auto-added by Google — do not add manually |
| `Brand Name` | `brand` |
| `Target Audience` | `audience` |
| `Platform` | `platform` |
| `Campaign Objective` | `objective` |
| `Key Message` | `message` |
| `Tone of Voice` | `tone` |
| `Call to Action` | `cta` |
| `Constraints / Notes` | `constraints` |

**Recommended question types:**
- `Platform` → Multiple choice (Instagram, TikTok, YouTube Shorts, LinkedIn, Twitter/X)
- `Tone of Voice` → Multiple choice (Playful, Professional, Bold, Minimalist, Edgy)
- `Campaign Objective` → Multiple choice (Awareness, Engagement, Conversion, Retention)
- All others → Short answer / Paragraph

> If a question name doesn't match, that field will come through blank. The AI will still run but the script quality will be lower.

---

## Notion Database — Required Setup

> **Yes, you need to configure your Notion database with these exact property names and types.**

| Property Name | Type | Notes |
|---|---|---|
| `Brand` | **Title** | Required — every Notion DB has one title property |
| `Platform` | **Select** | Options: Instagram, TikTok, YouTube Shorts, LinkedIn, Twitter/X, Other |
| `Status` | **Select** | Must include option: `Draft Ready` |
| `Target Audience` | **Rich Text** | |
| `Campaign Objective` | **Rich Text** | |
| `Script` | **Rich Text** | |
| `Quality Notes` | **Rich Text** | |

**How to set it up:**
1. Open Notion → create a new page → select **Table** view
2. Rename the default "Name" column → `Brand` (keep it as Title type)
3. Add each property above with the exact name and type listed
4. For `Status` select → add `Draft Ready` as an option
5. Share the database with your Notion integration (the one whose secret key you put in `.env`)
6. Copy the database ID from the URL: `notion.so/your-workspace/`**`31938c324c0a804eaac7caf3fbdd304f`**`?v=...`

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

**Why a dict for `processed_submissions.json` instead of a list?**  
The original approach stored only timestamps in a list. The upgraded approach stores a rich dict with brand name, processed timestamp, and Notion URL. This makes it easy to audit what was processed and when, debug failures, and manually remove a record if you ever need to force a reprocess.

**Why write state before sending email?**  
Email is non-fatal — if Gmail SMTP fails, it logs a warning and continues. If state were saved after email, a crashing mail server would cause every submission to reprocess forever. Saving state first guarantees idempotency regardless of email reliability.

**Why atomic writes for the state file?**  
Python's `open(..., "w")` truncates the file before writing. If the process is killed mid-write, you get an empty or corrupt JSON file. Atomic write (temp file + `shutil.move`) is OS-level atomic — either the old file or the new file exists, never a partial state.

**Why strip JSON fences from the AI response?**  
GPT models sometimes wrap JSON in ` ```json ``` ` markdown blocks even when instructed not to. Rather than hoping the model behaves, the `_strip_json_fences()` function defensively removes them before `json.loads()`, preventing crashes on otherwise valid responses.

**Why retry on API failures?**  
Both OpenAI and Notion APIs can return transient 5xx errors or rate-limit responses. MAX_RETRIES=3 with a 5-second backoff handles the vast majority of transient failures without any human intervention.

**Why two files (`main.py` and `agent_server.py`)?**  
`main.py` is the clean, production-quality standalone agent. `agent_server.py` wraps logic in Flask for Heroku/Railway's Gunicorn process model. Run `main.py` directly — it has the better implementation.

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
- **Autonomous agent design** — makes decisions, takes actions, and self-corrects without human input
- **Prompt engineering** — structured JSON prompt design for reliable machine-readable AI output
- **Production-grade state management** — idempotent processing with atomic writes and backward-compatible migration
- **Resilience** — per-submission error isolation, retry logic with backoff, non-fatal email handling
- **Security** — all secrets in `.env`, never hardcoded in source
- **Real business value** — directly eliminates a manual, repetitive, error-prone workflow inside a content agency

---

## Author

Built as an internship assignment submission for **Scrollhouse**.
