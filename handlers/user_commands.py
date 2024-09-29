import aiofiles
from aiogram import F, Bot, Router
from aiogram.enums import ContentType
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from pyrogram.client import Client
from keyboards.inline.inline_kb import make_row_keyboard, top_kb
from utils.utils import search_chats_by_tags

router = Router()

class ChatParserStates(StatesGroup):
    waiting_for_limit = State()
    waiting_for_tags = State()
    waiting_for_usernames = State()


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await message.answer(
        '<b>🔎 Сбор топа выдачи</b>\n\n'
        '— Выберите лимит',
        reply_markup=top_kb
    )
    await state.set_state(ChatParserStates.waiting_for_limit)
    
@router.callback_query(F.data == 'top-3')
async def chats_parser_top_3(
        call: CallbackQuery, bot: Bot,
        client: Client, state: FSMContext
    ):
    await call.answer()
    await state.update_data(limit=3)
    await state.set_state(ChatParserStates.waiting_for_tags)
    await bot.send_message(
        chat_id=call.from_user.id,
        text='Отправьте список тегов для поиска чатов\n'
        'Либо отправьте .txt файл с тегами'
    )
    
    

@router.callback_query(F.data == 'top-10')
async def chats_parser_top_10(
        call: CallbackQuery, bot: Bot,
        client: Client, state: FSMContext
    ):
    await call.answer()
    await state.update_data(limit=10)
    await state.set_state(ChatParserStates.waiting_for_tags)
    await bot.send_message(
        chat_id=call.from_user.id,
        text='Отправьте список тегов для поиска чатов\n'
        'Либо отправьте .txt файл с тегами'
    )
    
    

@router.message(ChatParserStates.waiting_for_tags, F.text | F.document)
async def parse_chats(message: Message, bot: Bot, client: Client, state: FSMContext):
    data = await state.get_data()
    text = ""

    if message.content_type == ContentType.DOCUMENT:
        if not message.document.file_name.endswith('.txt'):
            return await message.answer(
                '<b>❌ Название файла должно заканчиваться на .txt!</b>'
            )
        await bot.download(message.document, 'data/downloaded_tags.txt')
        async with aiofiles.open('data/downloaded_tags.txt', encoding='utf-8') as file:
            content = await file.read()
            if not content:
                return await message.answer(
                    '<b>❗️ В файле отсутствуют теги!</b>'
                )
            await state.update_data(tags=content)
            tags = content
    else:
        tags = message.text
        await state.update_data(tags=message.text)

    async with aiofiles.open('data/last_used_tags.txt', 'w', encoding='utf-8') as file:
        await file.write(tags)
        
    async with aiofiles.open('data/last_used_limit.txt', 'w', encoding='utf-8') as file:
        await file.write(str(data['limit']))

    await state.set_state(ChatParserStates.waiting_for_usernames)
    await bot.send_message(
        chat_id=message.from_user.id,
        text='Отправьте список юзернеймов для отслеживания (до 3)\n'
        'Либо отправьте .txt файл с юзернеймами'
    )


@router.message(ChatParserStates.waiting_for_usernames, F.text | F.document)
async def parse_chats_with_usernames(message: Message, bot: Bot, client: Client, state: FSMContext):
    data = await state.get_data()
    usernames = ""

    if message.content_type == ContentType.DOCUMENT:
        if not message.document.file_name.endswith('.txt'):
            return await message.answer(
                '<b>❌ Название файла должно заканчиваться на .txt!</b>'
            )
        await bot.download(message.document, 'data/downloaded_usernames.txt')
        async with aiofiles.open('data/downloaded_usernames.txt', encoding='utf-8') as file:
            content = await file.read()
            if not content:
                return await message.answer(
                    '<b>❗️ В файле отсутствуют юзернеймы!</b>'
                )
            usernames = content
    else:
        usernames = message.text

    # Разделяем юзернеймы по пробелам и переносам строк
    username_list = [username.strip() for username in usernames.split() if username.strip()]

        
    async with aiofiles.open('data/last_used_usernames.txt', 'w', encoding='utf-8') as file:
        await file.write(usernames)

    msg = await message.answer('<b>🔎 Идет поиск...</b>')
    results = await search_chats_by_tags(client, data['tags'], data['limit'], usernames)

    if len(results) == 0:
        await msg.edit_text('<b>❌ Не удалось найти чаты!</b>')
    else:
        await msg.delete()
        await message.answer(text=f'<b>✅ Успешно найдено {len(results)} чатов!</b>')
        
    await state.clear()
    await state.set_data({})