import os
import json
import smtplib
import time
import tempfile
import shutil
from datetime import datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv
from openai import OpenAI
from notion_client import Client

from google.oauth2 import service_account
from googleapiclient.discovery import build


# ==============================
# ENV SETUP
# ==============================

load_dotenv()

OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
NOTION_API_KEY     = os.getenv("NOTION_API_KEY")
EMAIL_ADDRESS      = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
notion        = Client(auth=NOTION_API_KEY)


# ==============================
# CONFIG
# ==============================

SCOPES               = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SERVICE_ACCOUNT_FILE = "credentials.json"

SPREADSHEET_ID = "1bUMlFolCpSJbSraLDE8ZkiNRhHhufGwN_FF2Fa7I0ZU"
RANGE_NAME     = "Form Responses 1"

NOTION_DATABASE_ID = "31938c324c0a804eaac7caf3fbdd304f"

CHECK_INTERVAL = 60          # seconds between each poll
PROCESSED_FILE = "processed_submissions.json"
MAX_RETRIES    = 3           # retries for OpenAI / Notion calls


# ==============================
# LOGGING
# ==============================

def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


# ==============================
# STATE TRACKING
# Stores a dict keyed by Google Form timestamp:
# {
#   "3/4/2026 20:10:05": {
#       "brand": "Nike",
#       "processed_at": "2026-03-04 20:10:12",
#       "notion_url": "https://notion.so/..."
#   }
# }
# ==============================

def load_processed() -> dict:
    """
    Load the state file. Auto-migrates the old list format
    (used before this upgrade) to the new dict format so no
    previously processed submissions get re-run.
    """
    if not os.path.exists(PROCESSED_FILE):
        return {}

    with open(PROCESSED_FILE, "r") as f:
        raw = json.load(f)

    # Backward-compat: old format was a plain list of timestamps
    if isinstance(raw, list):
        log("⚙️  Migrating processed_submissions.json from list → dict format")
        migrated = {
            ts: {"brand": "unknown", "processed_at": "migrated", "notion_url": ""}
            for ts in raw
        }
        save_processed(migrated)
        return migrated

    return raw


def save_processed(state: dict):
    """
    Atomic write — write to a temp file then rename so a crash
    mid-write never corrupts the state file.
    """
    dir_name = os.path.dirname(os.path.abspath(PROCESSED_FILE))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        shutil.move(tmp_path, PROCESSED_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


def already_processed(state: dict, timestamp: str) -> bool:
    return timestamp in state


def mark_processed(state: dict, timestamp: str, brand: str, notion_url: str):
    state[timestamp] = {
        "brand":        brand,
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notion_url":   notion_url,
    }
    save_processed(state)


# ==============================
# GOOGLE SHEETS
# ==============================

def get_all_submissions() -> list:
    """
    Fetch all rows from the linked Google Sheet.
    Returns a list of dicts, one per form response.
    Column headers from the sheet drive field mapping —
    no hard-coded column indices.
    """
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)

    result = (
        service.spreadsheets()
               .values()
               .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
               .execute()
    )

    values = result.get("values", [])

    if len(values) < 2:
        log("📭 No submissions in sheet yet.")
        return []

    headers = [h.strip().lower() for h in values[0]]

    submissions = []
    for row in values[1:]:
        # Pad short rows so zip never silently drops columns
        while len(row) < len(headers):
            row.append("")

        data = dict(zip(headers, row))

        submissions.append({
            "timestamp":   data.get("timestamp", ""),
            "brand":       data.get("brand name", ""),
            "audience":    data.get("target audience", ""),
            "platform":    data.get("platform", ""),
            "objective":   data.get("campaign objective", ""),
            "message":     data.get("key message", ""),
            "tone":        data.get("tone of voice", ""),
            "cta":         data.get("call to action", ""),
            "constraints": data.get("constraints / notes", ""),
        })

    return submissions


# ==============================
# AI GENERATION
# ==============================

def _strip_json_fences(text: str) -> str:
    """
    GPT sometimes wraps JSON in ```json ... ```.
    Strip those fences before json.loads so it never crashes.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        text = "\n".join(lines).strip()
    return text


def generate_script(data: dict, attempt: int = 1) -> dict:
    """
    Call GPT-4o-mini with the brief and return a parsed dict.
    Retries up to MAX_RETRIES times on JSON parse or API errors.
    """
    log(f"🤖 Generating script with OpenAI (attempt {attempt}/{MAX_RETRIES})")

    prompt = f"""
You are Scrollhouse's creative strategist.

Generate a short-form video script for the brief below.

Return ONLY valid JSON — no markdown fences, no extra text.

{{
  "internal_brief": {{
    "brand_name": "",
    "target_audience": "",
    "platform": "",
    "campaign_objective": "",
    "key_message": "",
    "tone_of_voice": "",
    "call_to_action": "",
    "constraints": ""
  }},
  "script_draft": "",
  "quality_notes": ""
}}

Brand Name: {data['brand']}
Target Audience: {data['audience']}
Platform: {data['platform']}
Campaign Objective: {data['objective']}
Key Message: {data['message']}
Tone: {data['tone']}
CTA: {data['cta']}
Constraints: {data['constraints']}
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        raw     = response.choices[0].message.content
        cleaned = _strip_json_fences(raw)
        return json.loads(cleaned)

    except (json.JSONDecodeError, Exception) as e:
        if attempt < MAX_RETRIES:
            log(f"⚠️  Script generation failed ({e}). Retrying in 5 s...")
            time.sleep(5)
            return generate_script(data, attempt + 1)
        raise RuntimeError(f"OpenAI failed after {MAX_RETRIES} attempts: {e}")


