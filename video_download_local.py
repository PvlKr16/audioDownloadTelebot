import os
import requests
from yt_dlp import YoutubeDL

def get_real_size(url):
    """file size detection with HTTP HEAD-request"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        size = int(response.headers.get("Content-Length", 0))
        return size // 1024 // 1024 if size else None  # MB
    except Exception:
        return None


def print_formats(video_formats, formats_blacklist):
    print("Фарматы, даступныя для спампоўкі:\n")
    available = []
    for i, f in enumerate(video_formats, start=1):
        fmt_id = f.get("format_id")
        if fmt_id in formats_blacklist:
            continue
        size = f.get("filesize") or f.get("filesize_approx")
        if not size and f.get("url"):
            real_size = get_real_size(f["url"])
            size_str = f"{real_size} MB" if real_size else "N/A"
        else:
            size_str = f"{(size or 0) // 1024 // 1024} MB" if size else "N/A"

        audio_info = "🎧+відэа" if f.get("acodec") != "none" else "🎥 без гука"
        print(f"{len(available)+1:>2}. {fmt_id:>4}: {f.get('ext','?')} — {f.get('format_note','')} "
              f"— {f.get('resolution','N/A')} — {audio_info} — {size_str}")
        available.append(f)
    return available


def main():
    download_dir = "downloads_from_utube"
    os.makedirs(download_dir, exist_ok=True)

    print("🎬 Выберыце рэжым:")
    print("1. Спампаваць відэа")
    print("2. Спампаваць толькі аўдыё (MP3)")
    mode = input("\nВаш выбар (1/2): ").strip()

    if mode == "2":
        url = input("\nУвядзіце спасылку на YouTube: ").strip()
        if not url:
            print("❌ Спасылка ня можа быць пустая.")
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

        print("\n⬇️ Спампоўка аўдыё ў фармаце MP3...\n")
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print("❌ Памылка падчас спампоўкі аўдыё:", e)
            return

        print("\n✅ Аўдыё паспяхова спампаванае ў тэчку:", os.path.abspath(download_dir))
        return

    elif mode != "1":
        print("❌ Памылковы выбар.")
        return

    # ---- Video regime ----
    url = input("\nУвядзіце спасылку на відэа с YouTube: ").strip()
    if not url:
        print("❌ Спасылка ня можа быць пустая.")
        return

    print("\n🔍 Аналіз відэа. Калі ласка, пачакайце...\n")
    ydl_opts_probe = {"quiet": True, "skip_download": True}
    with YoutubeDL(ydl_opts_probe) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            print("❌ Памылка падчас аналізу відэа:", e)
            return

    print(f"🎞️ Назва: {info.get('title')}")
    print(f"📺 Канал: {info.get('uploader')}")
    print(f"⏱️ Даўжыня: {info.get('duration')} секундаў\n")

    formats = info.get("formats", [])
    video_formats_all = [f for f in formats if f.get("vcodec") != "none"]
    if not video_formats_all:
        print("❌ Відэа-фарматы не знойдзеныя.")
        return

    formats_blacklist = set()
    auto_mode_blocked = False  # if auto is down, no more tries with it

    # main cycle: user selects option and trying to download,
    # in case of error back to selection (without problem options)
    while True:
        # checking if formats are available
        available_formats = [f for f in video_formats_all if f.get("format_id") not in formats_blacklist]
        if not available_formats:
            print("❌ Няма фарматаў для спампоўкі (усе адзначаныя як праблемныя).")
            return

        # formats
        available_list = print_formats(video_formats_all, formats_blacklist)

        print("\nПадказка: увядзіце нумар фармату для спампоўкі, Enter — аўта (лепшыя відэа+гук), q — выхад.")
        choice = input("\nувядзіце нумар фармату (ці Enter/q): ").strip()

        if choice.lower() == "q":
            print("Выхад.")
            return

        if not choice:
            if auto_mode_blocked:
                print("⚠️ Рэжым аўта прывёў да памылкі — выберыце фармат уручную.")
                continue
            format_string = "bestvideo+bestaudio/best"
            chosen_desc = "auto (bestvideo+bestaudio/best)"
            chosen_video_format_id = None  # unknown until yt-dlp selects
        else:
            if not choice.isdigit() or not (1 <= int(choice) <= len(available_list)):
                print("❌ Памылковы выбар.")
                continue
            selected_f = available_list[int(choice) - 1]
            selected_format_id = selected_f["format_id"]
            chosen_video_format_id = selected_format_id
            # available options in case video is without sound
            if selected_f.get("acodec") == "none":
                print("\n⚠️ Вы выбралі відэа без гуку.")
                print("1. Спампаваць як ёсць (без гуку)")
                print("2. Дадаць найлепшае аўдыё")
                print("3. Паказаць усе наяўныя аўдыё-сцежкі")
                audio_choice = input("\nВыберыце варыянт (1/2/3): ").strip()

                if audio_choice == "1":
                    format_string = selected_format_id
                elif audio_choice == "2":
                    format_string = f"{selected_format_id}+bestaudio/best"
                elif audio_choice == "3":
                    audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
                    if not audio_formats:
                        print("❌ Няма аўдыё-сцежак.")
                        format_string = f"{selected_format_id}+bestaudio/best"
                    else:
                        print("\n🎧 Наяўныя аўдыёфарматы:\n")
                        for j, af in enumerate(audio_formats, start=1):
                            abr = af.get("abr", "N/A")
                            ext = af.get("ext", "?")
                            size = af.get("filesize") or af.get("filesize_approx")
                            size_str = f"{(size or 0) // 1024 // 1024} MB" if size else "N/A"
                            print(f"{j:>2}. {af['format_id']:>4}: {ext} — {abr} kbps — {size_str}")

                        sel_audio = input("\nУвядзіце нумар аўдыёфармата (ці Enter для найлепшага): ").strip()
                        if sel_audio and sel_audio.isdigit() and (1 <= int(sel_audio) <= len(audio_formats)):
                            audio_format_id = audio_formats[int(sel_audio) - 1]["format_id"]
                            format_string = f"{selected_format_id}+{audio_format_id}/best"
                        else:
                            format_string = f"{selected_format_id}+bestaudio/best"
                else:
                    format_string = f"{selected_format_id}+bestaudio/best"
            else:
                format_string = selected_format_id
            chosen_desc = f"format {format_string}"

        print(f"\n⬇️ Спроба спампоўкі ({chosen_desc})...\n")

        ydl_opts = {
            "format": format_string,
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
            "noplaylist": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("\n✅ Відэа паспяхова спампаванае ў тэчку:", os.path.abspath(download_dir))
            return
        except Exception as e:
            err_msg = str(e)
            print("\n❌ Памылка падчас спампоўкі:")
            print(err_msg)
            # selected format being added to blacklist
            if chosen_video_format_id:
                print(f"Фармат {chosen_video_format_id} азначаны як праблемны і будзе выключаны са спісу.")
                formats_blacklist.add(chosen_video_format_id)
            else:
                # auto mode is down, selection by hand required
                print("Рэжым аўта (bestvideo+bestaudio) не спрацаваў. Калі ласка, выберыце фармат уручную.")
                auto_mode_blocked = True

            # in ces 403 error
            if "403" in err_msg or "HTTP Error 403" in err_msg or "Forbidden" in err_msg:
                print("\nМагчыма, доступ абмежаваны (403 Forbidden).")
            cont = input("\nЦі хочаце паспрабаваць спампаваць іншы фармат? (y/N): ").strip().lower()
            if cont != "y":
                print("Выхад.")
                return
            else:
                print("Паўторна паказваю наяўныя фарматы (праблемныя выключаныя).\n")
                continue


if __name__ == "__main__":
    main()
