import telebot
from telebot import types
import yt_dlp
import os
import re
import threading
import http.server
import socketserver
from dotenv import load_dotenv
from loguru import logger
from datetime import datetime


# === ЛОГИРОВАНИЕ ===
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
today_log = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")

logger.remove()  # убираем дефолтный вывод
logger.add(
    today_log,
    rotation="00:00",          # новый файл каждый день
    retention="7 days",        # храним неделю
    compression="zip",         # старые архивируются
    encoding="utf-8",
    enqueue=True,              # потокобезопасно
    level="INFO",
)
logger.add(lambda msg: print(msg, end=""), colorize=True, level="INFO")


# токен бота
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

user_data = {}
user_lang = {}  # выбранный язык для каждого пользователя

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ========== Мини веб-сервер ==========
PORT = 8095

def start_http_server():
    handler = http.server.SimpleHTTPRequestHandler
    os.chdir(DOWNLOAD_DIR)
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"HTTP сервер запущен на http://localhost:{PORT}/")
        httpd.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()
logger.info("🤖 Bot started and HTTP server running on port {}", PORT)
# =======================================================

# словари переводов
translations = {
    "be": {
        "start": "Прывітанне! Дашлі мне спасылку на відэа, і я знайду аўдыяфарматы для спампоўкі.",
        "nofile": "Аўдыяфайлы не знойдзеныя 😢",
        "choose": "Абяры аўдыяфармат:",
        "quality": "Цяпер абяры якасць (бітрэйт):",
        "downloading": "Спампоўваю аўдыя...\nФармат: {ext}, якасць: {q} kbps",
        "done": "Гатова ✅",
        "error": "⚠️ Немагчыма адправіць файл (памылка: {err}).\nСпампаваць па спасылцы (дзеян. 2 гадзіны):\n{url}",
        "format_chosen": "Фармат абраны: {ext}.",
        "format_select": "Цяпер абяры канчатковы фармат файла:",
        "lang_select": "Абяры сваю мову:",
        "lang_set": "Мова зменена на беларуская 🇧🇾",
        "too_big": "няма дурных такія вялікія файлы спампоўваць, выбяры нештае меньшае. Нейкую песенку, напрыклад",
        "unsupported": "Гэтая спасылка не падтрымліваецца 🚫"
    },
    "en": {
        "start": "Hello! Send me a video link and I’ll find audio formats to download.",
        "nofile": "No audio files found 😢",
        "choose": "Choose an audio format:",
        "quality": "Now choose quality (bitrate):",
        "downloading": "Downloading audio...\nFormat: {ext}, quality: {q} kbps",
        "done": "Done ✅",
        "error": "⚠️ Could not send file (error: {err}).\nDownload via link (valid for 2 hours):\n{url}",
        "format_chosen": "Format selected: {ext}.",
        "format_select": "Now choose output file format:",
        "lang_select": "Choose your language:",
        "lang_set": "Language set to English 🇬🇧",
        "too_big": "It makes no sense to download such huge files, please choose something smaller. Some song, for example",
        "unsupported": "This link is not supported 🚫"
    },
    "uk": {
        "start": "Привіт! Надішли мені посилання на відео, і я знайду аудіоформати для завантаження.",
        "nofile": "Аудіофайлів не знайдено 😢",
        "choose": "Вибери аудіоформат:",
        "quality": "Тепер вибери якість (бітрейт):",
        "downloading": "Завантажую аудіо...\nФормат: {ext}, якість: {q} kbps",
        "done": "Готово ✅",
        "error": "⚠️ Неможливо надіслати файл (помилка: {err}).\nЗавантаж за посиланням (дійсне 2 години):\n{url}",
        "format_chosen": "Формат вибрано: {ext}.",
        "format_select": "Тепер вибери кінцевий формат файлу:",
        "lang_select": "Вибери свою мову:",
        "lang_set": "Мову змінено на українську 🇺🇦",
        "too_big": "нема дурних такі великі файли завантажувати, виберіть щось менше",
        "unsupported": "Це посилання не підтримується 🚫"
    },
    "ru": {
        "start": "Привет! Отправь мне ссылку на видео, а я найду аудиоформаты для скачивания.",
        "nofile": "Аудиофайлы не найдены 😢",
        "choose": "Выбери аудиоформат:",
        "quality": "Теперь выбери качество (битрейт):",
        "downloading": "Скачиваю аудио...\nФормат: {ext}, качество: {q} kbps",
        "done": "Готово ✅",
        "error": "⚠️ Не удалось отправить файл (ошибка: {err}).\nСкачай по ссылке (действует 2 часа):\n{url}",
        "format_chosen": "Формат выбран: {ext}.",
        "format_select": "Теперь выбери конечный формат файла:",
        "lang_select": "Выбери язык:",
        "lang_set": "Язык изменён на русский 🇷🇺",
        "too_big": "нет дураков такие большие файлы скачивать, выберите что-нибудь поменьше. Какую-то песенку, например",
        "unsupported": "Эта ссылка не поддерживается 🚫"
    }
}

