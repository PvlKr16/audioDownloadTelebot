import os
import requests
from yt_dlp import YoutubeDL


def get_real_size(url):
    """Определяет реальный размер файла через HTTP HEAD-запрос"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        size = int(response.headers.get("Content-Length", 0))
        return size // 1024 // 1024 if size else None  # MB
    except Exception:
        return None


def main():
    download_dir = "downloads_from_utube"
    os.makedirs(download_dir, exist_ok=True)

    print("🎬 Выберите режим:")
    print("1. Скачать видео")
    print("2. Скачать только аудио (MP3)")
    mode = input("\nВаш выбор (1/2): ").strip()

    if mode == "2":
        url = input("\nВведите ссылку на YouTube: ").strip()
        if not url:
            print("❌ Ссылка не может быть пустой.")
            return

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        print("\n⬇️ Скачивание аудио в формате MP3...\n")
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print("\n✅ Аудио успешно скачано в папку:", os.path.abspath(download_dir))
        return

    elif mode != "1":
        print("❌ Неверный выбор.")
        return

    # ---- Видео-режим ----
    url = input("\nВведите ссылку на видео с YouTube: ").strip()
    if not url:
        print("❌ Ссылка не может быть пустой.")
        return

    print("\n🔍 Анализ видео, пожалуйста подождите...\n")
    ydl_opts = {"quiet": True, "skip_download": True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    print(f"🎞️ Название: {info.get('title')}")
    print(f"📺 Канал: {info.get('uploader')}")
    print(f"⏱️ Длительность: {info.get('duration')} секунд\n")

    formats = info.get("formats", [])
    video_formats = [f for f in formats if f.get("vcodec") != "none"]

    print("Доступные форматы для скачивания:\n")
    for i, f in enumerate(video_formats, start=1):
        size = f.get("filesize") or f.get("filesize_approx")
        if not size and f.get("url"):
            real_size = get_real_size(f["url"])
            size_str = f"{real_size} MB" if real_size else "N/A"
        else:
            size_str = f"{(size or 0) // 1024 // 1024} MB" if size else "N/A"

        audio_info = "🎧+видео" if f.get("acodec") != "none" else "🎥 без звука"
        print(f"{i:>2}. {f['format_id']:>4}: {f.get('ext','?')} — {f.get('format_note','')} — {f.get('resolution','N/A')} — {audio_info} — {size_str}")

    choice = input("\nВведите номер формата для скачивания (или Enter для авто-выбора лучшего): ").strip()

    if not choice:
        # авто-режим: лучшее видео + лучший звук
        format_string = "bestvideo+bestaudio/best"
    else:
        if not choice.isdigit() or not (1 <= int(choice) <= len(video_formats)):
            print("❌ Неверный выбор.")
            return

        selected_format = video_formats[int(choice) - 1]
        selected_format_id = selected_format["format_id"]

        if selected_format.get("acodec") == "none":
            print("\n⚠️ Вы выбрали видео без звука.")
            print("1. Скачать как есть (без звука)")
            print("2. Добавить лучшую аудио-дорожку")
            print("3. Показать все доступные аудио-дорожки")
            audio_choice = input("\nВыберите вариант (1/2/3): ").strip()

            if audio_choice == "1":
                format_string = selected_format_id
            elif audio_choice == "2":
                format_string = f"{selected_format_id}+bestaudio/best"
            elif audio_choice == "3":
                audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
                print("\n🎧 Доступные аудиоформаты:\n")
                for j, af in enumerate(audio_formats, start=1):
                    abr = af.get("abr", "N/A")
                    ext = af.get("ext", "?")
                    size = af.get("filesize") or af.get("filesize_approx")
                    size_str = f"{(size or 0) // 1024 // 1024} MB" if size else "N/A"
                    print(f"{j:>2}. {af['format_id']:>4}: {ext} — {abr} kbps — {size_str}")

                sel_audio = input("\nВведите номер аудиоформата (или Enter для лучшего): ").strip()
                if sel_audio and sel_audio.isdigit() and (1 <= int(sel_audio) <= len(audio_formats)):
                    audio_format_id = audio_formats[int(sel_audio) - 1]["format_id"]
                    format_string = f"{selected_format_id}+{audio_format_id}/best"
                else:
                    format_string = f"{selected_format_id}+bestaudio/best"
            else:
                format_string = f"{selected_format_id}+bestaudio/best"
        else:
            format_string = selected_format_id

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
