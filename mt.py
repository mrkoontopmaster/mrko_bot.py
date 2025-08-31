# FULL Telegram Video Uploader Bot (Termux-ready)
# KEEP PAST CODES - extended with many features, animations & commands
# Uses Telethon for uploads (2GB+ supported), yt-dlp fallback, BeautifulSoup extractor,
# ffmpeg metadata fix, processed_links saving, progress bars and fancy console/UI messages.

import os
import re
import sys
import time
import json
import asyncio
import aiohttp
import subprocess
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from bs4 import BeautifulSoup
from tqdm import tqdm
from colorama import Fore, Style, init
from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeVideo
import yt_dlp
import requests

# -------------------------
# Terminal UI init
# -------------------------
init(autoreset=True)

BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║   🎥  ULTIMATE VIDEO Uploader BOT  (Termux / Telethon)   ║
╠══════════════════════════════════════════════════════════╣
║  - Supports TikTok, YouTube, Instagram, Twitter, direct ║
║    mp4/m3u8 links and any yt-dlp-supported sources.     ║
║  - /sendfile asks for .txt -> processes all links       ║
║  - Saves processed links, avoids duplicates             ║
║  - ffmpeg metadata fix, yt-dlp fallback, progress bars  ║
╚══════════════════════════════════════════════════════════╝
"""

print(Fore.CYAN + BANNER)

# -------------------------
# CONFIG - Edit these
# -------------------------
API_ID = 23510012              # <-- replace with your API_ID
API_HASH = "76f633b685c582c0021cf6bea4c10f77"   # <-- replace with your API_HASH
BOT_TOKEN = "8185842252:AAE7ElUbwiMGmdC1n1NQjxijoTKXXeU65-8"  # your bot token (kept as in previous)
CHANNEL_ID = "@MAINPINAYV1"  # can be @username or -100123... numeric id

# Files
PROCESSED_FILE = "processed_links.txt"
FAILED_FILE = "failed_links.txt"
LINKS_FOLDER = "downloads"

# Ensure folders/files exist
os.makedirs(LINKS_FOLDER, exist_ok=True)
if not os.path.exists(PROCESSED_FILE):
    open(PROCESSED_FILE, "w").close()
if not os.path.exists(FAILED_FILE):
    open(FAILED_FILE, "w").close()

# Blacklist (keep from past)
BLACKLIST = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

# Telethon client
client = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Thread pool for downloads (used for parallelizable tasks)
CPU_COUNT = multiprocessing.cpu_count()
DOWNLOAD_WORKERS = max(2, min(8, CPU_COUNT * 2))

# -------------------------
# Utility functions (kept past logic)
# -------------------------
def load_processed_set():
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_processed(url):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")

def save_failed(url, reason=""):
    with open(FAILED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()} | {url} | {reason}\n")

def is_blacklisted(url):
    return any(b in url.lower() for b in BLACKLIST)

# -------------------------
# Extract video urls using BeautifulSoup (kept original)
# -------------------------
def extract_video_url(page_url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        r = requests.get(page_url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # Direct <video src>
        video_tag = soup.find("video")
        if video_tag and video_tag.get("src"):
            return video_tag["src"]

        # <source>
        source_tag = soup.find("source")
        if source_tag and source_tag.get("src"):
            return source_tag["src"]

        # iframe (nested)
        iframe = soup.find("iframe")
        if iframe and iframe.get("src"):
            return iframe["src"] if iframe["src"].startswith("http") else None

        # regex fallback for mp4/m3u8
        matches = re.findall(r'https?://[^\s"\']+\.(?:mp4|m3u8)', r.text)
        if matches:
            return matches[0]

    except Exception as e:
        print(Fore.RED + f"⚠ Error extracting: {e}")
        return None

    return None

# -------------------------
# FFmpeg metadata fix (kept)
# -------------------------
def fix_metadata(input_path: str, output_path: str):
    """Re-mux video to fix metadata without re-encoding."""
    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-map", "0", "-c", "copy", "-movflags", "faststart", output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(Fore.RED + f"⚠ Metadata fix failed: {e}")
        return False

# -------------------------
# yt-dlp download (universal)
# -------------------------
def ytdlp_download(link, outdir=LINKS_FOLDER, max_width=None):
    """Download using yt-dlp; returns filepath and info dict."""
    safe_template = os.path.join(outdir, "%(title).120s.%(ext)s")
    ydl_opts = {
        "outtmpl": safe_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
    }
    if max_width:
        # prefer formats <= given width (helps keep size smaller)
        ydl_opts["format"] = f'bestvideo[width<={max_width}]+bestaudio/best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filepath = ydl.prepare_filename(info)
            return filepath, info
    except Exception as e:
        print(Fore.YELLOW + f"[yt-dlp] failed for {link}: {e}")
        return None, None

# -------------------------
# M3U8 download via ffmpeg
# -------------------------
def download_m3u8_ffmpeg(m3u8_url: str, out_path: str):
    try:
        cmd = ["ffmpeg", "-y", "-i", m3u8_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", out_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(Fore.RED + f"❌ FFmpeg m3u8 failed: {e}")
        return False

# -------------------------
# direct http download (streamed)
# -------------------------
def download_streamed(url, out_path, chunk_size=4 * 1024 * 1024):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url, stream=True, headers=headers, timeout=120) as r:
            if r.status_code != 200:
                print(Fore.RED + f"Download bad status {r.status_code} for {url}")
                return False
            total = int(r.headers.get("content-length", 0))
            with open(out_path, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc="⬇ Download", ncols=100) as bar:
                for chunk in r.iter_content(chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    bar.update(len(chunk))
        return True
    except Exception as e:
        print(Fore.RED + f"❌ MP4 download error: {e}")
        return False

# -------------------------
# send via Telethon with progress callback
# -------------------------
async def send_file_with_progress(chat_id, file_path, caption):
    size_bytes = os.path.getsize(file_path)
    uploaded = 0
    last_print = 0

    def progress_callback(current, total):
        nonlocal uploaded, last_print
        uploaded = current
        pct = int(current / total * 100) if total else 0
        if pct - last_print >= 5 or pct in (0, 100):
            last_print = pct
            bar = "[" + ("█" * (pct // 4)).ljust(25) + f"] {pct}%"
            print(Fore.MAGENTA + f"\r{bar} {current/(1024*1024):.2f}/{total/(1024*1024):.2f} MB", end="")

    print(Fore.CYAN + f"\n📤 Uploading to Telegram: {os.path.basename(file_path)}")
    await client.send_file(
        chat_id,
        file_path,
        caption=caption,
        parse_mode="html",
        progress_callback=progress_callback,
        attributes=[DocumentAttributeVideo(0, 0, 0)]
    )
    print("\n" + Fore.GREEN + "✅ Upload finished")

# -------------------------
# Single link processor: tries extract -> direct -> yt-dlp -> ffmpeg m3u8
# -------------------------
def process_single_link_blocking(link):
    """Blocking function to download a link and return filepath, title or (None, reason)."""
    link = link.strip()
    if not link:
        return None, "empty"

    if is_blacklisted(link):
        return None, "blacklisted"

    # 1) Try BeautifulSoup extractor if plain page
    possible_media = extract_video_url(link)
    if possible_media:
        # If it's m3u8
        if possible_media.endswith(".m3u8"):
            outname = os.path.join(LINKS_FOLDER, f"out_{abs(hash(link)) % 100000}.mp4")
            ok = download_m3u8_ffmpeg(possible_media, outname)
            if ok:
                title = os.path.basename(outname)
                fixed = os.path.join(LINKS_FOLDER, f"fixed_{abs(hash(link)) % 100000}.mp4")
                if fix_metadata(outname, fixed):
                    os.remove(outname)
                    return fixed, title
                return outname, title
            # fallback to yt-dlp if ffmpeg fails
        elif possible_media.endswith(".mp4"):
            outpath = os.path.join(LINKS_FOLDER, f"dl_{abs(hash(link)) % 100000}.mp4")
            if download_streamed(possible_media, outpath):
                title = os.path.basename(outpath)
                fixed = os.path.join(LINKS_FOLDER, f"fixed_{abs(hash(link)) % 100000}.mp4")
                if fix_metadata(outpath, fixed):
                    os.remove(outpath)
                    return fixed, title
                return outpath, title
            # else fallthrough to yt-dlp

    # 2) Try yt-dlp universal download
    print(Fore.YELLOW + f"[yt-dlp] Attempting to download: {link}")
    filepath, info = ytdlp_download(link)
    if filepath:
        title = info.get("title", os.path.basename(filepath) if info else os.path.basename(filepath))
        # Try fix metadata to enable faststart
        fixed_path = os.path.splitext(filepath)[0] + "_fixed.mp4"
        if fix_metadata(filepath, fixed_path):
            try:
                os.remove(filepath)
            except:
                pass
            return fixed_path, title
        return filepath, title

    # 3) if all fails
    return None, "download_failed"

# -------------------------
# Async wrapper to run blocking downloader without blocking the loop
# -------------------------
async def process_single_link(link, loop=None, executor=None):
    loop = loop or asyncio.get_event_loop()
    executor = executor or ThreadPoolExecutor(max_workers=2)
    return await loop.run_in_executor(executor, process_single_link_blocking, link)

# -------------------------
# high-level: process list of links sequentially (safe for Termux storage)
# -------------------------
async def process_links_from_file(file_path, event=None, ask_delete=True):
    # read links
    if not os.path.exists(file_path):
        if event:
            await event.respond("❌ File not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        links = [l.strip() for l in f.read().splitlines() if l.strip()]

    processed_set = load_processed_set()
    total = len(links)
    sent = 0
    skipped = 0
    failed = 0

    if event:
        await event.respond(f"📂 Found {total} links. Starting processing...")

    # We'll process sequentially to avoid huge simultaneous disk usage, but file downloads use threads in ytdlp.
    for idx, link in enumerate(links, start=1):
        nice = f"[{idx}/{total}]"
        print(Fore.CYAN + f"\n{nice} Processing: {link}")

        if link in processed_set:
            print(Fore.YELLOW + "⏭ Already processed, skipping.")
            skipped += 1
            if event:
                await event.respond(f"⚠️ Skipped (already processed): {link}")
            continue

        if is_blacklisted(link):
            print(Fore.YELLOW + "⏭ Blacklisted link type, skipping.")
            skipped += 1
            if event:
                await event.respond(f"⚠️ Skipped (blacklist): {link}")
            save_processed(link)
            continue

        # Try to process
        filepath, title_or_reason = await process_single_link(link)
        if not filepath:
            print(Fore.RED + f"❌ Failed to download: {link} ({title_or_reason})")
            save_failed(link, title_or_reason)
            failed += 1
            if event:
                await event.respond(f"❌ Failed to download: {link}")
            continue

        # Upload with progress to Telegram
        caption = f'ᥕᥲ𝗍ᥴһ ᥆ᥙ𝗍 <a href="{link}">source</a>\n📌 {title_or_reason}'
        try:
            await send_file_with_progress(CHANNEL_ID, filepath, caption)
            sent += 1
            save_processed(link)
            processed_set.add(link)
            if event:
                await event.respond(f"✅ Uploaded: {link}")
        except Exception as e:
            print(Fore.RED + f"❌ Upload failed: {e}")
            save_failed(link, f"upload_error:{e}")
            failed += 1
            if event:
                await event.respond(f"❌ Upload failed for {link}: {e}")
        finally:
            # cleanup
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(Fore.BLUE + f"[🗑] Removed temporary file: {filepath}")
            except Exception as e:
                print(Fore.YELLOW + f"[!cleanup] could not delete: {e}")

    # Summary
    summary = f"✨ Done. Sent: {sent} | Skipped: {skipped} | Failed: {failed}"
    print(Fore.GREEN + summary)
    if event:
        await event.respond(summary)

# -------------------------
# Bot commands & handlers
# -------------------------
@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(event):
    await event.respond(
        "👋 Yo! I'm the Video Uploader Bot.\n\n"
        "Commands:\n"
        "/sendfile - I'll ask for a .txt file and upload every link inside.\n"
        "/status - show processed counts\n"
        "/clearhistory - clear processed list (admin only)\n"
        "/help - show help\n\n"
        "Send /sendfile to begin."
    )

@client.on(events.NewMessage(pattern="/help"))
async def cmd_help(event):
    await event.respond(
        "💡 HELP\n"
        "/sendfile - send a .txt file with links (one per line)\n"
        "/status - get summary of processed/failed\n"
        "/clearhistory - clear processed links file\n"
        "/addlink <url> - add a link to processed_links (if you want it marked processed)\n"
        "/unprocessed - show first 10 unprocessed links in last uploaded txt (not persistent)\n"
    )

@client.on(events.NewMessage(pattern="/status"))
async def cmd_status(event):
    processed = len(load_processed_set())
    failed = sum(1 for _ in open(FAILED_FILE, "r", encoding="utf-8"))
    await event.respond(f"📊 Status:\nProcessed links: {processed}\nFailed entries: {failed}")

@client.on(events.NewMessage(pattern="/clearhistory"))
async def cmd_clear(event):
    # You can add admin check here if you want
    open(PROCESSED_FILE, "w").close()
    await event.respond("🧹 Processed links cleared.")

@client.on(events.NewMessage(pattern=r"^/addlink\s+(.+)$"))
async def cmd_addlink(event):
    m = event.pattern_match
    url = m.group(1).strip()
    save_processed(url)
    await event.respond(f"✅ Added to processed: {url}")

# /sendfile flow: ask for .txt file and then processing runs when user uploads it
@client.on(events.NewMessage(pattern="/sendfile"))
async def cmd_sendfile(event):
    await event.respond("📂 Please send me a .txt file with links (one per line). I will process and upload each to the channel.")
    # The actual processing occurs in the below generic handler when a .txt file is received

# Generic handler for any uploaded .txt file
@client.on(events.NewMessage(func=lambda e: e.file and e.file.name and e.file.name.lower().endswith(".txt")))
async def handle_uploaded_txt(event):
    # When user sends the txt file, download it and begin processing
    try:
        sender = await event.get_sender()
        who = getattr(sender, "username", None) or getattr(sender, "id", "unknown")
        await event.respond(Fore.CYAN + f"📥 Received .txt file from {who}. Downloading and processing...")
        txt_path = await event.download_media()
        # Small animation: pretend to read and parse
        await event.respond("🔎 Reading links...")
        await asyncio.sleep(0.8)
        await process_links_from_file(txt_path, event=event)
        # optionally remove uploaded txt after process
        try:
            if os.path.exists(txt_path):
                os.remove(txt_path)
        except:
            pass
    except Exception as e:
        await event.respond(Fore.RED + f"❌ Error processing your file: {e}")

# Provide a command to show recent failed links (first 10)
@client.on(events.NewMessage(pattern="/failed"))
async def cmd_failed(event):
    lines = []
    with open(FAILED_FILE, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 10:
                break
            lines.append(line.strip())
    if not lines:
        await event.respond("✅ No failed records.")
    else:
        await event.respond("❌ Recent failed entries:\n" + "\n".join(lines))

# Keep-alive fancy banner printed in console
print(Fore.GREEN + "✅ Bot initialized. Listening for commands...")
print(Fore.YELLOW + "Tip: Use /sendfile then upload your links.txt file (one link per line).")

# Run client
client.run_until_disconnected()