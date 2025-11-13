import yt_dlp
import os
import re
from datetime import datetime
from loguru import logger

# === Настройки ===
DOWNLOAD_DIR = "utube_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
today_log = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")

logger.remove()
logger.add(today_log, rotation="00:00", retention="7 days", compression="zip",
           encoding="utf-8", enqueue=True, level="INFO")
logger.add(lambda msg: print(msg, end=""), colorize=True, level="INFO")


def sanitize_filename(name: str) -> str:
    """Удаляет недопустимые символы из имени файла."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def download_best_audio(url: str):
    """Скачивает лучшее доступное аудио по ссылке."""
    logger.info("Получена ссылка: {}", url)

    # Папка и шаблон имени файла
    outtmpl = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    # Настройки yt_dlp
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "geo_bypass_country": "US",
        "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
        "quiet": False,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = sanitize_filename(info.get("title", "Без названия"))
            duration = info.get("duration")
            logger.info("Название: {}", title)
            logger.info("Продолжительность: {} сек", duration)
            ydl.download([url])
            logger.info("✅ Успешно скачано: {}", title)
    except Exception as e:
        if "403" in str(e):
            logger.error("🚫 Ошибка 403 — доступ запрещён (возможно, требуется вход или VPN)")
        else:
            logger.exception("Ошибка при скачивании: {}", e)


if __name__ == "__main__":
    url = input("Введите ссылку на YouTube: ").strip()
    download_best_audio(url)
