import os
from dotenv import load_dotenv
from pathlib import Path
from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

uri = os.getenv('IOT_MONGO_URI')
print(f"URI loaded from .env: '{uri}'")

try:
    client = MongoClient(uri)
    print("Nodes configured in client:")
    print(client.nodes)
    print("Host:")
    print(client.HOST)
    print("Port:")
    print(client.PORT)
except Exception as e:
    print(f"Error during creation: {e}")
