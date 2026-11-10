import os
import threading
import requests
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# --- ХРАНИЛИЩЕ ДАННЫХ ---
user_langs = {}  # {chat_id: 'ru' / 'kz'}
user_deadlines = {}  # {chat_id: { "Понедельник": [...], "Вторник": [...] }}


LANG = {
    "ru": {
        "choose_lang": "🇷🇺 Язык выбран / Выберите язык:",
        "lang_set": (
            "🇷🇺 Язык успешно установлен! Отправьте фото или текст с заданием,"
            " и я распределю его по дням недели. Команды: /add, /deadlines"
        ),
        "help": (
            "🤖 **Помощь**: \n/start - Сменить язык\n/deadlines - Посмотреть"
            " все дедлайны по дням\n/add - Добавить новый дедлайн"
        ),
        "no_deadlines": "📭 У вас пока нет сохраненных дедлайнов.",
        "added_success": (
            "✅ Дедлайн успешно распознан и добавлен в ваш график!"
        ),
        "ai_prompt": (
            "Ты умный помощник для студента-архитектора. Текущий год — 2026."
            " Пользователь присылает задание или дедлайн. Твоя задача:"
            " 1. Определить день недели (Понедельник, Вторник, Среда, Четверг,"
            " Пятница, Суббота, Воскресенье)."
            " 2. Сформировать короткое понятное описание задачи."
            " 3. Вернуть ответ строго в формате: ДЕНЬ_НЕДЕЛИ | Описание задачи."
            " Например: Понедельник | Сдать чертеж павильона 1:100"
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
    },
    "kz": {
        "choose_lang": "🇰🇿 Тілді таңдаңыз / Выберите язык:",
        "lang_set": (
            "🇰🇿 Тіл сәтті таңдалды! Тапсырмасы бар фото немесе мәтін"
            " жіберіңіз, мен оны апта күндері бойынша бөлемін. Командалар:"
            " /add, /deadlines"
        ),
        "help": (
            "🤖 **Көмек**: \n/start - Тілді ауыстыру\n/deadlines - Барлық"
            " дедлайндарды көру\n/add - Жаңа дедлайн қосу"
        ),
        "no_deadlines": "📭 Сізде әзірге сақталған дедлайндар жоқ.",
        "added_success": (
            "✅ Дедлайн сәтті анықталып, кестеңізге қосылды!"
        ),
        "ai_prompt": (
            "Сен студентке көмектесетін ақылды көмекшісің. Қазіргі жыл — 2026."
            " Пайдаланушы тапсырма немесе дедлайн жібереді. Міндетің:"
            " 1. Апта күнін анықтау (Дүйсенбі, Сейсенбі, Сәрсенбі, Бейсенбі,"
            " Жұма, Сенбі, Жексенбі)."
            " 2. Қысқаша түсінікті сипаттама жазу."
            " 3. Жауапты мына форматта қайтару: АПТА_КҮНІ | Сипаттамасы."
            " Мысалы: Дүйсенбі | Павильон сызбасын өткізу"
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
    },
}


def get_lang(chat_id):
  return user_langs.get(chat_id, "ru")


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
  bot.reply_to(
      message,
      (
          "📅 Отправьте текст задания или фото с дедлайном, и я распределю его"
          " по дням недели (2026 год):"
      ),
  )


@bot.message_handler(commands=["deadlines", "tasks"])
def cmd_deadlines(message):
  chat_id = message.chat.id
  lang = get_lang(chat_id)

  if chat_id not in user_deadlines or not user_deadlines[chat_id]:
    bot.reply_to(message, LANG[lang]["no_deadlines"])
    return

  response_text = "📋 **Ваши дедлайны по дням недели (2026):**\n\n"
  for day in LANG[lang]["days"]:
    tasks = user_deadlines[chat_id].get(day, [])
    if tasks:
      response_text += f"📌 **{day}:**\n"
      for t in tasks:
        response_text += f"  - {t}\n"
      response_text += "\n"

  bot.reply_to(message, response_text, parse_mode="Markdown")


@bot.message_handler(
    func=lambda message: True, content_types=["text", "photo"]
)
def handle_all_messages(message):
  chat_id = message.chat.id
  lang = get_lang(chat_id)

  user_text = message.text or message.caption
  if not user_text and message.photo:
    user_text = "Фото архитектурного проекта или задания с дедлайном."

  if not user_text:
    return

  headers = {
      "Authorization": f"Bearer {OPENROUTER_API_KEY}",
      "Content-Type": "application/json",
  }

  prompt = (
      f"{LANG[lang]['ai_prompt']}\n\nВходные данные от студента:"
      f" '{user_text}'"
  )

  data = {
      "model": "deepseek/deepseek-chat",
      "messages": [{"role": "user", "content": prompt}],
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
      ai_reply = res_json["choices"][0]["message"]["content"].strip()

      # Пытаемся разобрать ответ вида: День | Задача
      if "|" in ai_reply:
        parts = ai_reply.split("|", 1)
        day_part = parts[0].strip()
        task_part = parts[1].strip()

        # Ищем точное совпадение дня недели
        matched_day = None
        for d in LANG[lang]["days"]:
          if d.lower() in day_part.lower():
            matched_day = d
            break

        if not matched_day:
          matched_day = LANG[lang]["days"][0]  # По умолчанию понедельник

        if chat_id not in user_deadlines:
          user_deadlines[chat_id] = {}
        if matched_day not in user_deadlines[chat_id]:
          user_deadlines[chat_id][matched_day] = []

        user_deadlines[chat_id][matched_day].append(task_part)
        bot.reply_to(
            message,
            f"✅ Сохранено на **{matched_day}**:\n- {task_part}\n\nНажмите"
            " /deadlines для просмотра всего расписания.",
            parse_mode="Markdown",
        )
      else:
        bot.reply_to(message, f"🤖 {ai_reply}")
    else:
      bot.reply_to(
          message, f"Ошибка обращения к ИИ (код {response.status_code})."
      )
  except Exception as e:
    bot.reply_to(message, f"Произошла ошибка: {e}")


# --- FLASK ДЛЯ RENDER ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is alive and running 24/7!"


def run_bot():
  bot.infinity_polling(none_stop=True, interval=0)


if __name__ == "__main__":
  bot_thread = threading.Thread(target=run_bot)
  bot_thread.daemon = True
  bot_thread.start()

  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
