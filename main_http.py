import telebot
from telebot import types
import yt_dlp
import os
import re
import threading
import http.server
import socketserver
from dotenv import load_dotenv

load_dotenv()
# токен бота
TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

user_data = {}
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ========== Мини веб-сервер для раздачи файлов ==========
PORT = 8080

def start_http_server():
    handler = http.server.SimpleHTTPRequestHandler
    os.chdir(DOWNLOAD_DIR)
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"HTTP сервер запущен на http://localhost:{PORT}/")
        httpd.serve_forever()

# Запускаем веб-сервер в отдельном потоке
threading.Thread(target=start_http_server, daemon=True).start()

# =======================================================

def schedule_delete(path, delay=7200):
    """Удаляет файл через delay секунд (по умолчанию 2 часа)"""
    def _delete():
        if os.path.exists(path):
            os.remove(path)
            print(f"[AUTO] Файл удалён: {path}")
    threading.Timer(delay, _delete).start()

def sanitize_filename(name: str) -> str:
    """Убирает недопустимые символы для имени файла"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def format_duration(seconds: int) -> str:
    if not seconds:
        return "неизвестно"
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

# старт
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Отправь мне ссылку на видео, а я найду аудиоформаты для скачивания.")

# обработка URL
@bot.message_handler(func=lambda m: m.text and m.text.startswith("http"))
def handle_url(message):
    url = message.text.strip()
    chat_id = message.chat.id

    ydl_opts = {"skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if "entries" in info:  # если плейлист — берём первый элемент
        info = info["entries"][0]

    formats = [
        f for f in info.get("formats", [])
        if f.get("acodec") != "none" and f.get("vcodec") == "none"
    ]

    if not formats:
        bot.send_message(chat_id, "Аудиофайлов не найдено 😢")
        return

    user_data[chat_id] = {"url": url, "formats": formats, "info": info}

    title = info.get("title", "Без названия")
    uploader = info.get("uploader", "Неизвестный автор")
    duration = format_duration(info.get("duration"))

    text_info = f"🎵 *{title}*\n👤 {uploader}\n⏱ Длительность: {duration}"
    bot.send_message(chat_id, text_info, parse_mode="Markdown")

    markup = types.InlineKeyboardMarkup()
    for idx, f in enumerate(formats[:15]):  # до 15 вариантов
        kb_text = f"{f.get('format_id')} | {f.get('abr','?')}kbps | {f.get('ext')}"
        markup.add(types.InlineKeyboardButton(kb_text, callback_data=f"choose_{idx}"))

    bot.send_message(chat_id, "Выбери аудиоформат:", reply_markup=markup)

# выбор формата аудио
@bot.callback_query_handler(func=lambda call: call.data.startswith("choose_"))
def choose_audio(call):
    chat_id = call.message.chat.id
    idx = int(call.data.split("_")[1])

    formats = user_data[chat_id]["formats"]
    chosen_format = formats[idx]
    user_data[chat_id]["chosen"] = chosen_format

    markup = types.InlineKeyboardMarkup()
    for ext in ["mp3", "m4a", "opus"]:
        markup.add(types.InlineKeyboardButton(ext, callback_data=f"format_{ext}"))

    bot.send_message(chat_id, f"Выбран ID {chosen_format['format_id']} ({chosen_format.get('abr','?')}kbps).\nТеперь выбери конечный формат файла:", reply_markup=markup)

# выбор конечного расширения
@bot.callback_query_handler(func=lambda call: call.data.startswith("format_"))
def ask_quality(call):
    chat_id = call.message.chat.id
    ext = call.data.split("_")[1]

    user_data[chat_id]["ext"] = ext

    markup = types.InlineKeyboardMarkup()
    for q in ["128", "192", "256", "320"]:
        markup.add(types.InlineKeyboardButton(f"{q} kbps", callback_data=f"quality_{q}"))

    bot.send_message(chat_id, f"Формат выбран: {ext.upper()}.\nТеперь выбери качество (битрейт):", reply_markup=markup)

# скачивание
@bot.callback_query_handler(func=lambda call: call.data.startswith("quality_"))
def download_audio(call):
    chat_id = call.message.chat.id
    quality = call.data.split("_")[1]

    url = user_data[chat_id]["url"]
    chosen_format = user_data[chat_id]["chosen"]
    ext = user_data[chat_id]["ext"]

    info = user_data[chat_id]["info"]
    title = info.get("title", "Без названия")
    safe_title = sanitize_filename(title)

    outtmpl = os.path.join(DOWNLOAD_DIR, f"{safe_title}.%(ext)s")

    ydl_opts = {
        "format": chosen_format["format_id"],
        "outtmpl": outtmpl,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": ext,
            "preferredquality": quality,
        }],
    }

    bot.send_message(chat_id, f"Скачиваю аудио...\nФормат: {ext.upper()}, качество: {quality} kbps")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.{ext}")

    try:
        with open(filename, "rb") as f:
            bot.send_document(chat_id, f, caption=title, timeout=60)
        bot.send_message(chat_id, "Готово ✅")
        os.remove(filename)

    except Exception as e:
        public_url = f"http://YOUR_SERVER_IP:{PORT}/{os.path.basename(filename)}"
        bot.send_message(
            chat_id,
            f"⚠️ Не удалось отправить файл напрямую (ошибка: {e}).\n"
            f"Скачай по ссылке (действует 2 часа):\n{public_url}"
        )
        schedule_delete(filename, delay=7200)


if __name__ == "__main__":
    bot.infinity_polling()
