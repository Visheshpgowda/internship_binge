import os
import json
import time
import smtplib
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

# ==============================
# CONFIG
# ==============================

NOTION_DATABASE_ID = "31938c324c0a804eaac7caf3fbdd304f"

SPREADSHEET_ID = "1bUMlFolCpSJbSraLDE8ZkiNRhHhufGwN_FF2Fa7I0ZU"
RANGE_NAME = "Form Responses 1"

SERVICE_ACCOUNT_FILE = "credentials.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

CHECK_INTERVAL = 60

PROCESSED_FILE = "processed_submissions.json"

# ==============================
# CLIENTS
# ==============================

openai_client = OpenAI(api_key=OPENAI_API_KEY)
notion = Client(auth=NOTION_API_KEY)

# ==============================
# UTILITIES
# ==============================

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            return set(json.load(f))
    return set()

def save_processed(data):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(data), f)

# ==============================
# GOOGLE SHEETS
# ==============================

def fetch_rows():

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )

    service = build("sheets", "v4", credentials=creds)

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    rows = result.get("values", [])

    return rows

# ==============================
# AI GENERATION
# ==============================

def generate_script(data):

    log("🤖 Generating script with AI")

    prompt = f"""
You are Scrollhouse's creative strategist.

Generate a short-form video script.

Brand: {data['brand']}
Target Audience: {data['audience']}
Platform: {data['platform']}
Campaign Objective: {data['objective']}
Key Message: {data['message']}
Tone: {data['tone']}
Call To Action: {data['cta']}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    script = response.choices[0].message.content

    return script

# ==============================
# NOTION
# ==============================

def create_notion_page(brand, platform, objective, audience, script):

    log("📝 Creating Notion page")

    page = notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Brand": {
                "title": [
                    {"text": {"content": brand}}
                ]
            },

            "Platform": {
                "select": {
                    "name": platform
                }
            },

            "Status": {
                "select": {
                    "name": "Draft Ready"
                }
            },

            "Campaign Objective": {
                "rich_text": [
                    {"text": {"content": objective}}
                ]
            },

            "Target Audience": {
                "rich_text": [
                    {"text": {"content": audience}}
                ]
            },

            "Script": {
                "rich_text": [
                    {"text": {"content": script}}
                ]
            }
        }
    )

    page_url = page["url"]

    log(f"✅ Notion page created: {page_url}")

    return page_url

# ==============================
# EMAIL
# ==============================

def send_email(brand, script, notion_link):

    if not EMAIL_ADDRESS:
        log("⚠️ Email disabled (no credentials)")
        return

    log("📧 Sending email")

    body = f"""
New Script Generated 🚀

Brand: {brand}

Script:
{script}

View in Notion:
{notion_link}
"""

    msg = MIMEText(body)

    msg["Subject"] = f"Script Ready - {brand}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS

    try:

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()

        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)

        server.send_message(msg)

        server.quit()

        log("✅ Email sent")

    except Exception as e:

        log(f"⚠️ Email failed: {e}")

# ==============================
# PROCESS ROW
# ==============================

def process_submission(row):

    # Pad row if missing columns
    while len(row) < 8:
        row.append("")

    timestamp = row[0]
    brand = row[1]
    audience = row[2]
    platform = row[3]
    objective = row[4]
    message = row[5]
    tone = row[6]
    cta = row[7]

    log(f"Processing submission for brand: {brand}")

    data = {
        "brand": brand,
        "audience": audience,
        "platform": platform,
        "objective": objective,
        "message": message,
        "tone": tone,
        "cta": cta
    }

    script = generate_script(data)

    notion_link = create_notion_page(
        brand,
        platform,
        objective,
        audience,
        script
    )

    send_email(brand, script, notion_link)

# ==============================
# MAIN LOOP
# ==============================

def main():

    log("🚀 Scrollhouse AI Polling Agent Started")

    processed = load_processed()

    while True:

        try:

            rows = fetch_rows()

            if not rows:
                log("No data in sheet")

            for row in rows[1:]:  # skip header

                # ensure timestamp exists
                if not row:
                    continue

                timestamp = row[0]

                if timestamp not in processed:

                    log(f"🆕 New submission detected: {timestamp}")

                    process_submission(row)

                    processed.add(timestamp)

                    save_processed(processed)

        except Exception as e:

            log(f"❌ Error: {e}")

        log(f"Sleeping {CHECK_INTERVAL} seconds...\n")

        time.sleep(CHECK_INTERVAL)

# ==============================
# START
# ==============================

if __name__ == "__main__":
    main()