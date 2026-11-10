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
        "lang_set": "🇷🇺 Язык установлен! Отправьте скриншот расписания.",
        "choose_day": "📅 Выберите день недели:",
        "added_msg": "✅ Все задачи (**{}** шт.) успешно распределены по дням!\n\nНажмите /deadlines для проверки.",
        "ai_prompt": "ВНИМАНИЕ! Посмотри на скриншот расписания. Выпиши КАЖДОЕ задание без исключения. Для каждого укажи точную дату и время слева в формате ДД.ММ.ГГГГ ЧЧ:ММ и оригинальное название задачи точь-в-точь как на фото. Отвечай СТРОГО НА РУССКОМ ЯЗЫКЕ. Формат списка: ДД.ММ.ГГГГ ЧЧ:ММ | Название задачи",
    },
    "kz": {
        "lang_set": "🇰🇿 Тіл таңдалды! Кесте скриншотын жіберіңіз.",
        "choose_day": "📅 Дедлайндарды көру үшін апта күнін басыңыз:",
        "added_msg": "✅ Барлық тапсырмалар (**{}** дана) фотодағы күндері бойынша сәтті тіркелді!\n\nКестені тексеру үшін /deadlines басыңыз.",
        "ai_prompt": "НАЗАР АУДАРЫҢЫЗ! Кесте суретін мұқият қара. Бірде-бір тапсырманы қалдырмай түгел жаз. Әрқайсысы үшін нақты дата мен сол жағындағы уақытты КК.АА.ЖЖЖЖ СС:ММ форматында және тапсырма атауын фотода қалай тұр, солай дәл өзін жаз. Жауапты ТЕК ҚАЗАҚ ТІЛІНДЕ бер. Формат: КК.АА.ЖЖЖЖ СС:ММ | Тапсырма атауы",
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
        "✍️ Отправьте скриншот расписания." if lang == 'ru' else "✍️ Кесте скриншотын жіберіңіз."
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
        
        markup.add(telebot.types.InlineKeyboardButton("🔔 Напоминание / Ескерту", callback_data=f"notif_{selected_day}"))
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
    bot.answer_callback_query(call.id, text=f"✅ {selected_day} күніне 15 сағат қалғанда ескерту жіберіледі!", show_alert=True)

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_all_messages(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    # Фотоны Telegram серверінен жүктеп алып, base64 немесе URL арқылы жіберуге болады, бірақ оңайы — фотоның file_id арқылы OpenRouter-ге vision арқылы беру немесе төмендегідей OpenAI форматтау:
    image_url = None
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    user_text = message.text or message.caption or "Распознай расписание с картинки."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    content_payload = [{"type": "text", "text": f"{LANG[lang]['ai_prompt']}\n\nЗадание: {user_text}"}]
    if image_url:
        content_payload.append({
            "type": "image_url",
            "image_url": {"url": image_url}
        })

    data = {
        "model": "openai/gpt-4o-mini",  # Суретті қатесіз әрі жылдам оқитын модель
        "messages": [{"role": "user", "content": content_payload}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            ai_reply = res_json['choices'][0]['message']['content'].strip()
            
            lines = ai_reply.split('\n')
            added_count = 0
            
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
                bot.reply_to(message, LANG[lang]["added_msg"].format(added_count), parse_mode="Markdown")
            else:
                bot.reply_to(message, f"🤖 Ответ ИИ:\n{ai_reply}")
        else:
            bot.reply_to(message, f"Ошибка ИИ: {response.status_code}")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

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
