from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

top_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Топ 3',
                callback_data='top-3'
            ),
            InlineKeyboardButton(
                text='Топ 10',
                callback_data='top-10'
            )
        ]
    ]
)

def make_row_keyboard(items: list[str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=item) for item in items]
    return InlineKeyboardMarkup(keyboard=[row], resize_keyboard=True)