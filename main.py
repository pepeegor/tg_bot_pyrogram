import asyncio
import logging
from aiofiles import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from create_session import create_new_session
from handlers import user_commands
from data.config import BOT_TOKEN
from utils.session_manager import create_client, start_client, stop_client
from utils.utils import daily_analysis

async def main():
    
    session_file = 'session.session'
    if not await os.path.exists(session_file):
        logging.error(f'Файл {session_file} не найден. Пожалуйста, создайте сессию.')
        await create_new_session()
        
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    client = create_client(name='session')
    client_me = await start_client(client)
    await stop_client(client)
    
    if client_me:
        logging.info(f'Session Valid - +{client_me.phone_number}')
    else:
        logging.info('Session Invalid')

    dp = Dispatcher()
    dp.include_router(user_commands.router)
    
    scheduler = AsyncIOScheduler()
    
    scheduler.add_job(daily_analysis, 'cron', hour=0, args=[client])
    # scheduler.add_job(daily_analysis, 'cron', minute='*', args=[client])
    
    scheduler.start()
    
    await dp.start_polling(bot, client=client)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())