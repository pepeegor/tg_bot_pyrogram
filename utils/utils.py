
import asyncio
from datetime import datetime
import logging
import time
import aiofiles
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from pyrogram import Client
import pyrogram
from pyrogram.errors import FloodWait, RPCError
from pyrogram.raw import functions, types
from pyrogram.raw.functions.contacts import Search
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import format_cell_range, TextFormat, CellFormat
import schedule

from data.config import TABLE_NAME
from utils.session_manager import start_client, stop_client



async def get_chat_info(client: Client, chat: types.Chat):
    try:
        if isinstance(chat, types.Channel):
            # Канал или супергруппа
            chat_type = "канал" if chat.broadcast else "группа"
            username = chat.username or 'недоступно'
            title = chat.title or 'Без имени'
            participants_count = chat.participants_count or 0

        elif isinstance(chat, types.Chat):
            # Простая группа
            chat_type = "группа"
            username = chat.username or 'недоступно'
            title = chat.title or 'Без имени'
            participants_count = chat.participants_count or 0

        else:
            # Другие типы чатов пропускаем
            return None

        return {
            "username": username,
            "title": title,
            "subscribers": participants_count,
            "type": chat_type
        }

    except Exception as e:
        logging.error(f"Ошибка при обработке чата: {e}")
        return None

async def get_user_info(client: Client, user: types.User):
    try:
        if user.bot:
            chat_type = "бот"
            username = user.username or 'недоступно'
            title = user.first_name or 'Без имени'
            subscribers = 0  # Боты обычно не имеют подписчиков

            return {
                "username": username,
                "title": title,
                "subscribers": subscribers,
                "type": chat_type
            }

        else:
            # Если пользователь не бот, пропускаем
            return None

    except Exception as e:
        logging.error(f"Ошибка при обработке пользователя: {e}")
        return None

async def search_chats_by_tags(client: Client, tags: str, limit: int, usernames):
    results = []
    tag_list = tags.split("\n")
    username_list = [username.strip() for username in usernames.split() if username.strip()]
    async with client:
        for tag in tag_list:
            tag_clean = tag.strip()
            if not tag_clean:
                continue  # Пропускаем пустые строки

            rank = 1
            while True:
                try:
                    # Используем Pyrogram Raw API для поиска контактов
                    search_result = await client.invoke(
                        functions.contacts.Search(
                            q=tag_clean,
                            limit=limit
                        )
                    )
                    
                    # Обработка найденных чатов
                    for chat in search_result.chats:
                        # Определяем тип чата и собираем нужные данные
                        chat_info = await get_chat_info(client, chat)
                        if chat_info:
                            chat_info['rank'] = rank
                            chat_info['tag'] = tag_clean
                            results.append(chat_info)
                            rank += 1

                    # Обработка найденных пользователей (включая ботов)
                    for user in search_result.users:
                        if user.bot:
                            user_info = await get_user_info(client, user)
                            if user_info:
                                user_info['rank'] = rank
                                user_info['tag'] = tag_clean
                                results.append(user_info)
                                rank += 1

                    break  # Выход из цикла повторов при успешном выполнении

                except FloodWait as e:
                    logging.warning(f"Flood wait: {e.value} seconds. Waiting...")
                    await asyncio.sleep(e.value)
                except RPCError as e:
                    logging.error(f"RPC Error: {e}. Пропускаем текущий тег '{tag_clean}'.")
                    break  # Пропуск текущего тега при других RPC ошибках

    logging.info(f"Найдено результатов: {len(results)}")
    logging.info(f"{results}")
    await export_to_google_sheets(results, username_list)
    return results


def is_blank_row(row):
    return all(cell == "" for cell in row)

def group_consecutive_rows(rows):
    """
    Группирует последовательные номера строк в диапазоны.
    Например, [2, 3, 4, 6, 7] -> [(2, 4), (6, 7)]
    """
    if not rows:
        return []

    sorted_rows = sorted(rows)
    grouped = []
    start = sorted_rows[0]
    end = sorted_rows[0]

    for row in sorted_rows[1:]:
        if row == end + 1:
            end = row
        else:
            grouped.append((start, end))
            start = row
            end = row
    grouped.append((start, end))
    return grouped

