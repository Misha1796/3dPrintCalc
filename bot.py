import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Пытаемся импортировать твои модули
try:
    from calc import calculate_price
    from db import init_db, save_history, get_history
except ImportError:
    # Заглушка, если модулей нет (для тестов)
    def calculate_price(weight, hours, plastic_price, extra, quantity, profit_percent, delivery):
        # Примерная логика: (себестоимость + доп) * наценка * кол-во + доставка
        base = (weight * (plastic_price/1000) + hours * 5 + extra) 
        total = (base * (1 + profit_percent)) * quantity + delivery
        return {"total": round(total, 2)}
    def init_db(): pass
    def save_history(*args): pass
    def get_history(*args): return []

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище состояний: {user_id: {data}}
user_state = {}

# --- Клавиатуры ---

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Новый расчет", callback_data="new")],
        [InlineKeyboardButton(text="📦 История", callback_data="history")]
    ])

def plastic_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="PLA — 129₪", callback_data="pl_129_PLA")],
        [InlineKeyboardButton(text="PETG — 139₪", callback_data="pl_139_PETG")],
        [InlineKeyboardButton(text="ABS — 120₪", callback_data="pl_120_ABS")],
        [InlineKeyboardButton(text="TPU — 160₪", callback_data="pl_160_TPU")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel")]
    ])

def extra_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="LED (+20₪)", callback_data="ex_20")],
        [InlineKeyboardButton(text="Своя сумма", callback_data="ex_manual")],
        [InlineKeyboardButton(text="Без допов", callback_data="ex_0")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel")]
    ])

def quantity_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 шт", callback_data="qty_1"), InlineKeyboardButton(text="5 шт", callback_data="qty_5")],
        [InlineKeyboardButton(text="10 шт", callback_data="qty_10"), InlineKeyboardButton(text="Своё число", callback_data="qty_manual")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel")]
    ])

def margin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обычный (40%)", callback_data="mr_40")],
        [InlineKeyboardButton(text="Шабат (70%)", callback_data="mr_70")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel")]
    ])

def delivery_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да (50₪)", callback_data="dl_50")],
        [InlineKeyboardButton(text="Нет (0₪)", callback_data="dl_0")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel")]
    ])

# --- Обработчики Callback ---

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("📦 **3dPrintCalc**\nВыберите действие:", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "new")
async def new_calc(callback: types.CallbackQuery):
    user_state[callback.from_user.id] = {"main_msg_id": callback.message.message_id, "step": "plastic"}
    await callback.message.edit_text("🔵 **Шаг 1:** Выберите тип пластика:", reply_markup=plastic_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery):
    user_state.pop(callback.from_user.id, None)
    await callback.message.edit_text("📦 **3dPrintCalc**\nВыберите действие:", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("pl_"))
async def set_plastic(callback: types.CallbackQuery):
    _, price, name = callback.data.split("_")
    state = user_state.get(callback.from_user.id)
    if state:
        state.update({"plastic_price": int(price), "plastic_name": name, "step": "weight"})
        await callback.message.edit_text("⚖️ **Шаг 2:** Введите вес модели (в граммах):")

@dp.callback_query(F.data.startswith("ex_"))
async def set_extra(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if not state: return
    
    if callback.data == "ex_manual":
        state["step"] = "manual_extra"
        await callback.message.edit_text("💰 Введите сумму доп. расходов (₪):")
    else:
        state.update({"extra": int(callback.data.split("_")[1]), "step": "quantity"})
        await callback.message.edit_text("🔢 **Шаг 5:** Выберите количество:", reply_markup=quantity_menu())

@dp.callback_query(F.data.startswith("qty_"))
async def set_qty(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if not state: return
    
    if callback.data == "qty_manual":
        state["step"] = "manual_qty"
        await callback.message.edit_text("🔢 Введите количество штук:")
    else:
        state.update({"quantity": int(callback.data.split("_")[1]), "step": "margin"})
        await callback.message.edit_text("📈 **Шаг 6:** Выберите наценку:", reply_markup=margin_menu())

@dp.callback_query(F.data.startswith("mr_"))
async def set_margin(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if state:
        state.update({"profit_percent": int(callback.data.split("_")[1]) / 100, "step": "delivery"})
        await callback.message.edit_text("🚚 **Шаг 7:** Доставка (50₪)?", reply_markup=delivery_menu())

@dp.callback_query(F.data.startswith("dl_"))
async def finish_calc(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = user_state.get(user_id)
    if not state: return

    state["delivery"] = int(callback.data.split("_")[1])
    
    result = calculate_price(
        weight=state["weight"],
        hours=state["time"],
        plastic_price=state["plastic_price"],
        extra=state.get("extra", 0),
        quantity=state.get("quantity", 1),
        profit_percent=state.get("profit_percent", 0.4),
        delivery=state["delivery"]
    )
    
    save_history(user_id, state["weight"], state["time"], result["total"])
    subtotal = result["total"] - state["delivery"]

    summary = (
        f"🛠 Пластик: {state['plastic_name']}\n"
        f"⚖️ Вес: {state['weight']}г\n"
        f"⏱ Время: {state['time']}ч\n"
        f"📦 Кол-во: {state['quantity']} шт.\n"
        f"💵 Стоимость: {subtotal}₪\n"
        f"🚚 Доставка: {state['delivery']}₪\n\n"
        f"💰 Итого к оплате: {result['total']}₪"
    )
    
    state["final_text"] = f"📋 **Смета на 3D печать**\n\n{summary}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить клиенту", callback_data="send_client")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="cancel")]
    ])
    
    await callback.message.edit_text(f"✅ **Расчет готов!**\n\n{summary}", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "send_client")
async def send_to_client(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if state and "final_text" in state:
        # Отправляем чистый текст в моноширинном формате для копирования
        await callback.message.answer(f"```{state['final_text']}```", parse_mode="Markdown")
        await callback.answer("Готово!")

# --- Обработка ввода текста ---

@dp.message()
async def handle_input(message: types.Message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    if not state or "main_msg_id" not in state: return

    # Удаляем сообщение пользователя
    await message.delete()
    
    msg_id = state["main_msg_id"]
    step = state.get("step")

    try:
        val = float(message.text.replace(",", "."))
        if step == "weight":
            state.update({"weight": val, "step": "time"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="⏱ **Шаг 3:** Введите время печати (в часах):")
        
        elif step == "time":
            state.update({"time": val, "step": "extra"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="➕ **Шаг 4:** Дополнительные расходы:", reply_markup=extra_menu())

        elif step == "manual_extra":
            state.update({"extra": val, "step": "quantity"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="🔢 **Шаг 5:** Выберите количество:", reply_markup=quantity_menu())

        elif step == "manual_qty":
            state.update({"quantity": int(val), "step": "margin"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="📈 **Шаг 6:** Выберите наценку:", reply_markup=margin_menu())

    except ValueError:
        pass # Игнорируем некорректный ввод или можно добавить alert

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
