import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

print("TOKEN:", os.getenv("NOTION_API_KEY"))

notion = Client(auth=os.getenv("NOTION_API_KEY"))

db = notion.databases.retrieve("31938c324c0a804eaac7caf3fbdd304f")

print(db["title"])