# ==============================
# NOTION
# ==============================

def create_notion_page(result: dict, attempt: int = 1) -> str:
    """
    Create a Notion page for this submission and return its URL.
    Retries up to MAX_RETRIES times on API errors.
    Handles Notion's 2000-char limit per rich_text block.
    """
    log(f"📝 Creating Notion page (attempt {attempt}/{MAX_RETRIES})")

    brief  = result["internal_brief"]
    script = result["script_draft"]
    notes  = result.get("quality_notes", "")

    def rich_text_block(text: str) -> list:
        # Notion caps each text block at 2000 characters
        chunks = [text[i:i + 2000] for i in range(0, max(len(text), 1), 2000)]
        return [{"text": {"content": chunk}} for chunk in chunks]

    try:
        page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Brand": {
                    "title": [{"text": {"content": brief.get("brand_name", "Unknown")}}]
                },
                "Platform": {
                    "select": {"name": brief.get("platform", "Other")}
                },
                "Status": {
                    "select": {"name": "Draft Ready"}
                },
                "Target Audience": {
                    "rich_text": rich_text_block(brief.get("target_audience", ""))
                },
                "Campaign Objective": {
                    "rich_text": rich_text_block(brief.get("campaign_objective", ""))
                },
                "Script": {
                    "rich_text": rich_text_block(script)
                },
                "Quality Notes": {
                    "rich_text": rich_text_block(notes)
                },
            },
        )
        url = page["url"]
        log(f"✅ Notion page created: {url}")
        return url

    except Exception as e:
        if attempt < MAX_RETRIES:
            log(f"⚠️  Notion failed ({e}). Retrying in 5 s...")
            time.sleep(5)
            return create_notion_page(result, attempt + 1)
        raise RuntimeError(f"Notion failed after {MAX_RETRIES} attempts: {e}")


# ==============================
# EMAIL
# ==============================

def send_email(brand: str, script: str, notion_link: str):
    """
    Send a plain-text notification via Gmail SMTP.
    Gracefully skips if credentials are not set in .env.
    Non-fatal — a mail failure never blocks the pipeline.
    """
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        log("⚠️  Email skipped — EMAIL_ADDRESS / EMAIL_APP_PASSWORD not set in .env")
        return

    log("📧 Sending email notification")

    body = f"""New Script Generated 🚀

Brand:       {brand}
Notion Page: {notion_link}

--- SCRIPT ---
{script}
"""

    msg            = MIMEText(body)
    msg["Subject"] = f"Script Ready — {brand}"
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = EMAIL_ADDRESS

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        server.ehlo()
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        log("✅ Email sent")
    except Exception as e:
        log(f"⚠️  Email failed (non-fatal): {e}")


# ==============================
# PROCESS ONE SUBMISSION
# ==============================

def process_submission(sub: dict, state: dict):
    """
    Full pipeline for a single new form submission.
    State is written to disk immediately after Notion succeeds —
    before email — so a crash in email never causes a re-process.
    If anything fails, the submission is left un-marked so it will
    be retried on the next poll cycle automatically.
    """
    timestamp = sub["timestamp"]
    brand     = sub["brand"] or "Unknown Brand"

    log("─" * 50)
    log(f"🆕 Processing: [{timestamp}] — {brand}")

    try:
        # 1. Generate AI script
        result = generate_script(sub)

        # 2. Push to Notion
        notion_url = create_notion_page(result)

        # 3. Persist state BEFORE email (email is non-fatal)
        mark_processed(state, timestamp, brand, notion_url)

        # 4. Send email notification
        send_email(
            result["internal_brief"].get("brand_name", brand),
            result["script_draft"],
            notion_url,
        )

        log(f"✅ Completed: {brand}")

    except Exception as e:
        log(f"❌ Failed to process [{brand}]: {e}")
        log("   → Submission NOT marked as processed. Will retry next poll.")


# ==============================
# MAIN LOOP
# ==============================

if __name__ == "__main__":

    log("=" * 50)
    log("🚀 Scrollhouse AI Agent Starting")
    log(f"   Poll interval : {CHECK_INTERVAL}s")
    log(f"   State file    : {PROCESSED_FILE}")
    log(f"   Email         : {EMAIL_ADDRESS or 'NOT CONFIGURED — set in .env'}")
    log("=" * 50)

    # Load persisted state once at startup
    state = load_processed()
    log(f"📂 Loaded {len(state)} previously processed submission(s)\n")

    while True:

        try:
            submissions = get_all_submissions()
            total    = len(submissions)
            new_subs = [s for s in submissions if not already_processed(state, s["timestamp"])]
            skipped  = total - len(new_subs)

            log(f"📊 Sheet: {total} row(s) | {skipped} already done | {len(new_subs)} new")

            for sub in new_subs:
                # Skip rows with no timestamp (manually inserted sheet rows, not Form submissions)
                if not sub["timestamp"].strip():
                    log(f"⚠️  Skipping row with empty timestamp (brand: '{sub['brand']}') — not a Form submission")
                    continue

                # Re-check state here in case two rows share the same timestamp
                # (e.g. duplicate manual entries added to the sheet)
                if already_processed(state, sub["timestamp"]):
                    log(f"⏭️  Already processed this cycle: [{sub['timestamp']}] — skipping duplicate")
                    continue

                process_submission(sub, state)

        except Exception as e:
            log(f"❌ Poll cycle error: {e}")

        log(f"😴 Sleeping {CHECK_INTERVAL}s...\n")
        time.sleep(CHECK_INTERVAL)