async def export_to_google_sheets(data, username_list):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("data/credentials.json", scope)
    client_gs = gspread.authorize(creds)

    try:
        spreadsheet = client_gs.open(TABLE_NAME)
    except SpreadsheetNotFound:
        logging.error(f"Таблица с именем '{TABLE_NAME}' не найдена.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        sheet = spreadsheet.worksheet(today)
        spreadsheet.del_worksheet(sheet)
        sheet = spreadsheet.add_worksheet(title=today, rows="1000", cols="6")
        logging.info(f"Создан новый лист с названием '{today}'.")
    except WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=today, rows="1000", cols="6")
        logging.info(f"Создан новый лист с названием '{today}'.")
    
    # Запись заголовков
    headers = ["Rank", "Username", "Title", "Subscribers", "Type", "Tag"]
    sheet.append_row(headers)

    rows_to_write = []
    for entry in data:
        row = [
            entry.get("rank", ""),
            entry.get("username", ""),
            entry.get("title", ""),
            entry.get("subscribers", ""),
            entry.get("type", ""),
            entry.get("tag", "")
        ]
        rows_to_write.append(row)

    # Вставка пустых строк перед новыми группами
    new_rows_to_write = []
    for row in rows_to_write:
        if row[0] == 1 and new_rows_to_write:  # Если rank=1 и это не первая строка
            new_rows_to_write.append([""])  # Вставляем пустую строку
        new_rows_to_write.append(row)

    # Пакетная запись новых строк
    while True:
        try:
            sheet.append_rows(new_rows_to_write, value_input_option="RAW")
            break
        except APIError as e:
            if e.response.status_code == 429:
                logging.warning("Превышен лимит API, ожидание 60 секунд...")
                await asyncio.sleep(60)
            else:
                logging.error(f"Ошибка API при записи строк: {e}")
                raise

    # Подготовка списка username для форматирования
    username_list_lower = [username.lower() for username in username_list]
    logging.info(f'Usernames для форматирования: {username_list_lower}')

    # Сборка номеров строк для жирного форматирования
    bold_rows = []
    row_number = 2  # Начинаем с 2, так как первая строка — заголовки
    for row in new_rows_to_write:
        if is_blank_row(row):
            row_number += 1
            continue  # Пропускаем пустые строки

        username = row[1].lower() if row[1] else ""
        if username in username_list_lower:
            bold_rows.append(row_number)
        row_number += 1

    # Группировка последовательных строк
    grouped_bold_ranges = group_consecutive_rows(bold_rows)
    grouped_not_bold_rows = []  # Если нужно применять к остальным строки

    # Создание запросов для batch_update
    requests = []

    # Форматирование жирными
    for start, end in grouped_bold_ranges:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet.id,
                    "startRowIndex": start - 1,  # 0-индексация
                    "endRowIndex": end,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6  # Колонки A-F
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "bold": True
                        }
                    }
                },
                "fields": "userEnteredFormat.textFormat.bold"
            }
        })
        
    if requests:
        # Разбиваем запросы на батчи по 100 запросов (по умолчанию допустимо 500)
        batch_size = 100
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            while True:
                try:
                    sheet.spreadsheet.batch_update({'requests': batch})
                    logging.info(f"Применено форматирование для {len(batch)} запросов.")
                    break
                except APIError as e:
                    if e.response.status_code == 429:
                        logging.warning("Превышен лимит API при форматировании, ожидание 60 секунд...")
                        await asyncio.sleep(60)
                    else:
                        logging.error(f"Ошибка API при форматировании: {e}")
                        raise
            # Небольшая задержка между батчами
            await asyncio.sleep(1)

    logging.info("Форматирование успешно применено.")
    
async def daily_analysis(client: Client):
    client_me = await start_client(client)
    await stop_client(client)
    if client_me:
        logging.info("Запуск ежедневного анализа...")
        try:
            async with aiofiles.open('data/last_used_tags.txt', encoding='utf-8') as file:
                tags = await file.read()
            async with aiofiles.open('data/last_used_limit.txt', encoding='utf-8') as file:
                limit = int(await file.read())
            async with aiofiles.open('data/last_used_usernames.txt', encoding='utf-8') as file:
                usernames = await file.read()
            await search_chats_by_tags(client, tags, limit, usernames)
        except Exception as e:
            logging.error(f"Ошибка при ежедневном анализе: {e}")
            return False