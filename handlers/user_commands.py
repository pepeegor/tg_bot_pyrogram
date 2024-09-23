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
    tags = ""

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
            tags = content
    else:
        tags = message.text

    if not tags.startswith('/start'):
        async with aiofiles.open('data/last_used_tags.txt', 'w', encoding='utf-8') as file:
            await file.write(tags)
        
    async with aiofiles.open('data/last_used_limit.txt', 'w', encoding='utf-8') as file:
        await file.write(str(data['limit']))

    msg = await message.answer('<b>🔎 Идет поиск...</b>')
    results = await search_chats_by_tags(client, tags, data['limit'])
    
    if len(results) == 0:
        await msg.edit_text('<b>❌ Не удалось найти чаты!</b>')
    else:
        await msg.delete()
        await message.answer(text=f'<b>✅ Успешно найдено {len(results)} чатов!</b>')

    await state.clear()
    await state.set_data({})
