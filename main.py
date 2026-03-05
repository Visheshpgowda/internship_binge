import os
import json
import smtplib
import time
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

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
notion = Client(auth=os.getenv("NOTION_API_KEY"))


# ==============================
# CONFIG
# ==============================

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SERVICE_ACCOUNT_FILE = 'credentials.json'

SPREADSHEET_ID = "1bUMlFolCpSJbSraLDE8ZkiNRhHhufGwN_FF2Fa7I0ZU"
RANGE_NAME = "Form Responses 1"

NOTION_DATABASE_ID = "31938c324c0a804eaac7caf3fbdd304f"

EMAIL_ADDRESS = "visheshtechie15@gmail.com"
EMAIL_APP_PASSWORD = "fldc gipu mkgd kcxq"

CHECK_INTERVAL = 60
PROCESSED_FILE = "processed_submissions.json"


# ==============================
# UTILITIES
# ==============================

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_processed(processed):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed), f)


# ==============================
# GOOGLE SHEETS
# ==============================

def get_all_submissions():

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )

    service = build('sheets', 'v4', credentials=creds)

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    values = result.get("values", [])

    if len(values) < 2:
        return []

    headers = [h.strip().lower() for h in values[0]]

    submissions = []

    for row in values[1:]:
        while len(row) < len(headers):
            row.append("")

        data = dict(zip(headers, row))

        form_data = {
            "timestamp": data.get("timestamp", ""),
            "brand": data.get("brand name", ""),
            "audience": data.get("target audience", ""),
            "platform": data.get("platform", ""),
            "objective": data.get("campaign objective", ""),
            "message": data.get("key message", ""),
            "tone": data.get("tone of voice", ""),
            "cta": data.get("call to action", ""),
            "constraints": data.get("constraints / notes", "")
        }

        submissions.append(form_data)

    return submissions


# ==============================
# AI GENERATION
# ==============================

def generate_script(data):

    log("🤖 Generating script with OpenAI")

    prompt = f"""
You are Scrollhouse's creative strategist.

Generate a short-form video script.

Return STRICT JSON.

{{
 "internal_brief": {{
   "brand_name":"",
   "target_audience":"",
   "platform":"",
   "campaign_objective":"",
   "key_message":"",
   "tone_of_voice":"",
   "call_to_action":"",
   "constraints":""
 }},
 "script_draft":"",
 "quality_notes":""
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

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    output = response.choices[0].message.content

    return json.loads(output)


# ==============================
# NOTION
# ==============================

def create_notion_page(result):

    log("📝 Creating Notion page")

    page = notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={

            "Brand": {
                "title": [
                    {"text": {"content": result["internal_brief"]["brand_name"]}}
                ]
            },

            "Platform": {
                "select": {
                    "name": result["internal_brief"]["platform"]
                }
            },

            "Status": {
                "select": {
                    "name": "Draft Ready"
                }
            },

            "Script": {
                "rich_text": [
                    {"text": {"content": result["script_draft"]}}
                ]
            }

        }
    )

    return page["url"]


# ==============================
# EMAIL
# ==============================

def send_email(brand, script, notion_link):

    log("📧 Sending email")

    body = f"""
New Script Generated

Brand: {brand}

Script:
{script}

Notion Page:
{notion_link}
"""

    msg = MIMEText(body)

    msg["Subject"] = f"Script Ready - {brand}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
    server.send_message(msg)
    server.quit()


# ==============================
# PROCESS
# ==============================

def process_submission(data):

    result = generate_script(data)

    notion_link = create_notion_page(result)

    send_email(
        result["internal_brief"]["brand_name"],
        result["script_draft"],
        notion_link
    )


# ==============================
# MAIN LOOP
# ==============================

if __name__ == "__main__":

    log("🚀 Scrollhouse AI Agent Started")

    processed = load_processed()

    while True:

        try:

            submissions = get_all_submissions()

            for sub in submissions:

                submission_id = sub["timestamp"]

                if submission_id not in processed:

                    log(f"🆕 New submission detected: {sub['brand']}")

                    process_submission(sub)

                    processed.add(submission_id)

                    save_processed(processed)

                    log("✅ Submission processed\n")

        except Exception as e:

            log(f"❌ Error: {e}")

        time.sleep(CHECK_INTERVAL)