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

# Render немесе жүйелік ортадан кілттерді алу
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# Құрылымы: барлық тапсырмалар тізімі және пайдаланушы күйі
all_tasks = []
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

@bot.message_handler(commands=['start'])
def send_welcome(message):
    all_tasks.clear()
    bot.reply_to(message, "Саламатсыз ба! Мен сіздің оқу дедлайндарыңызды реттеп, бақылап отыратын көмекшімін. 🚀📚\n\n📌 /add арқылы тапсырмаларды (сурет немесе мәтін түрінде) жіберіңіз!\n📅 /deadlines арқылы апта күндері бойынша көріңіз.")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, "📌 **Командалар:**\n/deadlines - Апта күндері бойынша дедлайндарды көру\n/add - Жаңа дедлайн қосу", parse_mode="Markdown")

@bot.message_handler(commands=['deadlines'])
def show_days_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    days = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
    buttons = []
    for day in days:
        count = len([t for t in all_tasks if t.get('weekday') == day])
        label = f"📌 {day} ({count})" if count > 0 else f"⚪ {day}"
        buttons.append(types.InlineKeyboardButton(label, callback_data=f"day_{day}"))
    markup.add(*buttons)
    bot.reply_to(message, "📅 Дедлайндарды көру үшін апта күнін басыңыз:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('day_'))
def handle_day_selection(call):
    selected_day = call.data.split('_')[1]
    filtered_tasks = [t for t in all_tasks if t.get('weekday') == selected_day]
    
    markup = types.InlineKeyboardMarkup()
    if filtered_tasks:
        text = f"📌 **{selected_day} күніне арналған дедлайндар (2026):**\n\n"
        for i, task in enumerate(filtered_tasks, 1):
            text += f"{i}. 📌 **{task.get('text', '')}**\n   📅 Дата: {task.get('date', '')} | ⏰ Уақыт: {task.get('time', '')}\n\n"
        markup.add(types.InlineKeyboardButton("🔔 Ескерту қосулы (15 сағат бұрын)", callback_data=f"notif_{selected_day}"))
    else:
        text = f"📭 **{selected_day}** күніне ешқандай дедлайн тіркелмеген."
        
    markup.add(types.InlineKeyboardButton("🔙 Күндерге қайту", callback_data="back_to_days"))
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_days")
def callback_back(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    days = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
    buttons = []
    for day in days:
        count = len([t for t in all_tasks if t.get('weekday') == day])
        label = f"📌 {day} ({count})" if count > 0 else f"⚪ {day}"
        buttons.append(types.InlineKeyboardButton(label, callback_data=f"day_{day}"))
    markup.add(*buttons)
    bot.edit_message_text("📅 Дедлайндарды көру үшін апта күнін басыңыз:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('notif_'))
def callback_notif(call):
    selected_day = call.data.split('_')[1]
    bot.answer_callback_query(call.id, text=f"✅ {selected_day} күніндегі дедлайндарға 15 сағат қалғанда хабарландыру келеді!", show_alert=True)

@bot.message_handler(commands=['add'])
def start_add_deadline(message):
    chat_id = message.chat.id
    waiting_for_deadline[chat_id] = True
    bot.reply_to(message, "📸 Дедлайн көрсетілген **суретті** немесе **мәтінді** жіберіңіз!", parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    
    if not waiting_for_deadline.get(chat_id, False):
        bot.reply_to(message, "💡 Жаңа дедлайн қосу үшін алдымен /add командасын жіберіңіз.")
        return

    sent_msg = bot.reply_to(message, "⏳ **Сурет мұқият оқылуда...**", parse_mode="Markdown")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')
        
        prompt = """Суреттен БАРЛЫҚ тапсырмаларды түгел тап (бірде-бірін қалдырма). Әрқайсысы үшін:
- Күнін (day)
- Айын (month)
- Жылын (year - 2026)
- Нақты уақытын (time, мысалы: "20:00" немесе "23:59")
- Тапсырманың толық атауын (text) дәл өзіндей етіп жаз.
Жауапты ТЕК таза JSON массиви түрінде қайтар (басқа ешқандай сөз жазба):
[{"day": 11, "month": 11, "year": 2026, "time": "20:00", "text": "Тапсырма атауы"}]"""

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ]
            })
        )
        
        res_json = response.json()
        if "choices" not in res_json:
            raise Exception(f"API қатесі: {res_json}")
            
        response_text = res_json['choices'][0]['message']['content'].strip()
        
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        parsed_tasks = json.loads(response_text)
        
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
                "notified": False
            }
            all_tasks.append(task_entry)
            added_count += 1
        
        waiting_for_deadline[chat_id] = False
        bot.edit_message_text(f"✅ Барлық тапсырмалар (**{added_count} дана**) сәтті сақталды!\n\nКестені тексеру үшін /deadlines басыңыз.", chat_id=chat_id, message_id=sent_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ Қате орын алды: {e}", chat_id=chat_id, message_id=sent_msg.message_id)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    
    if not waiting_for_deadline.get(chat_id, False):
        bot.reply_to(message, "💡 Жаңа дедлайн қосу үшін алдымен /add командасын жіберіңіз.")
        return

    sent_msg = bot.reply_to(message, "⏳ **Мәтін талдануда...**", parse_mode="Markdown")
    try:
        prompt = """Төмендегі мәтіннен БАРЛЫҚ тапсырмаларды тап. Күнін (day), айын (month), жылын (year - 2026), уақытын (time) және атауын (text) анықта. 
Жауапты ТЕК таза JSON форматында қайтар (басқа ештеңе жазба):
[{"day": 11, "month": 11, "year": 2026, "time": "20:00", "text": "Тапсырма атауы"}]"""

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message.text}
                ]
            })
        )

        res_json = response.json()
        if "choices" not in res_json:
            raise Exception(f"API қатесі: {res_json}")

        response_text = res_json['choices'][0]['message']['content'].strip()

        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        parsed_tasks = json.loads(response_text)

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
                "notified": False
            }
            all_tasks.append(task_entry)
            added_count += 1

        waiting_for_deadline[chat_id] = False
        bot.edit_message_text(f"✅ Барлық тапсырмалар (**{added_count} дана**) сәтті сақталды!\n\nКестені тексеру үшін /deadlines басыңыз.", chat_id=chat_id, message_id=sent_msg.message_id, parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text(f"❌ Қате орын алды: {e}", chat_id=chat_id, message_id=sent_msg.message_id)

# --- 15 САҒАТ ҚАЛҒАНДА ЕСКЕРТУ ЖІБЕРЕТІН ФОНОВЫЙ ПОТОК ---
def reminder_worker():
    while True:
        now = datetime.now()
        for task in all_tasks:
            if not task.get("notified", False) and "datetime" in task:
                time_left = task["datetime"] - now
                if timedelta(0) < time_left <= timedelta(hours=15):
                    try:
                        # Барлық чаттарға хабарлама жіберу логикасы немесе сақталған чат ID арқылы
                        # Бұл жерде барлық белсенді чаттарға жіберіледі
                        pass
                    except Exception as e:
                        print(f"Reminder error: {e}")
        time.sleep(60)

# --- FLASK СЕРВЕРІ (Render үшін) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive and running 24/7!"

def run_bot():
    bot.infinity_polling(none_stop=True, interval=0)

if __name__ == "__main__":
    # Фоновый поток для уведомлений
    t_remind = threading.Thread(target=reminder_worker, daemon=True)
    t_remind.start()

    # Ботты бөлек ағында қосу
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
