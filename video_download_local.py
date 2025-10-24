import os
import requests
from yt_dlp import YoutubeDL

def get_real_size(url):
    """Пытается определить реальный размер файла через HTTP HEAD-запрос"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        size = int(response.headers.get("Content-Length", 0))
        return size // 1024 // 1024 if size else None  # MB
    except Exception:
        return None


def main():
    # Папка для загрузок
    download_dir = "downloads_from_utube"
    os.makedirs(download_dir, exist_ok=True)

    url = input("Введите ссылку на видео с YouTube: ").strip()
    if not url:
        print("❌ Ссылка не может быть пустой.")
        return

    print("\n🔍 Анализ видео, пожалуйста подождите...\n")
    ydl_opts = {"quiet": True, "skip_download": True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    print(f"🎬 Название: {info.get('title')}")
    print(f"📺 Канал: {info.get('uploader')}")
    print(f"⏱️ Длительность: {info.get('duration')} секунд\n")

    # Берем все форматы, включая video-only
    formats = info.get("formats", [])
    video_formats = [f for f in formats if f.get("vcodec") != "none"]

    print("Доступные форматы для скачивания:\n")
    for i, f in enumerate(video_formats, start=1):
        # Попробуем получить размер (точный или оценочный)
        size = f.get("filesize") or f.get("filesize_approx")
        if not size and f.get("url"):
            real_size = get_real_size(f["url"])
            size_str = f"{real_size} MB" if real_size else "N/A"
        else:
            size_str = f"{(size or 0) // 1024 // 1024} MB" if size else "N/A"

        audio_info = "🎧+видео" if f.get("acodec") != "none" else "🎥 только видео"
        print(f"{i:>2}. {f['format_id']:>4}: {f.get('ext','?')} — {f.get('format_note','')} — {f.get('resolution','N/A')} — {audio_info} — {size_str}")

    choice = input("\nВведите номер формата для скачивания (или Enter для авто-выбора лучшего): ").strip()

    if choice:
        if not choice.isdigit() or not (1 <= int(choice) <= len(video_formats)):
            print("❌ Неверный выбор.")
            return
        selected_format = video_formats[int(choice) - 1]['format_id']
        format_string = f"{selected_format}+bestaudio/best"
    else:
        format_string = "bestvideo+bestaudio/best"

    print("\n⬇️ Скачивание началось...\n")

    ydl_opts = {
        "format": format_string,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    print("\n✅ Видео успешно скачано в папку:", os.path.abspath(download_dir))


if __name__ == "__main__":
    main()