def t(chat_id, key, **kwargs):
    lang = user_lang.get(chat_id, "en")
    return translations[lang][key].format(**kwargs)

# утилиты
def schedule_delete(path, delay=7200):
    def _delete():
        if os.path.exists(path):
            os.remove(path)
            logger.info("[AUTO] File deleted: {}", path)
    threading.Timer(delay, _delete).start()

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def format_duration(seconds: int) -> str:
    if not seconds:
        return "неизвестно"
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

# команды
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id

    # если язык еще не выбран пользователем
    if chat_id not in user_lang:
        tg_lang = message.from_user.language_code  # например "ru", "en", "uk", "be"
        if tg_lang in translations:
            user_lang[chat_id] = tg_lang
        else:
            user_lang[chat_id] = "be"  # язык по умолчанию

    bot.send_message(chat_id, t(chat_id, "start"))
    logger.info("User {} started bot. Language: {}", message.from_user.id, user_lang[chat_id])

@bot.message_handler(commands=['language'])
def language(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    langs = [("Беларуская 🇧🇾", "be"), ("English 🇬🇧", "en"), ("Українська 🇺🇦", "uk"), ("Русский 🇷🇺", "ru")]
    for text, code in langs:
        markup.add(types.InlineKeyboardButton(text, callback_data=f"lang_{code}"))
    bot.send_message(chat_id, t(chat_id, "lang_select"), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_language(call):
    chat_id = call.message.chat.id
    code = call.data.split("_")[1]
    user_lang[chat_id] = code
    logger.info("User {} changed language to {}", chat_id, code)
    bot.send_message(chat_id, translations[code]["lang_set"])

# обработка URL
@bot.message_handler(func=lambda m: m.text and m.text.startswith("http"))
def handle_url(message):
    url = message.text.strip()
    chat_id = message.chat.id
    logger.info("User {} sent URL: {}", chat_id, url)

    ydl_opts = {"skip_download": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        logger.warning("Unsupported URL from {}: {}", chat_id, url)
        bot.send_message(chat_id, t(chat_id, "unsupported"))
        return

    if "entries" in info:
        info = info["entries"][0]

    formats = [f for f in info.get("formats", []) if f.get("acodec") != "none" and f.get("vcodec") == "none"]

    if not formats:
        bot.send_message(chat_id, t(chat_id, "nofile"))
        return

    user_data[chat_id] = {"url": url, "formats": formats, "info": info}

    title = info.get("title", "Без названия")
    uploader = info.get("uploader", "Неизвестный автор")
    duration = format_duration(info.get("duration"))

    text_info = f"🎵 *{title}*\n👤 {uploader}\n⏱ {duration}"
    bot.send_message(chat_id, text_info, parse_mode="Markdown")

    markup = types.InlineKeyboardMarkup()
    for idx, f in enumerate(formats[:15]):
        kb_text = f"{f.get('format_id')} | {f.get('abr','?')}kbps | {f.get('ext')}"
        markup.add(types.InlineKeyboardButton(kb_text, callback_data=f"choose_{idx}"))

    bot.send_message(chat_id, t(chat_id, "choose"), reply_markup=markup)

# выбор формата
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

    bot.send_message(chat_id, t(chat_id, "format_chosen", ext=chosen_format['ext']))
    bot.send_message(chat_id, t(chat_id, "format_select"), reply_markup=markup)

# выбор расширения
@bot.callback_query_handler(func=lambda call: call.data.startswith("format_"))
def ask_quality(call):
    chat_id = call.message.chat.id
    ext = call.data.split("_")[1]
    user_data[chat_id]["ext"] = ext

    markup = types.InlineKeyboardMarkup()
    for q in ["128", "192", "256", "320"]:
        markup.add(types.InlineKeyboardButton(f"{q} kbps", callback_data=f"quality_{q}"))

    bot.send_message(chat_id, t(chat_id, "quality"), reply_markup=markup)

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

    est_size = chosen_format.get("filesize") or chosen_format.get("filesize_approx")

    if est_size and est_size > 20 * 1024 * 1024:  # 20 MB
        bot.send_message(chat_id, t(chat_id, "too_big"))
        logger.info("⚠️ Skipped too large file ({} MB) for user {}", round(est_size / 1048576, 2), chat_id)
        return

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

    bot.send_message(chat_id, t(chat_id, "downloading", ext=ext.upper(), q=quality))
    logger.info("Downloading {} as {} {}kbps for user {}", title, ext, quality, chat_id)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.{ext}")


    try:
        with open(filename, "rb") as f:
            bot.send_document(chat_id, f, caption=title, timeout=60)
        bot.send_message(chat_id, t(chat_id, "done"))
        os.remove(filename)
    except Exception as e:
        logger.error("Error sending file to {}: {}", chat_id, e)
        public_url = f"http://YOUR_SERVER_IP:{PORT}/{os.path.basename(filename)}"
        bot.send_message(chat_id, t(chat_id, "error", err=e, url=public_url))
        schedule_delete(filename, delay=7200)

if __name__ == "__main__":
    bot.infinity_polling()
