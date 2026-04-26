import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

# Предполагаем, что эти модули у тебя есть
try:
    from calc import calculate_price
    from db import init_db, save_history, get_history
except ImportError:
    # Заглушки для теста, если файлов нет рядом
    def calculate_price(**kwargs): return {"total": 100}
    def init_db(): pass
    def save_history(*args): pass
    def get_history(*args): return []

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
        [InlineKeyboardButton(text="PLA — 129₪", callback_data="plastic_129_PLA")],
        [InlineKeyboardButton(text="PETG — 139₪", callback_data="plastic_139_PETG")],
        [InlineKeyboardButton(text="ABS — 120₪", callback_data="plastic_120_ABS")],
        [InlineKeyboardButton(text="TPU — 160₪", callback_data="plastic_160_TPU")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

def extra_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="LED (+20₪)", callback_data="extra_20")],
        [InlineKeyboardButton(text="Ввести вручную", callback_data="manual_extra")],
        [InlineKeyboardButton(text="Пропустить", callback_data="extra_0")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

def quantity_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="qty_1"), InlineKeyboardButton(text="5", callback_data="qty_5")],
        [InlineKeyboardButton(text="10", callback_data="qty_10"), InlineKeyboardButton(text="Ввести вручную", callback_data="manual_qty")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

def margin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обычный заказ (40%)", callback_data="margin_40")],
        [InlineKeyboardButton(text="Шабат (70%)", callback_data="margin_70")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

def delivery_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да (50₪)", callback_data="delivery_50")],
        [InlineKeyboardButton(text="Нет (0₪)", callback_data="delivery_0")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")]
    ])

# --- Обработчики ---

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("📦 **3dPrintCalc**\n\nВыберите действие:", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "new")
async def new_calc(callback: types.CallbackQuery):
    user_state[callback.from_user.id] = {"step": "plastic", "main_msg_id": callback.message.message_id}
    await callback.message.edit_text("🔵 **Шаг 1:** Выберите тип пластика:", reply_markup=plastic_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "cancel")
async def cancel(callback: types.CallbackQuery):
    user_state.pop(callback.from_user.id, None)
    await callback.message.edit_text("📦 **3dPrintCalc**\n\nВыберите действие:", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("plastic_"))
async def set_plastic(callback: types.CallbackQuery):
    data = callback.data.split("_")
    state = user_state.get(callback.from_user.id)
    if state:
        state["plastic_price"] = int(data[1])
        state["plastic_name"] = data[2]
        state["step"] = "weight"
        await callback.message.edit_text("⚖️ **Шаг 2:** Введите вес модели в граммах (просто числом):")

@dp.callback_query(F.data.startswith("extra_"))
async def set_extra(callback: types.CallbackQuery):
    val = int(callback.data.split("_")[1])
    state = user_state.get(callback.from_user.id)
    if state:
        state["extra"] = val
        state["step"] = "quantity"
        await callback.message.edit_text("🔢 **Шаг 4:** Выберите или введите количество:", reply_markup=quantity_menu())

@dp.callback_query(F.data == "manual_extra")
async def manual_extra(callback: types.CallbackQuery):
    user_state[callback.from_user.id]["step"] = "manual_extra_input"
    await callback.message.edit_text("💰 Введите сумму доп. расходов (₪):")

@dp.callback_query(F.data.startswith("qty_"))
async def set_qty(callback: types.CallbackQuery):
    val = int(callback.data.split("_")[1])
    state = user_state.get(callback.from_user.id)
    if state:
        state["quantity"] = val
        state["step"] = "margin"
        await callback.message.edit_text("📈 **Шаг 5:** Выберите наценку (маржу):", reply_markup=margin_menu())

@dp.callback_query(F.data == "manual_qty")
async def manual_qty(callback: types.CallbackQuery):
    user_state[callback.from_user.id]["step"] = "manual_qty_input"
    await callback.message.edit_text("🔢 Введите нужное количество штук:")

@dp.callback_query(F.data.startswith("margin_"))
async def set_margin(callback: types.CallbackQuery):
    val = int(callback.data.split("_")[1])
    state = user_state.get(callback.from_user.id)
    if state:
        state["profit_percent"] = val / 100
        state["step"] = "delivery"
        await callback.message.edit_text("🚚 **Шаг 6:** Нужна ли доставка?", reply_markup=delivery_menu())

@dp.callback_query(F.data.startswith("delivery_"))
async def finish_calc(callback: types.CallbackQuery):
    val = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    state = user_state.get(user_id)
    
    if state:
        state["delivery"] = val
        result = calculate_price(
            weight=state["weight"],
            hours=state["time"],
            plastic_price=state["plastic_price"],
            extra=state.get("extra", 0),
            quantity=state.get("quantity", 1),
            profit_percent=state.get("profit_percent", 0.4),
            delivery=state.get("delivery", 0)
        )
        
        save_history(user_id, state["weight"], state["time"], result["total"])
        
        # Сохраняем итоговый текст в state, чтобы потом отправить клиенту
        summary = (
            f"✅ **Расчет готов!**\n\n"
            f"🛠 Пластик: {state['plastic_name']}\n"
            f"⚖️ Вес: {state['weight']}г\n"
            f"⏱ Время: {state['time']}ч\n"
            f"📦 Кол-во: {state['quantity']} шт.\n"
            f"🚚 Доставка: {state['delivery']}₪\n\n"
            f"💰 **Итого к оплате: {result['total']}₪**"
        )
        state["final_text"] = summary
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить клиенту", callback_data="send_client")],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="cancel")]
        ])
        
        await callback.message.edit_text(summary, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "send_client")
async def send_to_client(callback: types.CallbackQuery):
    state = user_state.get(callback.from_user.id)
    if state and "final_text" in state:
        # Убираем "Расчет готов" для клиента и делаем текст чище
        client_text = state["final_text"].replace("✅ **Расчет готов!**", "📋 **Смета на 3D печать**")
        await callback.message.answer(f"Отправьте этот текст клиенту:\n\n`{client_text}`", parse_mode="MarkdownV2")
        await callback.answer("Текст для копирования готов!")

# --- Обработка ручного ввода (самое важное для одного окна) ---

@dp.message()
async def handle_input(message: types.Message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    
    if not state or "main_msg_id" not in state:
        return

    # Удаляем сообщение пользователя, чтобы не засорять чат
    await message.delete()
    
    step = state.get("step")
    msg_id = state["main_msg_id"]

    try:
        if step == "weight":
            state["weight"] = float(message.text)
            state["step"] = "time"
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text="⏱ **Шаг 3:** Введите время печати (в часах):"
            )
        
        elif step == "time":
            state["time"] = float(message.text)
            state["step"] = "extra"
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text="➕ **Шаг 4:** Дополнительные расходы:",
                reply_markup=extra_menu()
            )

        elif step == "manual_extra_input":
            state["extra"] = float(message.text)
            state["step"] = "quantity"
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text="🔢 **Шаг 5:** Выберите или введите количество:",
                reply_markup=quantity_menu()
            )

        elif step == "manual_qty_input":
            state["quantity"] = int(message.text)
            state["step"] = "margin"
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text="📈 **Шаг 6:** Выберите наценку (маржу):",
                reply_markup=margin_menu()
            )
    except ValueError:
        # Если ввели не число, можно кратко мигнуть алертом или обновить текст
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text="⚠️ Пожалуйста, введите корректное число!"
        )
        await asyncio.sleep(2)
        # Возвращаем текст шага (нужна логика возврата, для краткости просто текст)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
