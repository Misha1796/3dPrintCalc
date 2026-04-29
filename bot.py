import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

# Твои модули
from calc import calculate_price
from db import init_db, save_history, get_history

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

user_state = {}

# --- Клавиатуры ---
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Новый расчет", callback_data="new")],
        [InlineKeyboardButton(text="📦 История", callback_data="history")]
    ])

# ... (остальные меню: plastic_menu, extra_menu и т.д. остаются из прошлых версий)
# ВАЖНО: Во всех меню кнопка "Назад" должна иметь callback_data="cancel"

# --- ИСПРАВЛЕННАЯ ИСТОРИЯ ---
@dp.callback_query(F.data == "history")
async def show_history(callback: types.CallbackQuery):
    rows = get_history(callback.from_user.id)
    
    if not rows:
        await callback.answer("История пуста 🤷‍♂️", show_alert=True)
        return

    text = "📋 **Последние расчеты:**\n\n"
    # Твоя БД: 0:id, 1:user_id, 2:weight, 3:time, 4:total
    for r in rows[:10]: # Берем последние 10
        text += f"🔹 {r[2]}г / {r[3]}ч → **{r[4]}₪**\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В меню", callback_data="cancel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- ЛОГИКА ОТПРАВКИ КЛИЕНТУ ---
@dp.callback_query(F.data == "send_client")
async def send_to_client(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if state and "final_text" in state:
        # 1. Сначала удаляем сообщение с кнопками (чтобы не дублировалось)
        await callback.message.delete()
        
        # 2. Отправляем чистый текст для копирования
        await callback.message.answer(f"```{state['final_text']}```", parse_mode="Markdown")
        
        # 3. Отправляем новое чистое главное меню
        await callback.message.answer("📦 **3dPrintCalc**\nВыберите действие:", reply_markup=main_menu(), parse_mode="Markdown")
        
        user_state.pop(callback.from_user.id, None)
        await callback.answer("Готово!")

# --- ФИНАЛЬНЫЙ ШАГ РАСЧЕТА ---
@dp.callback_query(F.data.startswith("dl_"))
async def finish_calc(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = user_state.get(user_id)
    if not state: return

    state["delivery"] = int(callback.data.split("_")[1])
    
    res = calculate_price(
        weight=state["weight"], hours=state["time"], plastic_price=state["plastic_price"],
        extra=state.get("extra", 0), quantity=state.get("quantity", 1),
        profit_percent=state.get("profit_percent", 0.4), delivery=state["delivery"]
    )
    
    # Сохраняем в БД
    save_history(user_id, state["weight"], state["time"], res["total"])
    
    subtotal = res["total"] - state["delivery"]
    
    summary = (
        f"🛠 Пластик: {state['plastic_name']}\n"
        f"⚖️ Вес: {state['weight']}г\n"
        f"⏱ Время: {state['time']}ч\n"
        f"📦 Кол-во: {state['quantity']} шт.\n"
        f"💵 Стоимость: {subtotal}₪\n"
        f"🚚 Доставка: {state['delivery']}₪\n\n"
        f"💰 Итого к оплате: {res['total']}₪"
    )
    
    state["final_text"] = f"📋 Смета на 3D печать\n\n{summary}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить клиенту", callback_data="send_client")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel")]
    ])
    
    await callback.message.edit_text(f"✅ **Расчет готов!**\n\n{summary}", reply_markup=kb, parse_mode="Markdown")

# --- Остальные хендлеры (start, handle_input, и т.д.) остаются без изменений ---
