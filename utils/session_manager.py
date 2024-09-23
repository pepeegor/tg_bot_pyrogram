import asyncio
from contextlib import suppress
from pyrogram.client import Client

from data.config import API_HASH, API_ID


class ClientAlreadyWorking(Exception):
    pass

def create_client(name: str):
    return Client(
        name=name,
        api_id=API_ID,
        api_hash=API_HASH
    )

async def start_client(
        client: Client,
        check_work: bool = False
):
    if not client:
        return

    if check_work and client.is_connected:
        raise ClientAlreadyWorking

    with suppress(Exception):
        if not client.is_connected:
            await asyncio.wait_for(
                fut=client.connect(),
                timeout=15
            )
        return await client.get_me()


async def stop_client(client: Client):
    if client.is_connected:
        with suppress(Exception):
            await client.disconnect()