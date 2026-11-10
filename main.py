import os
import time
import threading
from datetime import datetime, timedelta
import requests
import base64
import json
from flask import Flask
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# Құрылымы: {chat_id: [tasks...]}
user_tasks = {}
user_langs = {}
waiting_for_deadline = {}

days_map = {
    "Monday": "Дүйсенбі",
    "Tuesday": "Сейсенбі",
    "Wednesday": "Сәрсенбі",
    "Thursday": "Бейсенбі",
    "Friday": "Жұма",
    "Saturday": "Сенбі",
    "Sunday": "Жексенбі"
}

LANG = {
    "ru": {
        "welcome": "🇷🇺 Привет! Я твой помощник по дедлайнам.\n\nВыбери язык / Тілді таңдаңыз:",
        "set_lang": "✅ Язык установлен на Русский! Используйте /add для добавления и /deadlines для просмотра.",
        "add_prompt": "📸 Отправьте **фото** или **текст** расписания с дедлайнами!",
        "choose_day": "📅 Выберите день недели:",
        "no_tasks": "📭 На этот день дедлайнов нет.",
        "tasks_title": "📌 **Дедлайны на {}:**\n\n",
        "saved": "✅ Успешно сохранено задач: **{}** шт.\n\nПроверить: /deadlines",
        "notif_on": "🔔 Включено",
        "notif_off": "🔕 Выключено",
        "back": "🔙 Назад к дням"
    },
    "kz": {
        "welcome": "🇰🇿 Саламатсыз ба! Мен сіздің дедлайн көмекшіңізбін.\n\nТілді таңдаңыз / Выберите язык:",
        "set_lang": "✅ Тіл қазақшаға ауыстырылды! Тапсырма қосу үшін /add, көру үшін /deadlines басыңыз.",
        "add_prompt": "📸 Дедлайн көрсетілген **суретті** немесе **мәтінді** жіберіңіз!",
        "choose_day": "📅 Дедлайндарды көру үшін апта күнін басыңыз:",
        "no_tasks": "📭 Бұл күні ешқандай дедлайн тіркелмеген.",
        "tasks_title": "📌 **{}:**\n\n",
        "saved": "✅ Барлық тапсырмалар (**{}** дана) сәтті сақталды!\n\nТексеру үшін /deadlines басыңыз.",
        "notif_on": "🔔 Қосулы",
        "notif_off": "🔕 Өшірулі",
        "back": "🔙 Күндерге қайту"
    }
}

