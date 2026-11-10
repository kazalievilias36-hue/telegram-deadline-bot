import os
import requests
import telebot
from flask import Flask

# Токендерді Render ортасынан (Environment) аламыз
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

user_langs = {}  # {chat_id: 'ru' / 'kz'}
user_deadlines = {}  # {chat_id: { "Дүйсенбі": [...], "Сейсенбі": [...] }}

# Апта күндерінің сөздігі
days_map = {
    "Monday": "Дүйсенбі",
    "Tuesday": "Сейсенбі",
    "Wednesday": "Сәрсенбі",
    "Thursday": "Бейсенбі",
    "Friday": "Жұма",
    "Saturday": "Сенбі",
    "Sunday": "Жексенбі",
}

LANG = {
    "ru": {
        "lang_set": "🇷🇺 Язык установлен! Отправьте задание, и я распределю его по дням (2026 год). Нажмите /tasks для просмотра.",
        "no_deadlines": "📭 У вас пока нет сохраненных дедлайнов.",
        "choose_day": "📅 Выберите день недели, чтобы посмотреть дедлайны:",
        "ai_prompt": "Ты помощник студента-архитектора. Год 2026. Определи день недели (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday) и суть задачи. Верни строго: ДЕНЬ_НА_АНГЛИЙСКОМ | Описание. Пример: Friday | Сдать чертеж",
    },
    "kz": {
        "lang_set": "🇰🇿 Тіл таңдалды! Тапсырма жіберіңіз, мен оны апта күндеріне бөлемін (2026 жыл). /tasks басыңыз.",
        "no_deadlines": "📭 Сізде әзірге сақталған дедлайндар жоқ.",
        "choose_day": "📅 Дедлайндарды көру үшін апта күнін таңдаңыз:",
        "ai_prompt": "Сен студентке көмектесушісің. Жыл 2026. Апта күнін анықта (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday) және сипаттама жаз. Формат: АПТА_КҮНІ_АҒЫЛШЫНША | Сипаттама. Мысал: Friday | Сызба тапсыру",
    }
}

def get_lang(chat_id):
    return user_langs.get(chat_id, "ru")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        telebot.types.InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kz")
    )
    bot.send_message(chat_id, "Привет! Выберите язык / Сәлем! Тілді таңдаңыз:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def callback_lang(call):
    chat_id = call.message.chat.id
    lang = call.data.split('_')[1]
    user_langs[chat_id] = lang
    bot.answer_callback_query(call.id)
    bot.edit_message_text(LANG[lang]["lang_set"], chat_id, call.message.message_id)

@bot.message_handler(commands=['deadlines', 'tasks'])
def cmd_deadlines(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    if chat_id not in user_deadlines or not user_deadlines[chat_id]:
        bot.reply_to(message, LANG[lang]["no_deadlines"])
        return

    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    for eng_day, kz_day in days_map.items():
        if user_deadlines[chat_id].get(kz_day):
            markup.add(telebot.types.InlineKeyboardButton(f"📌 {kz_day}", callback_data=f"day_{kz_day}"))
            
    bot.reply_to(message, LANG[lang]["choose_day"], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('day_'))
def callback_day(call):
    chat_id = call.message.chat.id
    selected_day = call.data.split('_')[1]
    
    tasks = user_deadlines.get(chat_id, {}).get(selected_day, [])
    if tasks:
        text = f"📌 **{selected_day} күніне арналған дедлайндар (2026):**\n\n"
        for t in tasks:
            text += f"  - {t}\n"
    else:
        text = f"📭 {selected_day} күні ешқандай дедлайн жоқ."
        
    bot.answer_callback_query(call.id)
    bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_all_messages(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    user_text = message.text or message.caption
    if not user_text and message.photo:
        user_text = "Фото архитектурного задания."
        
    if not user_text:
        return

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"{LANG[lang]['ai_prompt']}\n\nЗадание: '{user_text}'"
    
    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            ai_reply = res_json['choices'][0]['message']['content'].strip()
            
            if "|" in ai_reply:
                parts = ai_reply.split("|", 1)
                eng_day = parts[0].strip()
                task_part = parts[1].strip()
                
                matched_kz_day = days_map.get(eng_day, "Жұма")
                
                if chat_id not in user_deadlines:
                    user_deadlines[chat_id] = {}
                if matched_kz_day not in user_deadlines[chat_id]:
                    user_deadlines[chat_id][matched_kz_day] = []
                    
                user_deadlines[chat_id][matched_kz_day].append(task_part)
                bot.reply_to(message, f"✅ Сақталды **{matched_kz_day}** күніне:\n- {task_part}\n\nБарлық кестені көру үшін /tasks басыңыз.", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"🤖 {ai_reply}")
        else:
            bot.reply_to(message, f"ИИ қатесі: {response.status_code}")
    except Exception as e:
        bot.reply_to(message, f"Қате орын алды: {e}")

# --- FLASK СЕРВЕРІ (Render үшін міндетті) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive and running 24/7!"

import threading
def run_bot():
    bot.infinity_polling(none_stop=True, interval=0)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
