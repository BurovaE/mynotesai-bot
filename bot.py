from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import asyncio
import os
import json
import sys

# --- где лежат файлы рядом с bot.py ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTES_FILE = os.path.join(BASE_DIR, "notes.json")
EXPORT_FILE = os.path.join(BASE_DIR, "notes_export.txt")

# --- удобные функции работы с заметками ---
def load_notes() -> dict:
    if not os.path.exists(NOTES_FILE):
        return {}
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}

def save_notes(data: dict) -> None:
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- токен: 1) BOT_TOKEN  2) TELEGRAM_BOT_TOKEN  3) token.txt ---
def read_token_from_file(filename: str = "token.txt") -> str:
    p = os.path.join(BASE_DIR, filename)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""

TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or read_token_from_file("token.txt")
)

if not TOKEN:
    print("\n[!] Токен бота не найден.")
    print("Ищем в порядке: BOT_TOKEN → TELEGRAM_BOT_TOKEN → token.txt (рядом с bot.py)\n")
    sys.exit(0)

# --- клавиатуры ---
kb_main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мои заметки")],
        [KeyboardButton(text="Добавить заметку"), KeyboardButton(text="Удалить заметку")],
        [KeyboardButton(text="Экспорт заметок"), KeyboardButton(text="Очистить все заметки")]
    ],
    resize_keyboard=True
)

kb_confirm_clear = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да, очистить")],
        [KeyboardButton(text="Отмена")]
    ],
    resize_keyboard=True
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- состояние подтверждения очистки: {user_id: True} ---
pending_clear = {}

# /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name or 'друг'}! Это твой умный заметочник.",
        reply_markup=kb_main
    )

# Мои заметки (каждый раз читаем из файла)
@dp.message(F.text == "Мои заметки")
async def show_notes(message: types.Message):
    user_id = str(message.from_user.id)
    all_notes = load_notes()
    user_notes = all_notes.get(user_id, [])
    text = "\n".join(f"{i+1}. {n}" for i, n in enumerate(user_notes)) if user_notes else "У тебя пока нет заметок."
    await message.answer(text)

# Добавить заметку — просим текст
@dp.message(F.text == "Добавить заметку")
async def ask_note_text(message: types.Message):
    await message.answer("Напиши текст заметки:")

# Удалить заметку — показываем нумерованный список
@dp.message(F.text == "Удалить заметку")
async def ask_delete_index(message: types.Message):
    user_id = str(message.from_user.id)
    all_notes = load_notes()
    user_notes = all_notes.get(user_id, [])
    if not user_notes:
        await message.answer("У тебя нет заметок для удаления.")
        return
    text = "\n".join(f"{i+1}. {n}" for i, n in enumerate(user_notes))
    await message.answer(f"Выбери номер заметки для удаления:\n{text}")

# --- НОВОЕ: Экспорт заметок в notes_export.txt ---
@dp.message(F.text == "Экспорт заметок")
async def export_notes(message: types.Message):
    user_id = str(message.from_user.id)
    all_notes = load_notes()
    user_notes = all_notes.get(user_id, [])
    if not user_notes:
        await message.answer("У тебя пока нет заметок для экспорта.")
        return

    with open(EXPORT_FILE, "w", encoding="utf-8") as f:
        f.write("Ваши заметки:\n")
        for i, n in enumerate(user_notes, start=1):
            f.write(f"{i}. {n}\n")

    await message.answer("Экспорт готов: файл 'notes_export.txt' создан рядом с bot.py.")

# --- НОВОЕ: Очистить все заметки (с подтверждением) ---
@dp.message(F.text == "Очистить все заметки")
async def clear_all_request(message: types.Message):
    user_id = str(message.from_user.id)
    all_notes = load_notes()
    if not all_notes.get(user_id):
        await message.answer("У тебя нет заметок для очистки.")
        return

    pending_clear[user_id] = True
    await message.answer(
        "Ты уверена, что хочешь удалить ВСЕ свои заметки? Это действие нельзя отменить.",
        reply_markup=kb_confirm_clear
    )

@dp.message(F.text == "Да, очистить")
async def clear_all_confirm(message: types.Message):
    user_id = str(message.from_user.id)
    if not pending_clear.get(user_id):
        # Нажали подтверждение без запроса — игнорируем
        await message.answer("Нет ожидающего подтверждения.", reply_markup=kb_main)
        return

    all_notes = load_notes()
    if user_id in all_notes:
        all_notes.pop(user_id, None)
        save_notes(all_notes)

    pending_clear.pop(user_id, None)
    await message.answer("Все твои заметки удалены ✅", reply_markup=kb_main)

@dp.message(F.text == "Отмена")
async def clear_all_cancel(message: types.Message):
    user_id = str(message.from_user.id)
    pending_clear.pop(user_id, None)
    await message.answer("Действие отменено.", reply_markup=kb_main)

# Сохранение/удаление по контексту (как раньше)
@dp.message()
async def save_or_delete(message: types.Message):
    user_id = str(message.from_user.id)
    all_notes = load_notes()  # читаем актуальные

    # Если прислали число — трактуем как номер для удаления
    if message.text and message.text.isdigit():
        idx = int(message.text) - 1
        user_notes = all_notes.get(user_id, [])
        if 0 <= idx < len(user_notes):
            deleted = user_notes.pop(idx)
            if user_notes:
                all_notes[user_id] = user_notes
            else:
                all_notes.pop(user_id, None)
            save_notes(all_notes)
            await message.answer(f"Заметка '{deleted}' удалена.")
        else:
            await message.answer("Неверный номер заметки.")
        return

    # иначе — добавляем новую заметку
    if message.text:
        all_notes.setdefault(user_id, []).append(message.text)
        save_notes(all_notes)
        await message.answer(f"Заметка сохранена, {message.from_user.first_name or 'друг'}!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
