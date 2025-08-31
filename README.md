# 🎥 Ultimate Video Uploader Bot (Telethon + Python)

This is a full-featured Telegram bot that downloads videos from any link (TikTok, YouTube, Instagram, Twitter, direct `.mp4`, `.m3u8` etc.) and uploads them to your Telegram channel.  
It’s designed for Termux, VPS, or any Linux server.  

---

## ⚡ Features

- Supports any video links, not just TikTok.  
- Handles direct MP4, m3u8 streams, and yt-dlp supported platforms.  
- Fixes metadata with ffmpeg for proper playback.  
- Downloads and uploads large videos (>300 MB) without crashing.  
- Saves processed links to avoid duplicates (`processed_links.txt`).  
- Logs failed links to `failed_links.txt`.  
- `/sendfile` command: bot asks for `.txt` file with links → uploads all.  
- Fancy progress bars and console animations.  
- Async & fast, uses `Telethon`, `aiohttp`, and `yt-dlp`.  
- Works in Termux, Linux, or VPS.  

---

## 🛠 Requirements

Python 3.10+ recommended.  

Python packages (`requirements.txt`):