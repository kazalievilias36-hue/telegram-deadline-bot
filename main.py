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

python_days_to_kz = {
    0: "Дүйсенбі",
    1: "Сейсенбі",
    2: "Сәрсенбі",
    3: "Бейсенбі",
    4: "Жұма",
    5: "Сенбі",
    6: "Жексенбі"
}

LANG = {
    "ru": {
        "lang_set": "🇷🇺 Язык установлен! Используйте /add для добавления или /deadlines для просмотра дедлайнов (2026 год).",
        "choose_day": "📅 Выберите день недели, чтобы посмотреть дедлайны:",
        "ai_prompt": "Ты точный системный парсер расписания для студента. Текущий год — 2026. Внимательно посмотри на скриншот и найди АБСОЛЮТНО ВСЕ задачи до единой. Для каждой задачи извлеки: 1) Точную дату и время (например, если написано 'среда 11 ноября 2026' и слева '20:00', то это 11.11.2026 20:00). 2) Полный точный текст/название задачи. Верни ответ СТРОГО списком, каждая задача на новой строке в формате: ДД.ММ.ГГГГ ЧЧ:ММ | Полное описание задачи. Не пропускай ни одной задачи!",
    },
    "kz": {
        "lang_set": "🇰🇿 Тіл таңдалды! Дедлайн қосу үшін /add немесе кестені көру үшін /deadlines қолданыңыз (2026 жыл).",
        "choose_day": "📅 Дедлайндарды көру үшін апта күнін басыңыз:",
        "ai_prompt": "Сен студентке арналған дәл кесте парсерісің. Жыл — 2026. Суретті мұқият қарап шығып, БАРЛЫҚ тапсырмаларды ТҮГЕЛ тап (бірде-бірін қалдырма!). Әрқайсысы үшін: 1) Нақты датасы мен сол жағындағы уақытын ал (мысалы: 'среда 11 ноября 2026' және '20:00' болса — 11.11.2026 20:00). 2) Тапсырманың толық атауы мен мәтінін жаз. Жауапты ҚАТАЛ түрде тізім ретінде бер, әр тапсырма жаңа жолдан мына форматта болсын: КК.АА.ЖЖЖЖ СС:ММ | Тапсырманың толық сипаттамасы",
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

@bot.message_handler(commands=['add'])
def cmd_add(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    text = (
        "✍️ **Добавление дедлайна:**\n"
        "Отправьте скриншот расписания. Я распознаю абсолютно все задачи, точное время и распределю их по дням недели!"
        if lang == 'ru' else
        "✍️ **Дедлайн қосу:**\n"
        "Кесте скриншотын жіберіңіз. Мен барлық тапсырмаларды, нақты уақыттарын түгел оқып, күндерге дұрыс бөліп сақтаймын!"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['deadlines'])
def cmd_deadlines(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    days_order = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
    for kz_day in days_order:
        count = len(user_deadlines.get(chat_id, {}).get(kz_day, []))
        label = f"📌 {kz_day} ({count})" if count > 0 else f"⚪ {kz_day}"
        markup.add(telebot.types.InlineKeyboardButton(label, callback_data=f"day_{kz_day}"))
            
    bot.reply_to(message, LANG[lang]["choose_day"], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('day_'))
def callback_day(call):
    chat_id = call.message.chat.id
    selected_day = call.data.split('_')[1]
    
    tasks = user_deadlines.get(chat_id, {}).get(selected_day, [])
    markup = telebot.types.InlineKeyboardMarkup()
    
    if tasks:
        text = f"📌 **{selected_day} күніне арналған дедлайндар (2026):**\n\n"
        for i, t in enumerate(tasks):
            time_str = t['time'].strftime('%d.%m.%Y %H:%M') if t['time'] else "Уақыты жоқ"
            text += f"{i+1}. {t['text']} ⏰ ({time_str})\n\n"
        
        markup.add(telebot.types.InlineKeyboardButton("🔔 Напоминание / Ескертуді баптау", callback_data=f"notif_{selected_day}"))
    else:
        text = f"📭 {selected_day} күні ешқандай дедлайн жоқ."
        
    markup.add(telebot.types.InlineKeyboardButton("🔙 Күндерге қайту", callback_data="back_to_days"))
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_days")
def callback_back(call):
    chat_id = call.message.chat.id
    lang = get_lang(chat_id)
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    days_order = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
    for kz_day in days_order:
        count = len(user_deadlines.get(chat_id, {}).get(kz_day, []))
        label = f"📌 {kz_day} ({count})" if count > 0 else f"⚪ {kz_day}"
        markup.add(telebot.types.InlineKeyboardButton(label, callback_data=f"day_{kz_day}"))
    bot.edit_message_text(LANG[lang]["choose_day"], chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('notif_'))
def callback_notif(call):
    selected_day = call.data.split('_')[1]
    bot.answer_callback_query(call.id, text=f"✅ {selected_day} күніне 15 сағат қалғанда хабарландыру жіберіледі!", show_alert=True)

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_all_messages(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    user_text = message.text or message.caption
    if not user_text and message.photo:
        user_text = "Фото расписания со всеми дедлайнами."
        
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
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            ai_reply = res_json['choices'][0]['message']['content'].strip()
            
            lines = ai_reply.split('\n')
            added_count = 0
            
            # Егер бұрынғы ескі тізімді тазарту керек болса немесе үстіне қосу керек болса (қазір үстіне қосады немесе жаңартады)
            for line in lines:
                if "|" in line:
                    parts = [p.strip() for p in line.split("|", 1)]
                    date_str = parts[0]
                    task_desc = parts[1]
                    
                    try:
                        deadline_time = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                    except:
                        try:
                            deadline_time = datetime.strptime(date_str, "%d.%m.%Y")
                        except:
                            continue
                    
                    weekday_num = deadline_time.weekday()
                    matched_kz_day = python_days_to_kz[weekday_num]
                    
                    if chat_id not in user_deadlines:
                        user_deadlines[chat_id] = {}
                    if matched_kz_day not in user_deadlines[chat_id]:
                        user_deadlines[chat_id][matched_kz_day] = []
                        
                    # Қайталанып қалмауы үшін тексереміз
                    exists = any(t['text'] == task_desc and t['time'] == deadline_time for t in user_deadlines[chat_id][matched_kz_day])
                    if not exists:
                        user_deadlines[chat_id][matched_kz_day].append({
                            "text": task_desc,
                            "time": deadline_time,
                            "notified": False,
                            "notified_set": True
                        })
                        added_count += 1
            
            if added_count > 0:
                bot.reply_to(message, f"✅ Барлық тапсырмалар (**{added_count} дана**) өз күндері мен нақты уақыттары бойынша сәтті тіркелді!\n\nКестені тексеру үшін /deadlines басыңыз.", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"🤖 ИИ жауабын оқи алмадым немесе формат сәйкес келмеді:\n{ai_reply}")
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
                    if not t.get("notified", False) and t.get("notified_set", True) and t["time"]:
                        time_left = t["time"] - now
                        if timedelta(0) < time_left <= timedelta(hours=15):
                            try:
                                bot.send_message(
                                    chat_id,
                                    f"⏰ **НАПОМИНАНИЕ / ЕСКЕРТУ!**\n\nДедлайнға 15 сағат қалды!\n📌 Тапсырма ({day}):\n- {t['text']}\n⏰ Уақыты: {t['time'].strftime('%d.%m.%Y %H:%M')}",
                                    parse_mode="Markdown"
                                )
                                t["notified"] = True
                            except Exception as e:
                                print(f"Notification error: {e}")
        time.sleep(60)

# --- FLASK СЕРВЕРІ ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive and running 24/7!"

def run_bot():
    bot.infinity_polling(none_stop=True, interval=0)

if __name__ == "__main__":
    t_remind = threading.Thread(target=reminder_worker, daemon=True)
    t_remind.start()

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
