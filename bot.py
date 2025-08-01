import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import *

env_path = Path('.') / '.env'
load_dotenv(env_path)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL") 
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

# Хранение контекста диалогов
user_sessions = {}

# Клавиатура
reply_keyboard = ReplyKeyboardMarkup(
    [["Новый диалог"]],
    resize_keyboard=True,
)

def save_sessions():
    """Сохраняет сессии в файл"""
    with open('sessions.json', 'w', encoding='utf-8') as f:
        json.dump(user_sessions, f, ensure_ascii=False)

def load_sessions():
    """Загружает сессии из файла"""
    try:
        with open('sessions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "ℹДоступные команды:\n"
        "/start - начать новый диалог\n"
        "/help - показать эту справку\n\n"
        "Кнопки:\n"
        "«Новый диалог» - очистить историю сообщений\n"
    )
    await update.message.reply_text(help_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user_sessions[user_id] = [
        {"role": "system", "content": "Отвечай на русском языке."}
    ]
    save_sessions()
    
    welcome_msg = (
        "Просто напиши мне сообщение, и я отвечу.\n"
        "Используй кнопку 'Новый диалог' чтобы начать заново."
    )
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_keyboard)

async def reset_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс диалога для пользователя"""
    user_id = update.effective_user.id
    user_sessions[user_id] = [
        {"role": "system", "content": "Отвечай на русском языке."}
    ]
    save_sessions()
    await update.message.reply_text("Диалог очищен. Можете начать новый!", reply_markup=reply_keyboard)

async def get_gpt_response(messages: list) -> str:
    """Запрос к OpenRouter API с сохранением контекста"""
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'X-Title': 'Telegram AI Assistant'
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        logging.debug(f"Отправка запроса: {json.dumps(payload, ensure_ascii=False)}")
        response = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            error_msg = f"API error {response.status_code}: {response.text}"
            logging.error(error_msg)
            return None
            
        data = response.json()
        return data["choices"][0]["message"]["content"]
        
    except Exception as e:
        logging.error(f"Ошибка API: {str(e)}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с сохранением контекста"""
    user_id = update.effective_user.id
    user_message = update.message.text.strip()

    if user_id not in user_sessions:
        await start(update, context)
        return

    # Обработка команды нового диалога
    if user_message.lower() in ["новый диалог", "новый сеанс"]:
        await reset_dialog(update, context)
        return

    user_sessions[user_id].append({"role": "user", "content": user_message})

    try:
        await update.message.chat.send_action(action="typing")
        response = await get_gpt_response(user_sessions[user_id])
        
        if not response:
            raise Exception("API не вернул ответ")

        user_sessions[user_id].append({"role": "assistant", "content": response})
        save_sessions()
        
        await update.message.reply_text(response, reply_markup=reply_keyboard)
        
    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        await update.message.reply_text(
            "Ошибка обработки запроса. Попробуйте позже.",
            reply_markup=reply_keyboard
        )

def main():
    """Запуск бота"""
    # Загрузка сохраненных сессий
    global user_sessions
    user_sessions = load_sessions()
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Создание и запуск бота
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен с поддержкой контекста...")
    application.run_polling()

if __name__ == "__main__":
    main()