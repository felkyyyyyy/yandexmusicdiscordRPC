# YandexMusicDiscordRPC
# Yandex Music Discord Rich Presence

A lightweight, efficient Python tool that brings Yandex Music playback status directly to your Discord profile using Windows Media APIs and `pypresence`. No Yandex Music tokens required!

## ✨ Features

- **Direct Windows Integration**: Fetches currently playing media natively using `winrt` (`GlobalSystemMediaTransportControls`), bypassing the need for account tokens.
- **Interactive Progress Bar**: Synchronized real-time playback timer (Spotify-like "Listening" mode).
- **Smart Metadata Fetching**: Automatically queries the Yandex Music API (guest mode) for high-definition album covers, track URLs, and artist profile links.
- **Smart Pause State**: Seamlessly switches to a clean paused state showing the last played track and cover when playback pauses or stops.
- **Media Filtering**: Automatically filters out browsers, YouTube videos, and non-music sources.
- **Customizable Buttons**: Direct quick-access buttons to open the track and the artist's page on Yandex Music.
<img width="426" height="144" alt="Снимок экрана 2026-10-21 012238" src="https://github.com/user-attachments/assets/18d554c9-ce30-44ac-bbde-a61947be9f9c" />
<img width="428" height="153" alt="Снимок экрана 2026-10-21 012229" src="https://github.com/user-attachments/assets/d14c973a-2658-4588-9812-8acee6ee9daf" />
<img width="260" height="175" alt="Снимок экрана 2026-10-21 012221" src="https://github.com/user-attachments/assets/985b03c8-4c6c-41f7-ba45-2a1bc3bbe4e3" />

## 🚀 Installation & Setup

1. **Clone or download** this repository.
2. **Install the required dependencies**:
   ```bash
   pip install pypresence yandex-music winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation
