import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Импорт твоих модулей (проверь, что в db.py функция get_history возвращает список кортежей)
try:
    from calc import calculate_price
    from db import init_db, save_history, get_history
except ImportError:
    # Заглушки для работы кода, если файлов нет под рукой
    def calculate_price(**kwargs): return {"total": 110}
    def init_db(): pass
    def save_history(*args): pass
    def get_history(user_id): return [(1, 40, 4, 110)] # id, вес, время, итого

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

def plastic_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="PLA — 129₪", callback_data="pl_129_PLA")],
        [InlineKeyboardButton(text="PETG — 139₪", callback_data="pl_139_PETG")],
        [InlineKeyboardButton(text="ABS — 120₪", callback_data="pl_120_ABS")],
        [InlineKeyboardButton(text="TPU — 160₪", callback_data="pl_160_TPU")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

# (Остальные меню: extra_menu, quantity_menu, margin_menu, delivery_menu остаются такими же)
def extra_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="LED (+20₪)", callback_data="ex_20")],
        [InlineKeyboardButton(text="Своя сумма", callback_data="ex_manual")],
        [InlineKeyboardButton(text="Без допов", callback_data="ex_0")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

def quantity_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 шт", callback_data="qty_1"), InlineKeyboardButton(text="5 шт", callback_data="qty_5")],
        [InlineKeyboardButton(text="10 шт", callback_data="qty_10"), InlineKeyboardButton(text="Своё число", callback_data="qty_manual")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

def margin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обычный (40%)", callback_data="mr_40")],
        [InlineKeyboardButton(text="Шабат (70%)", callback_data="mr_70")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

def delivery_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да (50₪)", callback_data="dl_50")],
        [InlineKeyboardButton(text="Нет (0₪)", callback_data="dl_0")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

# --- Обработка Истории ---

@dp.callback_query(F.data == "history")
async def show_history(callback: types.CallbackQuery):
    rows = get_history(callback.from_user.id)
    
    if not rows:
        await callback.answer("История пуста", show_alert=True)
        return

    text = "📦 **Последние 10 расчетов:**\n\n"
    # Форматируем вывод (индексы зависят от твоей структуры БД)
    for r in rows[-10:]:
        text += f"🔹 {r[1]}г / {r[2]}ч — **{r[3]}₪**\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В меню", callback_data="cancel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- Основная логика (Callback) ---

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("📦 **3dPrintCalc**\nВыберите действие:", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "new")
async def new_calc(callback: types.CallbackQuery):
    user_state[callback.from_user.id] = {"main_msg_id": callback.message.message_id, "step": "plastic"}
    await callback.message.edit_text("🔵 **Шаг 1:** Выберите пластик:", reply_markup=plastic_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "cancel")
async def back_to_main(callback: types.CallbackQuery):
    user_state.pop(callback.from_user.id, None)
    await callback.message.edit_text("📦 **3dPrintCalc**\nВыберите действие:", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("pl_"))
async def set_plastic(callback: types.CallbackQuery):
    _, price, name = callback.data.split("_")
    state = user_state.get(callback.from_user.id)
    if state:
        state.update({"plastic_price": int(price), "plastic_name": name, "step": "weight"})
        await callback.message.edit_text("⚖️ **Шаг 2:** Введите вес (г):")

@dp.callback_query(F.data.startswith("ex_"))
async def set_extra(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if not state: return
    if callback.data == "ex_manual":
        state["step"] = "manual_extra"
        await callback.message.edit_text("💰 Доп. расходы (₪):")
    else:
        state.update({"extra": int(callback.data.split("_")[1]), "step": "quantity"})
        await callback.message.edit_text("🔢 **Шаг 5:** Количество:", reply_markup=quantity_menu())

@dp.callback_query(F.data.startswith("qty_"))
async def set_qty(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if not state: return
    if callback.data == "qty_manual":
        state["step"] = "manual_qty"
        await callback.message.edit_text("🔢 Введите количество:")
    else:
        state.update({"quantity": int(callback.data.split("_")[1]), "step": "margin"})
        await callback.message.edit_text("📈 **Шаг 6:** Наценка:", reply_markup=margin_menu())

@dp.callback_query(F.data.startswith("mr_"))
async def set_margin(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if state:
        state.update({"profit_percent": int(callback.data.split("_")[1]) / 100, "step": "delivery"})
        await callback.message.edit_text("🚚 **Шаг 7:** Доставка?", reply_markup=delivery_menu())

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
    
    save_history(user_id, state["weight"], state["time"], res["total"])
    subtotal = res["total"] - state["delivery"]

    summary = (
        f"🛠 Пластик: {state['plastic_name']}\n⚖️ Вес: {state['weight']}г\n⏱ Время: {state['time']}ч\n"
        f"📦 Кол-во: {state['quantity']} шт.\n💵 Стоимость: {subtotal}₪\n🚚 Доставка: {state['delivery']}₪\n\n"
        f"💰 **Итого: {res['total']}₪**"
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
        # Отправляем новое сообщение, которое можно переслать
        await callback.message.answer(f"```{state['final_text']}```", parse_mode="Markdown")
        await callback.answer("Готово к копированию")

# --- Ввод текста (с удалением сообщений пользователя) ---

@dp.message()
async def handle_input(message: types.Message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    if not state or "main_msg_id" not in state: return

    await message.delete() # Удаляем цифру, которую ввел пользователь
    msg_id = state["main_msg_id"]
    step = state.get("step")

    try:
        val = float(message.text.replace(",", "."))
        if step == "weight":
            state.update({"weight": val, "step": "time"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="⏱ **Шаг 3:** Введите время (ч):")
        elif step == "time":
            state.update({"time": val, "step": "extra"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="➕ **Шаг 4:** Доп. расходы:", reply_markup=extra_menu())
        elif step == "manual_extra":
            state.update({"extra": val, "step": "quantity"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="🔢 **Шаг 5:** Количество:", reply_markup=quantity_menu())
        elif step == "manual_qty":
            state.update({"quantity": int(val), "step": "margin"})
            await bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="📈 **Шаг 6:** Наценка:", reply_markup=margin_menu())
    except ValueError:
        pass

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
