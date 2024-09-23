
import asyncio
from datetime import datetime
import logging
import time
import aiofiles
from pyrogram import Client
from pyrogram.raw.functions.contacts import Search
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import format_cell_range, TextFormat, CellFormat
import schedule

from data.config import TABLE_NAME
from utils.session_manager import start_client, stop_client

# для всех сразу
# async def search_chats_by_tags(client: Client, tags: str, limit: int):
#     results = []

#     async with client:
#         search_results = await client.invoke(Search(
#             q=tags,
#             limit=limit
#         ))
#         for chat in search_results.chats:
#             if not chat.username:
#                 chat.username = 'недоступно'
            
#             chat_type = "канал" if chat.broadcast else "группа" if chat.megagroup or chat.gigagroup else None
#             if chat_type in ["канал", "группа"]:
#                 results.append({
#                     "rank": len(results) + 1,
#                     "username": chat.username,
#                     "title": chat.title,
#                     "subscribers": chat.participants_count or 0,
#                     "type": chat_type
#                 })
#     print(results)
#     export_to_google_sheets(results)
#     return results[:limit]

async def search_chats_by_tags(client: Client, tags: str, limit: int):
    results = []
    print(tags)
    tag_list = tags.split("\n")

    async with client:
        for tag in tag_list:
            rank = 1
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
                        "tag": tag.strip()  # Add the current tag to the result
                    })
                    rank += 1  # Increment rank for the next chat

    print(results)
    export_to_google_sheets(results)
    return results

def export_to_google_sheets(data):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("data/credentials.json", scope)
    client = gspread.authorize(creds)

    # Открытие таблицы
    spreadsheet = client.open(TABLE_NAME)
    
    # Создание нового листа с названием, равным текущей дате
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        # Проверка, существует ли уже лист с этой датой
        spreadsheet.worksheet(today)
        print(f"Лист с названием {today} уже существует.")
    except gspread.WorksheetNotFound:
        # Если лист не найден, создаем новый
        spreadsheet.add_worksheet(title=today, rows="100", cols="7")  # Increase columns to accommodate the new tag column
        print(f"Создан новый лист с названием {today}.")

    # Открытие нового листа
    sheet = spreadsheet.worksheet(today)
    sheet.clear()
    
    # Запись заголовков
    sheet.append_row(["Rank", "Username", "Title", "Subscribers", "Type", "Tag"])

    for entry in data:
        row = [entry["rank"], entry["username"], entry["title"], entry["subscribers"], entry["type"], entry["tag"]]
        sheet.append_row(row)
        
        row_index = len(sheet.get_all_values())
        
        if entry["type"] == "группа":
            fmt = CellFormat(
                textFormat=TextFormat(bold=True),
            )
            range_to_format = f"A{row_index}:F{row_index}"  # Update the range to F for the tag column
            format_cell_range(sheet, range_to_format, fmt)
        else:
            range_to_clear_format = f"A{row_index}:F{row_index}"
            format_cell_range(sheet, range_to_clear_format, CellFormat(textFormat=TextFormat(bold=False)))

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