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
        [InlineKeyboardButton(text="Ввести вручную", callback_data="manual_extra")],
        [InlineKeyboardButton(text="Пропустить", callback_data="no_extra")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="cancel")]
    ])

# Количество
def quantity_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="1")],
        [InlineKeyboardButton(text="5", callback_data="5")],
        [InlineKeyboardButton(text="10", callback_data="10")],
        [InlineKeyboardButton(text="Ввести вручную", callback_data="manual_qty")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="cancel")]
    ])

# Маржа
def margin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обычный заказ 40%", callback_data="40")],
        [InlineKeyboardButton(text="Шабат 70%", callback_data="70")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="cancel")]
    ])

# Доставка
def delivery_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да 50₪", callback_data="50")],
        [InlineKeyboardButton(text="Нет", callback_data="0")],
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
    for r in rows[-10:]:
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

    # Шаги бота
    step = state.get("step")

    # Пластик
    if step == "plastic":
        plastics = {"PLA":129, "PETG":139, "ABS":120, "TPU":160}
        state["plastic_price"] = plastics.get(callback.data, 129)
        state["step"] = "weight"
        await callback.message.edit_text("Введите вес модели (граммы):")
        return

    # Доп расходы
    if step == "extra":
        if callback.data == "LED":
            state["extra"] = 20
            state["step"] = "quantity"
            await callback.message.answer("Выберите количество:", reply_markup=quantity_menu())
        elif callback.data == "manual_extra":
            state["step"] = "manual_extra_input"
            await callback.message.answer("Введите сумму доп расходов (₪):")
        else:  # no_extra
            state["extra"] = 0
            state["step"] = "quantity"
            await callback.message.answer("Выберите количество:", reply_markup=quantity_menu())
        return

    # Количество
    if step == "quantity":
        if callback.data == "manual_qty":
            state["step"] = "manual_qty_input"
            await callback.message.answer("Введите количество штук:")
        else:
            state["quantity"] = int(callback.data)
            state["step"] = "margin"
            await callback.message.answer("Выберите маржу:", reply_markup=margin_menu())
        return

    # Маржа
    if step == "margin":
        state["profit_percent"] = int(callback.data)/100
        state["step"] = "delivery"
        await callback.message.answer("Доставка? 50₪:", reply_markup=delivery_menu())
        return

    # Доставка
    if step == "delivery":
        state["delivery"] = int(callback.data)
        # Расчет
        result = calculate_price(
            weight=state["weight"],
            hours=state["time"],
            plastic_price=state["plastic_price"],
            extra=state.get("extra",0),
            quantity=state.get("quantity",1),
            profit_percent=state.get("profit_percent",0.4),
            delivery=state.get("delivery",0)
        )
        save_history(user_id, state["weight"], state["time"], result["total"])

        text = f"""
📦 3dPrintCalc

Вес: {state['weight']}г
Время: {state['time']}ч
Пластик: {state['plastic_price']} ₪
Доп расходы: {state.get('extra',0)} ₪
Количество: {state.get('quantity',1)}
Маржа: {int(state.get('profit_percent',0.4)*100)}%
Доставка: {state.get('delivery',0)} ₪

💰 Итог: {result['total']} ₪
"""
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить клиенту", callback_data="send_client")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="cancel")]
        ]))
        user_state.pop(user_id)
        return

    # Отправить клиенту
    if callback.data == "send_client":
        await callback.message.answer("✅ Итог отправлен клиенту (можно скопировать текст)")
        await callback.message.edit_reply_markup(reply_markup=main_menu())

@dp.message()
async def handle_input(message: types.Message):
    user_id = message.from_user.id
    state = user_state.get(user_id, {})

    if not state:
        return

    step = state.get("step")

    if step == "weight":
        state["weight"] = float(message.text)
        state["step"] = "time"
        await message.answer("Введите время печати (часы):")
        return

    if step == "time":
        state["time"] = float(message.text)
        state["step"] = "extra"
        await message.answer("Выберите доп расходы:", reply_markup=extra_menu())
        return

    if step == "manual_extra_input":
        state["extra"] = float(message.text)
        state["step"] = "quantity"
        await message.answer("Выберите количество:", reply_markup=quantity_menu())
        return

    if step == "manual_qty_input":
        state["quantity"] = int(message.text)
        state["step"] = "margin"
        await message.answer("Выберите маржу:", reply_markup=margin_menu())
        return

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
