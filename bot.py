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

# Главное меню
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Новый расчет", callback_data="new")],
        [InlineKeyboardButton(text="📦 История", callback_data="history")]
    ])

# Кнопки пластика
def plastic_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="PLA — 129₪", callback_data="PLA")],
        [InlineKeyboardButton(text="PETG — 139₪", callback_data="PETG")],
        [InlineKeyboardButton(text="ABS — 120₪", callback_data="ABS")],
        [InlineKeyboardButton(text="TPU — 160₪", callback_data="TPU")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="cancel")]
    ])

# Доп расходы
def extra_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="LED 20₪", callback_data="LED")],
        [InlineKeyboardButton(text="Пропустить", callback_data="no_extra")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="cancel")]
    ])

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "📦 3dPrintCalc\n\nВыберите действие:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "new")
async def new_calc(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите тип пластика:", reply_markup=plastic_menu())
    user_state[callback.from_user.id] = {"step": "plastic"}

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

@dp.callback_query()
async def handle_buttons(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Отмена
    if callback.data == "cancel":
        user_state.pop(user_id, None)
        await callback.message.edit_text("Возврат в главное меню", reply_markup=main_menu())
        return

    state = user_state.get(user_id, {})

    # Выбор пластика
    if state.get("step") == "plastic":
        plastics = {"PLA":129, "PETG":139, "ABS":120, "TPU":160}
        state["plastic_price"] = plastics.get(callback.data, 129)
        state["step"] = "weight"
        await callback.message.edit_text("Введите вес модели (граммы):\nНапример: 120")
        return

    # Выбор доп расходов
    if state.get("step") == "extra":
        if callback.data == "LED":
            state["extra"] = 20
        else:
            state["extra"] = 0

        # Расчет и вывод
        result = calculate_price(
            state["weight"],
            state["time"],
            plastic_price=state["plastic_price"],
            extra=state["extra"]
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
Доп расходы: {state['extra']} ₪
Печать: {result['time_cost']} ₪

Себестоимость: {result['cost']} ₪
Прибыль 40%: {result['profit']} ₪

💰 Итог: {result['total']} ₪
"""
        await callback.message.edit_text(text, reply_markup=main_menu())
        user_state.pop(user_id)
        return

@dp.message()
async def handle_input(message: types.Message):
    user_id = message.from_user.id
    state = user_state.get(user_id, {})

    if not state:
        return

    if state.get("step") == "weight":
        state["weight"] = float(message.text)
        state["step"] = "time"
        await message.answer("Введите время печати (часы):\nНапример: 3")
        return

    if state.get("step") == "time":
        state["time"] = float(message.text)
        state["step"] = "extra"
        state["extra"] = 0
        await message.answer("Выберите доп расходы:", reply_markup=extra_menu())
        return

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
