import os
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

BOT_TOKEN = os.getenv('BOT_TOKEN')
TABLE_NAME = os.getenv('TABLE_NAME')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')