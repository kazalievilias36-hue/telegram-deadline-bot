import os
import threading
import requests
import telebot
from flask import Flask

# Получаем ключи из переменных окружения Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)

# --- ДАННЫЕ И СЛОВАРИ ---
user_langs = {}  # {chat_id: 'ru' / 'kz'}
waiting_for_deadline = {}  # {chat_id: True}

LANG = {
    "ru": {
        "choose_lang": "🇷🇺 Язык выбран / Выберите язык:",
        "lang_set": (
            "🇷🇺 Язык успешно установлен! Вы можете использовать"
            " аудио/фото/текст для добавления дедлайнов. Чтобы добавить"
            " новый дедлайн - напишите /add."
        ),
        "help": (
            "🤖 **Помощь**: \n/start - Сменить язык / /start (kz/ru)\n/deadline -"
            " Проверить сколько дней до дедлайна\n/add - Добавить новый"
            " дедлайн\n/tasks - Все дедлайны"
        ),
        "choose_day": (
            "📅 Выберите день недели (или отправьте фото/текст с заданием):"
        ),
        "no_deadlines": "📭 У вас пока нет сохраненных дедлайнов.",
        "deadline_for": "⏳ **Дедлайн для**: {date} ⏰ **Время**: {time}",
        "success_photo": (
            "📸 Бот успешно найден и успешно распределен на день! Нажмите"
            " /deadlines для проверки."
        ),
        "success_text": (
            "📝 Текстовые дедлайны успешно распределены по дням! Нажмите"
            " /deadlines для проверки."
        ),
        "tasks_all": "📋 **Ваши текущие дедлайны по дням**:\n",
        "ai_prompt": (
            "Ты умный помощник, который помогает студенту с учебой. Отвечай четко,"
            " понятно и по делу. Текущий язык: русский."
        ),
        "days": [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ],
        "days_eng": [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ],
    },
    "kz": {
        "choose_lang": "🇰🇿 Тілді таңдаңыз / Выберите язык:",
        "lang_set": (
            "🇰🇿 Тіл сәтті таңдалды! Енді сіз аудио, фото немесе мәтін арқылы"
            " тапсырма қоса аласыз. Жаңа дедлайн қосу үшін - /add түймесін"
            " басыңыз."
        ),
        "help": (
            "🤖 **Көмек**: \n/start - Тілді ауыстыру\n/deadline - Дедлайнға қанша"
            " уақыт қалғанын тексеру\n/add - Жаңа дедлайн қосу\n/tasks - Барлық"
            " дедлайндар"
        ),
        "choose_day": (
            "📅 Апта күнін таңдаңыз (немесе тапсырмасы бар фото/мәтін"
            " жіберіңіз):"
        ),
        "no_deadlines": "📭 Сізде әзірге сақталған дедлайндар жоқ.",
        "deadline_for": "⏳ **Дедлайн күні**: {date} ⏰ **Уақыт**: {time}",
        "success_photo": (
            "📸 Бот дизайн файлы мен дедлайн сәтті сақталды! Тексеру үшін"
            " /deadlines басыңыз."
        ),
        "success_text": (
            "📝 Тапсырмалар күндер бойынша сәтті бөлінді! Тексеру үшін"
            " /deadlines басыңыз."
        ),
        "tasks_all": "📋 **Барлық дедлайндар**:\n",
        "ai_prompt": (
            "Сен студентке оқуға көмектесетін ақылды көмекшісің. Нақты,"
            " түсінікті жауап бер. Қазіргі тіл: қазақша."
        ),
        "days": [
            "Дүйсенбі",
            "Сейсенбі",
            "Сәрсенбі",
            "Бейсенбі",
            "Жұма",
            "Сенбі",
            "Жексенбі",
        ],
        "days_eng": [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ],
    },
}


def get_lang(chat_id):
  return user_langs.get(chat_id, "ru")


# --- КОМАНДЫ БОТА ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
  chat_id = message.chat.id
  markup = telebot.types.InlineKeyboardMarkup()
  markup.add(
      telebot.types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
      telebot.types.InlineKeyboardButton(
          "🇰🇿 Қазақша", callback_data="lang_kz"
      ),
  )
  bot.send_message(
      chat_id,
      "Привет! Выберите язык / Сәлем! Тілді таңдаңыз:",
      reply_markup=markup,
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def callback_lang(call):
  chat_id = call.message.chat.id
  lang = call.data.split("_")[1]
  user_langs[chat_id] = lang
  bot.answer_callback_query(call.id)
  bot.edit_message_text(
      LANG[lang]["lang_set"], chat_id, call.message.message_id
  )


@bot.message_handler(commands=["add"])
def cmd_add(message):
  chat_id = message.chat.id
  lang = get_lang(chat_id)
  waiting_for_deadline[chat_id] = True
  bot.reply_to(message, LANG[lang]["choose_day"])


@bot.message_handler(commands=["deadlines", "tasks"])
def cmd_deadlines(message):
  chat_id = message.chat.id
  lang = get_lang(chat_id)
  bot.reply_to(message, LANG[lang]["no_deadlines"])


@bot.message_handler(commands=["help"])
def cmd_help(message):
  chat_id = message.chat.id
  lang = get_lang(chat_id)
  bot.reply_to(message, LANG[lang]["help"], parse_mode="Markdown")


# --- ОБРАБОТКА СООБЩЕНИЙ И OPENROUTER ---
@bot.message_handler(
    func=lambda message: True, content_types=["text", "photo"]
)
def handle_all_messages(message):
  chat_id = message.chat.id
  lang = get_lang(chat_id)

  # Если пользователь отправляет текст для дедлайна после /add
  if waiting_for_deadline.get(chat_id):
    waiting_for_deadline[chat_id] = False
    bot.reply_to(message, LANG[lang]["success_text"])
    return

  # Запрос к OpenRouter ИИ
  user_text = message.text or message.caption or "Привет"
  headers = {
      "Authorization": f"Bearer {OPENROUTER_API_KEY}",
      "Content-Type": "application/json",
  }
  data = {
      "model": "deepseek/deepseek-chat",  # или другая модель по вашему выбору
      "messages": [
          {"role": "system", "content": LANG[lang]["ai_prompt"]},
          {"role": "user", "content": user_text},
      ],
  }

  try:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=data,
        headers=headers,
        timeout=30,
    )
    if response.status_code == 200:
      res_json = response.json()
      ai_reply = res_json["choices"][0]["message"]["content"]
      bot.reply_to(message, ai_reply)
    else:
      bot.reply_to(
          message,
          f"Ошибка обращения к ИИ (код {response.status_code}). Попробуйте"
          " позже.",
      )
  except Exception as e:
    bot.reply_to(message, f"Произошла ошибка при запросе к нейросети: {e}")


# --- НАСТРОЙКА ВЕБ-СЕРВЕРА FLASK ДЛЯ RENDER ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is alive and running 24/7!"


def run_bot():
  bot.infinity_polling(none_stop=True, interval=0)


if __name__ == "__main__":
  # Запускаем Telegram-бота в фоновом потоке
  bot_thread = threading.Thread(target=run_bot)
  bot_thread.daemon = True
  bot_thread.start()

  # Запускаем веб-сервер Flask на порту Render
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