def get_lang(chat_id):
    return user_langs.get(chat_id, "ru")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kz")
    )
    bot.send_message(chat_id, "🇷🇺 Выберите язык / 🇰🇿 Тілді таңдаңыз:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def callback_lang(call):
    chat_id = call.message.chat.id
    lang = call.data.split('_')[1]
    user_langs[chat_id] = lang
    bot.answer_callback_query(call.id)
    bot.edit_message_text(LANG[lang]["set_lang"], chat_id, call.message.message_id)

@bot.message_handler(commands=['deadlines'])
def show_days_menu(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    tasks = user_tasks.get(chat_id, [])
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    days = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
    buttons = []
    for day in days:
        count = len([t for t in tasks if t.get('weekday') == day])
        label = f"📌 {day} ({count})" if count > 0 else f"⚪ {day}"
        buttons.append(types.InlineKeyboardButton(label, callback_data=f"day_{day}"))
    markup.add(*buttons)
    bot.reply_to(message, LANG[lang]["choose_day"], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('day_'))
def handle_day_selection(call):
    chat_id = call.message.chat.id
    lang = get_lang(chat_id)
    selected_day = call.data.split('_')[1]
    
    tasks = user_tasks.get(chat_id, [])
    filtered_tasks = [t for t in tasks if t.get('weekday') == selected_day]
    
    markup = types.InlineKeyboardMarkup()
    if filtered_tasks:
        text = LANG[lang]["tasks_title"].format(selected_day)
        for i, task in enumerate(filtered_tasks, 1):
            # Тапсырманың бірегей индексін табу үшін жалпы тізімнен іздейміз
            global_idx = tasks.index(task)
            status = LANG[lang]["notif_on"] if task.get("notified_set", True) else LANG[lang]["notif_off"]
            text += f"{i}. 📌 **{task.get('text', '')}**\n   📅 {task.get('date', '')} | ⏰ {task.get('time', '')}\n   Эскерту / Напоминание: {status}\n\n"
            # Әр дедлайнның астына жеке ескертуді қосу/өшіру батырмасы
            markup.add(types.InlineKeyboardButton(f"🔔 #{i} ескертуді өзгерту", callback_data=f"toggle_{global_idx}"))
    else:
        text = LANG[lang]["no_tasks"]
        
    markup.add(types.InlineKeyboardButton(LANG[lang]["back"], callback_data="back_to_days"))
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_'))
def callback_toggle_notif(call):
    chat_id = call.message.chat.id
    lang = get_lang(chat_id)
    task_idx = int(call.data.split('_')[1])
    
    tasks = user_tasks.get(chat_id, [])
    if 0 <= task_idx < len(tasks):
        current_status = tasks[task_idx].get("notified_set", True)
        tasks[task_idx]["notified_set"] = not current_status
        status_text = LANG[lang]["notif_on"] if tasks[task_idx]["notified_set"] else LANG[lang]["notif_off"]
        bot.answer_callback_query(call.id, text=f"✅ Статус: {status_text}", show_alert=True)
        
        # Менюді жаңарту үшін сол күнге қайта ораламыз
        selected_day = tasks[task_idx]["weekday"]
        filtered_tasks = [t for t in tasks if t.get('weekday') == selected_day]
        
        markup = types.InlineKeyboardMarkup()
        text = LANG[lang]["tasks_title"].format(selected_day)
        for i, task in enumerate(filtered_tasks, 1):
            g_idx = tasks.index(task)
            st = LANG[lang]["notif_on"] if task.get("notified_set", True) else LANG[lang]["notif_off"]
            text += f"{i}. 📌 **{task.get('text', '')}**\n   📅 {task.get('date', '')} | ⏰ {task.get('time', '')}\n   Эскерту: {st}\n\n"
            markup.add(types.InlineKeyboardButton(f"🔔 #{i} ескертуді өзгерту", callback_data=f"toggle_{g_idx}"))
        markup.add(types.InlineKeyboardButton(LANG[lang]["back"], callback_data="back_to_days"))
        
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_days")
def callback_back(call):
    chat_id = call.message.chat.id
    lang = get_lang(chat_id)
    tasks = user_tasks.get(chat_id, [])
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    days = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
    buttons = []
    for day in days:
        count = len([t for t in tasks if t.get('weekday') == day])
        label = f"📌 {day} ({count})" if count > 0 else f"⚪ {day}"
        buttons.append(types.InlineKeyboardButton(label, callback_data=f"day_{day}"))
    markup.add(*buttons)
    bot.edit_message_text(LANG[lang]["choose_day"], chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)

@bot.message_handler(commands=['add'])
def start_add_deadline(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    waiting_for_deadline[chat_id] = True
    bot.reply_to(message, LANG[lang]["add_prompt"], parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    if not waiting_for_deadline.get(chat_id, False):
        return

    sent_msg = bot.reply_to(message, "⏳ ..." if lang=='ru' else "⏳ Оқылуда...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')
        
        prompt = "Суреттен БАРЛЫҚ тапсырмаларды тап. Күнін (day), айын (month), жылын (year - 2026), уақытын (time) және атауын (text) тап. Жауапты ТЕК таза JSON массиви түрінде қайтар: [{\"day\": 11, \"month\": 11, \"year\": 2026, \"time\": \"20:00\", \"text\": \"Тапсырма\"}]"

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            data=json.dumps({
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}]
            })
        )
        
        res_json = response.json()
        response_text = res_json['choices'][0]['message']['content'].strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        parsed_tasks = json.loads(response_text)
        
        if chat_id not in user_tasks:
            user_tasks[chat_id] = []
            
        added_count = 0
        for item in parsed_tasks:
            d = int(item.get("day", 11))
            m = int(item.get("month", 11))
            y = int(item.get("year", 2026))
            dt = datetime(y, m, d)
            rus_weekday = days_map.get(dt.strftime("%A"), "Сәрсенбі")
            
            task_entry = {
                "date": f"{d:02d}.{m:02d}.{y}",
                "weekday": rus_weekday,
                "time": item.get("time", "23:59"),
                "text": item.get("text", "Тапсырма"),
                "datetime": dt.replace(hour=int(item.get("time", "23:59").split(":")[0]), minute=int(item.get("time", "23:59").split(":")[1])),
                "notified": False,
                "notified_set": True
            }
            user_tasks[chat_id].append(task_entry)
            added_count += 1
        
        waiting_for_deadline[chat_id] = False
        bot.edit_message_text(LANG[lang]["saved"].format(added_count), chat_id=chat_id, message_id=sent_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {e}", chat_id=chat_id, message_id=sent_msg.message_id)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    lang = get_lang(chat_id)
    
    if not waiting_for_deadline.get(chat_id, False):
        return

    sent_msg = bot.reply_to(message, "⏳ ...")
    try:
        prompt = "Мәтіннен БАРЛЫҚ тапсырмаларды тап. Күні (day), айы (month), жылы (year - 2026), уақыты (time), атауы (text). ЖАУАП ТЕК JSON: [{\"day\": 11, \"month\": 11, \"year\": 2026, \"time\": \"20:00\", \"text\": \"Тапсырма\"}]"
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            data=json.dumps({
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": message.text}]
            })
        )

        res_json = response.json()
        response_text = res_json['choices'][0]['message']['content'].strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        parsed_tasks = json.loads(response_text)
        if chat_id not in user_tasks:
            user_tasks[chat_id] = []

        added_count = 0
        for item in parsed_tasks:
            d = int(item.get("day", datetime.now().day))
            m = int(item.get("month", datetime.now().month))
            y = int(item.get("year", datetime.now().year))
            dt = datetime(y, m, d)
            kz_weekday = days_map.get(dt.strftime("%A"), "Дүйсенбі")

            task_entry = {
                "date": f"{d:02d}.{m:02d}.{y}",
                "weekday": kz_weekday,
                "time": item.get("time", "23:59"),
                "text": item.get("text", message.text),
                "datetime": dt.replace(hour=int(item.get("time", "23:59").split(":")[0]), minute=int(item.get("time", "23:59").split(":")[1])),
                "notified": False,
                "notified_set": True
            }
            user_tasks[chat_id].append(task_entry)
            added_count += 1

        waiting_for_deadline[chat_id] = False
        bot.edit_message_text(LANG[lang]["saved"].format(added_count), chat_id=chat_id, message_id=sent_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {e}", chat_id=chat_id, message_id=sent_msg.message_id)

def reminder_worker():
    while True:
        now = datetime.now()
        for chat_id, tasks in user_tasks.items():
            for task in tasks:
                if not task.get("notified", False) and task.get("notified_set", True) and "datetime" in task:
                    time_left = task["datetime"] - now
                    if timedelta(0) < time_left <= timedelta(hours=15):
                        try:
                            bot.send_message(
                                chat_id,
                                f"⏰ **НАПОМИНАНИЕ / ЕСКЕРТУ!**\n\nДедлайнға 15 сағат қалды!\n📌 Тапсырма ({task['weekday']}):\n- {task['text']}\n⏰ Уақыты: {task['datetime'].strftime('%d.%m.%Y %H:%M')}",
                                parse_mode="Markdown"
                            )
                            task["notified"] = True
                        except Exception as e:
                            print(f"Reminder error: {e}")
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
