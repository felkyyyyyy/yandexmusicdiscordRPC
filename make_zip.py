import asyncio
import time
import os
import sys
import threading
import ctypes
from PIL import Image
import pystray
from pystray import MenuItem as item
from winotify import Notification, audio
from pypresence import Presence, ActivityType
from yandex_music import Client
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
)

DISCORD_CLIENT_ID = "1562220223191318728"
USE_PROGRESS_BAR_MODE = True
UPDATE_INTERVAL = 3
FALLBACK_COVER_URL = "https://yastatic.net/s3/doc-binary/freeze/ru/music/2393031772031213653.png"
CONFIG_FILE = "config.txt"

rpc_client = None
is_running = True

def show_toast(title, message):
    try:
        toast = Notification(
            app_id="Yandex Music RPC",
            title=title,
            msg=message,
            duration="short"
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception:
        pass

def check_startup():
    if not os.path.exists(CONFIG_FILE):
        result = ctypes.windll.user32.MessageBoxW(
            0, 
            "Хотите ли вы, чтобы Яндекс Музыка Discord RPC запускалась автоматически при включении Windows?", 
            "Yandex Music RPC - Автозагрузка", 
            0x4 | 0x20 | 0x1000
        )
        is_yes = (result == 6)
        
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if is_yes:
                    winreg.SetValueEx(key, "YandexMusicDiscordRPC", 0, winreg.REG_SZ, f'"{exe_path}"')
                else:
                    try:
                        winreg.DeleteValue(key, "YandexMusicDiscordRPC")
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write("configured")
        except Exception:
            pass

async def get_windows_media_info():
    try:
        sessions = await MediaManager.request_async()
        current_session = sessions.get_current_session()
        if not current_session:
            return None

        source_id = current_session.source_app_user_model_id.lower()
        if any(browser in source_id for browser in ["chrome", "edge", "firefox", "opera", "brave"]):
            return None

        playback_info = current_session.get_playback_info()
        status = playback_info.playback_status
        is_playing = (status == PlaybackStatus.PLAYING)
        is_paused = (status == PlaybackStatus.PAUSED)

        if not is_playing and not is_paused:
            return None

        info = await current_session.try_get_media_properties_async()
        if not info or not info.title:
            return None

        title = info.title.strip()
        artist = info.artist.strip() if info.artist else ""

        forbidden_words = ["youtube", "trailer", "стрим", "реакция", "подкаст"]
        full_info = f"{artist} {title}".lower()
        if any(word in full_info for word in forbidden_words):
            return None

        pos_sec = None
        dur_sec = None
        try:
            timeline = current_session.get_timeline_properties()
            if timeline and timeline.end_time.total_seconds() > 0:
                pos_sec = timeline.position.total_seconds()
                dur_sec = timeline.end_time.total_seconds()
        except Exception:
            pass

        return {
            "title": title,
            "artist": artist,
            "is_playing": is_playing,
            "pos_sec": pos_sec,
            "dur_sec": dur_sec
        }
    except Exception:
        return None

def search_yandex_metadata(ym_client: Client, title: str, artist: str):
    query = f"{artist} {title}".strip()
    try:
        search_result = ym_client.search(query, type_="track")
        if search_result and search_result.tracks and search_result.tracks.results:
            track = search_result.tracks.results[0]
            track_id = track.id
            
            if track.artists:
                main_artist = track.artists[0]
                artist_name = ", ".join([a.name for a in track.artists])
                artist_url = f"https://music.yandex.ru/artist/{main_artist.id}"
                main_artist_name = main_artist.name
            else:
                artist_name = artist or "Неизвестный исполнитель"
                main_artist_name = artist_name
                artist_url = "https://music.yandex.ru"

            if track.albums:
                album = track.albums[0]
                album_title = f"{album.title} ({album.year})" if album.year else (album.title or "Сингл")
                track_url = f"https://music.yandex.ru/album/{album.id}/track/{track_id}"
            else:
                album_title = "Сингл"
                track_url = f"https://music.yandex.ru/track/{track_id}"

            if track.cover_uri:
                cover_large = f"https://{track.cover_uri.replace('%%', '1000x1000')}"
            else:
                cover_large = FALLBACK_COVER_URL

            duration_sec = (track.duration_ms // 1000) if track.duration_ms else 0

            return {
                "title": track.title or title,
                "artist_names": artist_name,
                "main_artist_name": main_artist_name,
                "album_title": album_title,
                "track_url": track_url,
                "artist_url": artist_url,
                "cover_large": cover_large,
                "duration_sec": duration_sec
            }
    except Exception:
        pass

    safe_query = query.replace(' ', '%20') if query else "music"
    return {
        "title": title,
        "artist_names": artist or "Неизвестный исполнитель",
        "main_artist_name": artist or "Артист",
        "album_title": "Сингл",
        "track_url": f"https://music.yandex.ru/search?text={safe_query}",
        "artist_url": "https://music.yandex.ru",
        "cover_large": FALLBACK_COVER_URL,
        "duration_sec": 0
    }

def run_rpc_loop():
    global rpc_client, is_running
    ym_client = Client().init()

    try:
        rpc = Presence(DISCORD_CLIENT_ID)
        rpc.connect()
        rpc_client = rpc
    except Exception:
        return

    show_toast("Статус активен", "Скрипт успешно запущен и работает в фоне")

    last_track_key = None
    cached_meta = None
    track_start_ts = 0
    was_paused = False

    while is_running:
        try:
            media = asyncio.run(get_windows_media_info())

            if media:
                current_key = f"{media['artist']} - {media['title']}"
                now = int(time.time())

                if current_key != last_track_key:
                    last_track_key = current_key
                    track_start_ts = now
                    cached_meta = search_yandex_metadata(ym_client, media["title"], media["artist"])

                if cached_meta:
                    artist_btn = f"▫️ {cached_meta['main_artist_name']}"[:32]
                    
                    t_url = cached_meta["track_url"]
                    a_url = cached_meta["artist_url"]
                    if not t_url or not t_url.startswith("http"):
                        t_url = "https://music.yandex.ru"
                    if not a_url or not a_url.startswith("http"):
                        a_url = "https://music.yandex.ru"

                    buttons = [
                        {"label": "▶ Слушать трек", "url": t_url},
                        {"label": artist_btn, "url": a_url}
                    ]

                    if not media["is_playing"]:
                        if not was_paused:
                            was_paused = True

                        rpc.update(
                            activity_type=ActivityType.LISTENING,
                            details=f"⏸ {cached_meta['title']}"[:128],
                            state=f"от {cached_meta['artist_names']}"[:128],
                            large_image=cached_meta["cover_large"],
                            large_text="Музыка на паузе",
                            buttons=buttons
                        )
                    else:
                        if was_paused:
                            was_paused = False
                            track_start_ts = now

                        dur_sec = int(cached_meta["duration_sec"] or media["dur_sec"] or 0)

                        if media["pos_sec"] is not None and dur_sec > 0:
                            calculated_start = int(now - media["pos_sec"])
                            if abs(calculated_start - track_start_ts) > 3:
                                track_start_ts = calculated_start

                        track_end_ts = (track_start_ts + dur_sec) if dur_sec > 0 else None
                        act_type = ActivityType.LISTENING if USE_PROGRESS_BAR_MODE else ActivityType.PLAYING

                        rpc.update(
                            activity_type=act_type,
                            details=cached_meta["title"][:128],
                            state=f"от {cached_meta['artist_names']}"[:128],
                            large_image=cached_meta["cover_large"],
                            large_text=cached_meta["album_title"][:128],
                            start=track_start_ts,
                            end=track_end_ts,
                            buttons=buttons
                        )
            else:
                if last_track_key is not None:
                    rpc.clear()
                    last_track_key = None
                    was_paused = False

        except Exception:
            pass

        time.sleep(UPDATE_INTERVAL)

    try:
        rpc.clear()
        rpc.close()
    except Exception:
        pass

def on_exit(icon, item):
    global is_running
    is_running = False
    icon.stop()
    sys.exit(0)

def main():
    check_startup()

    t = threading.Thread(target=run_rpc_loop, daemon=True)
    t.start()

    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(base_path, "icon.png")

    if os.path.exists(icon_path):
        image = Image.open(icon_path)
    else:
        image = Image.new('RGB', (64, 64), color=(70, 130, 180))

    menu = (item('Выход', on_exit),)
    icon = pystray.Icon("YandexMusicRPC", image, "Yandex Music Discord RPC", menu)
    icon.run()

if __name__ == "__main__":
    main()