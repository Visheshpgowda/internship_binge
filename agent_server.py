import os
import json
import smtplib
from email.mime.text import MIMEText

from flask import Flask, request, jsonify

from dotenv import load_dotenv
from openai import OpenAI
from notion_client import Client

# ==============================
# ENV SETUP
# ==============================

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
notion = Client(auth=os.getenv("NOTION_API_KEY"))

app = Flask(__name__)

# ==============================
# CONFIG
# ==============================

NOTION_DATABASE_ID = "31938c324c0a804eaac7caf3fbdd304f"

EMAIL_ADDRESS = "visheshtechie15@gmail.com"
EMAIL_APP_PASSWORD = "fldc gipu mkgd kcxq"

# ==============================
# AI GENERATION
# ==============================

def generate_brief_and_script(form_data):

    print("🤖 Generating script with AI...")

    prompt = f"""
You are Scrollhouse's internal creative strategist.

Generate a short-form video script.

Return STRICT JSON only.

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
  "script_draft": "Hook, main script, CTA",
  "quality_notes": ""
}}

Client Submission:

Brand Name: {form_data['brand']}
Target Audience: {form_data['audience']}
Platform: {form_data['platform']}
Campaign Objective: {form_data['objective']}
Key Message: {form_data.get('message','')}
Tone of Voice: {form_data['tone']}
Call To Action: {form_data['cta']}
Constraints: {form_data.get('constraints','')}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    ai_output = response.choices[0].message.content

    print("🧠 AI response:", ai_output)

    return json.loads(ai_output)

# ==============================
# NOTION PAGE
# ==============================

def create_notion_page(result):

    print("📝 Creating Notion page...")

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

            "Campaign Objective": {
                "rich_text": [
                    {"text": {"content": result["internal_brief"]["campaign_objective"]}}
                ]
            },

            "Target Audience": {
                "rich_text": [
                    {"text": {"content": result["internal_brief"]["target_audience"]}}
                ]
            },

            "Script": {
                "rich_text": [
                    {"text": {"content": result["script_draft"]}}
                ]
            }

        }
    )

    page_url = page["url"]

    print("✅ Notion page created:", page_url)

    return page_url

# ==============================
# EMAIL SENDING
# ==============================

def send_email(brand, script, notion_link):

    print("📧 Sending email...")

    body = f"""
New Script Draft Ready 🚀

Brand: {brand}

Script:
{script}

View in Notion:
{notion_link}
"""

    msg = MIMEText(body)

    msg["Subject"] = f"New Script Ready - {brand}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS

    server = smtplib.SMTP("smtp.gmail.com", 587)

    server.starttls()

    server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)

    server.send_message(msg)

    server.quit()

    print("✅ Email sent")

# ==============================
# WEBHOOK ENDPOINT
# ==============================

@app.route("/webhook", methods=["POST"])
def webhook():

    form_data = request.json

    print("\n📩 Webhook triggered with data:", form_data)

    result = generate_brief_and_script(form_data)

    notion_link = create_notion_page(result)

    send_email(
        result["internal_brief"]["brand_name"],
        result["script_draft"],
        notion_link
    )

    return jsonify({"status": "success"})


# ==============================
# START SERVER
# ==============================

if __name__ == "__main__":

    print("\n🚀 Scrollhouse AI Agent Server Running\n")

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))