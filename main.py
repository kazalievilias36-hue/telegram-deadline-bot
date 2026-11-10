import os
import time
import threading
from datetime import datetime, timedelta
import requests
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

user_langs = {}
# Құрылымы: {chat_id: {"Дүйсенбі": [{"text": "...", "time": datetime, "notified": False}, ...]}}
user_deadlines = {}

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
        "lang_set": "🇷🇺 Язык установлен! Отправьте задание с дедлайном (2026 год). Нажмите /add для просмотра дней.",
        "no_deadlines": "📭 У вас пока нет сохраненных дедлайнов.",
        "choose_day": "📅 Выберите день недели, чтобы посмотреть дедлайны:",
        "ai_prompt": "Ты помощник студента-архитектора. Текущий год — 2026. Определи день недели (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday) и точную дату/время дедлайна (в формате ДД.ММ.ГГГГ ЧЧ:ММ, если время не указано, ставь 23:59 текущей недели). Верни строго: ДЕНЬ_АНГЛ | ДД.ММ.ГГГГ ЧЧ:ММ | Описание задачи.",
    },
    "kz": {
        "lang_set": "🇰🇿 Тіл таңдалды! Дедлайны бар тапсырма жіберіңіз (2026 жыл). Күндерді көру үшін /add басыңыз.",
        "no_deadlines": "📭 Сізде әзірге сақталған дедлайндар жоқ.",
        "choose_day": "📅 Дедлайндарды көру үшін апта күнін басыңыз:",
        "ai_prompt": "Сен студенттің көмекшісісің. Жыл — 2026. Апта күнін (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday) және дедлайн уақытын (КК.АА.ЖЖЖЖ СС:ММ форматында, уақыт болмаса 23:59) анықта. Формат: АПТА_КҮНІ_АНГЛ | КК.АА.ЖЖЖЖ СС:ММ | Сипаттама.",
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

# /add немесе /deadlines базғанда 7 күннің түймелері шығады
@bot.message_handler(commands=['add', 'deadlines', 'tasks'])
def cmd_menu(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    for eng_day, kz_day in days_map.items():
        # Бар болса немесе бәрібір 7 күннің бәрін шығарамыз
        count = len(user_deadlines.get(chat_id, {}).get(kz_day, []))
        label = f"📌 {kz_day} ({count})" if count > 0 else f"⚪ {kz_day}"
        markup.add(telebot.types.InlineKeyboardButton(label, callback_data=f"day_{kz_day}"))
            
    bot.reply_to(message, LANG[lang]["choose_day"], reply_markup=markup)

# Апта күнін басқанда сол күннің дедлайндары шығады
@bot.callback_query_handler(func=lambda call: call.data.startswith('day_'))
def callback_day(call):
    chat_id = call.message.chat.id
    selected_day = call.data.split('_')[1]
    
    tasks = user_deadlines.get(chat_id, {}).get(selected_day, [])
    if tasks:
        text = f"📌 **{selected_day} күніне арналған дедлайндар (2026):**\n\n"
        for t in tasks:
            time_str = t['time'].strftime('%d.%m.%Y %H:%M') if t['time'] else "Уақыты көрсетілмеген"
            text += f"  - {t['text']} ⏰ ({time_str})\n"
    else:
        text = f"📭 {selected_day} күні ешқандай дедлайн жоқ."
        
    bot.answer_callback_query(call.id)
    bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown")

# Мәтін немесе фото арқылы тапсырма қабылдау және ИИ арқылы өңдеу
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
            
            parts = [p.strip() for p in ai_reply.split("|")]
            if len(parts) >= 3:
                eng_day = parts[0]
                date_str = parts[1]
                task_desc = parts[2]
                
                matched_kz_day = days_map.get(eng_day, "Жұма")
                
                # Уақытын парсить ету
                try:
                    deadline_time = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                except:
                    deadline_time = datetime.now() + timedelta(days=1)
                
                if chat_id not in user_deadlines:
                    user_deadlines[chat_id] = {}
                if matched_kz_day not in user_deadlines[chat_id]:
                    user_deadlines[chat_id][matched_kz_day] = []
                    
                user_deadlines[chat_id][matched_kz_day].append({
                    "text": task_desc,
                    "time": deadline_time,
                    "notified": False
                })
                
                bot.reply_to(message, f"✅ Сақталды **{matched_kz_day}** күніне:\n- {task_desc}\n⏰ Уақыты: {date_str}\n\nКүндерді көру үшін /add басыңыз.", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"🤖 {ai_reply}")
        else:
            bot.reply_to(message, f"ИИ қатесі: {response.status_code}")
    except Exception as e:
        bot.reply_to(message, f"Қате орын алды: {e}")

# --- 15 САҒАТ ҚАЛҒАНДА ЕСКЕРТУ ЖІБЕРЕТІН ФОНОВЫЙ ПОТОК ---
def reminder_worker():
    while True:
        now = datetime.now()
        for chat_id, days in user_deadlines.items():
            for day, tasks in days.items():
                for t in tasks:
                    if not t.get("notified", False) and t["time"]:
                        time_left = t["time"] - now
                        # Егер дедлайнға 15 сағат немесе одан аз уақыт қалса (және уақыты әлі өтпесе)
                        if timedelta(0) < time_left <= timedelta(hours=15):
                            try:
                                bot.send_message(
                                    chat_id,
                                    f"⏰ **НАПОМИНАНИЕ / ЕСКЕРТУ!**\n\nДедлайнға 15 сағат қалды!\n📌 Тапсырма ({day}):\n- {t['text']}\n⏰ Уақыты: {t['time'].strftime('%d.%m.%Y %H:%M')}",
                                    parse_mode="Markdown"
                                )
                                t["notified"] = True # Қайталап жібермес үшін белгілеу
                            except Exception as e:
                                print(f"Notification error: {e}")
        time.sleep(60) # Әр 1 минут сайын тексеріп тұрады

# --- FLASK СЕРВЕРІ ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive and running 24/7!"

def run_bot():
    bot.infinity_polling(none_stop=True, interval=0)

if __name__ == "__main__":
    # Ескерту жіберетін фондық ағынды қосу
    t_remind = threading.Thread(target=reminder_worker, daemon=True)
    t_remind.start()

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
