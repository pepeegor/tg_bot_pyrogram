from pyrogram.client import Client

from data.config import API_HASH, API_ID


async def create_new_session():
    new_session = Client("session", API_ID, API_HASH)
    await new_session.start()
    await new_session.stop()