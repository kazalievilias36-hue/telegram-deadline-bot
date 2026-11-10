import os
import threading
import telebot
from flask import Flask

# Получаем ключи из переменных окружения Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)


# --- Обработчики команд бота ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
  bot.reply_to(
      message,
      "Привет! Я твой бот-помощник с ИИ. Напиши мне что-нибудь, и я отвечу.",
  )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  # Здесь вы можете добавить свой код запроса к OpenRouter
  user_text = message.text
  bot.reply_to(
      message, f"Я получил твое сообщение: {user_text}. Скоро здесь будет ответ ИИ!"
  )


# --- Настройка веб-сервера Flask для Render ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is alive and running 24/7!"


def run_bot():
  bot.infinity_polling()


if __name__ == "__main__":
  # Запускаем Telegram-бота в отдельном потоке
  bot_thread = threading.Thread(target=run_bot)
  bot_thread.daemon = True
  bot_thread.start()

  # Запускаем Flask-сервер на порту, который требует Render
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
