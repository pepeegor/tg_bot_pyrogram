
import asyncio
from datetime import datetime
import logging
import time
import aiofiles
from gspread.exceptions import APIError
from pyrogram import Client
import pyrogram
from pyrogram.errors import FloodWait
from pyrogram.raw.functions.contacts import Search
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import format_cell_range, TextFormat, CellFormat
import schedule

from data.config import TABLE_NAME
from utils.session_manager import start_client, stop_client


async def search_chats_by_tags(client: Client, tags: str, limit: int):
    results = []
    print(tags)
    tag_list = tags.split("\n")

    async with client:
        for tag in tag_list:
            rank = 1
            while True:
                try:
                    search_results = await client.invoke(Search(
                        q=tag,
                        limit=limit,
                    ))
                    for chat in search_results.chats:
                        if not chat.username:
                            chat.username = 'недоступно'
                        
                        chat_type = "канал" if chat.broadcast else "группа" if chat.megagroup or chat.gigagroup else None
                        if chat_type in ["канал", "группа"]:
                            results.append({
                                "rank": rank,
                                "username": chat.username,
                                "title": chat.title,
                                "subscribers": chat.participants_count or 0,
                                "type": chat_type,
                                "tag": tag.strip()
                            })
                            rank += 1  # Увеличиваем ранг для следующего чата

                    break  # Exit retry loop if successful
                except FloodWait as e:
                    print(f"Flood wait: {e.value} seconds. Waiting...")
                    await asyncio.sleep(e.value)  # Wait for the specified time

    print(results)
    await export_to_google_sheets(results)  # Проверка лимита для записи
    return results

async def export_to_google_sheets(data):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("data/credentials.json", scope)
    client = gspread.authorize(creds)

    spreadsheet = client.open(TABLE_NAME)
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        spreadsheet.worksheet(today)
        print(f"Лист с названием {today} уже существует.")
    except gspread.WorksheetNotFound:
        spreadsheet.add_worksheet(title=today, rows="500", cols="7")  # Увеличьте количество строк
        print(f"Создан новый лист с названием {today}.")

    sheet = spreadsheet.worksheet(today)
    sheet.clear()
    
    # Запись заголовков
    headers = ["Rank", "Username", "Title", "Subscribers", "Type", "Tag"]
    sheet.append_row(headers)

    rows_to_write = []
    for entry in data:
        row = [entry["rank"], entry["username"], entry["title"], entry["subscribers"], entry["type"], entry["tag"]]
        rows_to_write.append(row)

    # Пакетная запись строк
    while True:
        try:
            sheet.append_rows(rows_to_write)  # Пакетная запись
            break  # Если запись успешна, выходим из цикла
        except APIError as e:
            if e.response.status_code == 429:  # Код 429 - превышен лимит
                print("Превышен лимит API, ожидание 1 минуты...")
                await asyncio.sleep(60)  # Пауза на 1 минуту
            else:
                raise  # Если ошибка другая, выбрасываем ее

    
    for index, entry in enumerate(data):
        row_index = index + 2  # Индекс строки в таблице (плюс 2 для заголовка)

        try:
            if entry["type"] == "группа":
                fmt = CellFormat(
                    textFormat=TextFormat(bold=True),
                )
                range_to_format = f"A{row_index}:F{row_index}"
                format_cell_range(sheet, range_to_format, fmt)  # Применяем жирный шрифт
            else:
                range_to_clear_format = f"A{row_index}:F{row_index}"
                format_cell_range(sheet, range_to_clear_format, CellFormat(textFormat=TextFormat(bold=False)))  # Обычный шрифт
        except APIError as e:
            if e.response.status_code == 429:  # Код 429 - превышен лимит
                print("Превышен лимит API при форматировании, ожидание 1 минуты...")
                await asyncio.sleep(60)  # Пауза на 1 минуту
                # Повторите попытку форматирования после паузы
                continue  # Вернуться к началу цикла
            else:
                raise  # Если ошибка другая, выбрасываем ее
            
async def daily_analysis(client: Client):
    client_me = await start_client(client)
    await stop_client(client)
    if client_me:
        logging.info("Запуск ежедневного анализа...")
        async with aiofiles.open('data/last_used_tags.txt', encoding='utf-8') as file:
            tags = await file.read()
        async with aiofiles.open('data/last_used_limit.txt', encoding='utf-8') as file:
            limit = int(await file.read())
        await search_chats_by_tags(client, tags, limit)