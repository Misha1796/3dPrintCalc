import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

from calc import calculate_price
from db import init_db, save_history, get_history

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_state = {}

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Новый расчет", callback_data="new")],
        [InlineKeyboardButton(text="📦 История", callback_data="history")]
    ])

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "📦 3dPrintCalc\n\nВыберите действие:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "new")
async def new_calc(callback: types.CallbackQuery):
    await callback.message.edit_text("Введите вес модели (граммы):")
    user_state[callback.from_user.id] = {"step": "weight"}

@dp.callback_query(F.data == "history")
async def history(callback: types.CallbackQuery):
    rows = get_history(callback.from_user.id)

    if not rows:
        await callback.message.edit_text("История пуста", reply_markup=main_menu())
        return

    text = "📦 История расчетов:\n\n"

    for r in rows[:10]:
        text += f"{r[1]}г / {r[2]}ч → {r[3]}₪\n"

    await callback.message.edit_text(text, reply_markup=main_menu())

@dp.message()
async def handle_input(message: types.Message):
    user_id = message.from_user.id

    if user_id not in user_state:
        return

    state = user_state[user_id]

    if state["step"] == "weight":
        state["weight"] = float(message.text)
        state["step"] = "time"
        await message.answer("Введите время печати (часы):")
        return

    if state["step"] == "time":
        state["time"] = float(message.text)

        result = calculate_price(
            state["weight"],
            state["time"]
        )

        save_history(
            user_id,
            state["weight"],
            state["time"],
            result["total"]
        )

        text = f"""
📦 3dPrintCalc

Вес: {state['weight']}г
Время: {state['time']}ч

Пластик: {result['plastic']} ₪
Печать: {result['time_cost']} ₪

Себестоимость: {result['cost']} ₪
Прибыль 40%: {result['profit']} ₪

💰 Итог: {result['total']} ₪
"""

        await message.answer(text, reply_markup=main_menu())
        user_state.pop(user_id)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
