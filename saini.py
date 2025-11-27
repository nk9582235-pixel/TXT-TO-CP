import os
import re
import time
import asyncio
import aiohttp
import aiofiles
import subprocess
import requests
from utils import progress_bar
from pyrogram import Client
from pyrogram.types import Message


def sanitize_filename(filename):
    """Remove or replace characters that are invalid in filenames."""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    # Trim whitespace
    filename = filename.strip()
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename if filename else "unnamed"


def get_mps_and_keys(url):
    """Fetch MPD URL and decryption keys from API."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        mpd_url = data.get('data', {}).get('mpd', '')
        keys_list = data.get('data', {}).get('keys', [])
        
        return mpd_url, keys_list
    except Exception as e:
        print(f"Error getting MPD and keys: {e}")
        return None, []


async def pdf_download(url, filename):
    """Download a PDF file from URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(filename, mode='wb') as f:
                        await f.write(await resp.read())
        return filename
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return None


async def download(url, name):
    """Download a file (typically PDF) from URL."""
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka


async def download_video(url, cmd, name):
    """Download video using yt-dlp with aria2c."""
    download_cmd = f'{cmd} -R 25 --external-downloader aria2c --downloader-args "aria2c: -x 32 -j 64 -s 32 -k 2M --optimize-concurrent-downloads"'
    
    print(f"[DEBUG] Download command: {download_cmd}")
    k = subprocess.run(download_cmd, shell=True, capture_output=True, text=True)
    
    # Log yt-dlp output for debugging
    if k.returncode != 0:
        print(f"[ERROR] yt-dlp failed with code {k.returncode}")
        print(f"[ERROR] STDOUT: {k.stdout[:500]}")
        print(f"[ERROR] STDERR: {k.stderr[:500]}")
    
    try:
        if os.path.isfile(name):
            return name
        elif os.path.isfile(f"{name}.webm"):
            return f"{name}.webm"
        name_base = name.split(".")[0]
        if os.path.isfile(f"{name_base}.mkv"):
            return f"{name_base}.mkv"
        elif os.path.isfile(f"{name_base}.mp4"):
            return f"{name_base}.mp4"
        elif os.path.isfile(f"{name_base}.mp4.webm"):
            return f"{name_base}.mp4.webm"
        
        # If file not found, log what files exist
        import glob
        existing_files = glob.glob(f"{name_base}*")
        print(f"[DEBUG] Expected: {name}, Found files: {existing_files}")
        
        return name
    except FileNotFoundError:
        return os.path.splitext(name)[0] + ".mp4"


async def download_and_decrypt_video(url, cmd, name, key):
    """Download and decrypt encrypted video."""
    # This is a placeholder - the actual decryption logic depends on the encryption method
    # For now, just download normally
    return await download_video(url, cmd, name)


async def decrypt_and_merge_video(mpd_url, keys_string, path, name, resolution):
    """Download and decrypt DRM protected video using N_m3u8DL-RE."""
    try:
        # Create downloads directory if it doesn't exist
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        
        output_file = f"{name}.mp4"
        if path:
            output_file = os.path.join(path, output_file)
        
        # Use N_m3u8DL-RE for DRM content
        cmd = f'N_m3u8DL-RE "{mpd_url}" {keys_string} --save-name "{name}" --select-video res="{resolution}p" --save-dir "{path if path else "."}"'
        
        print(f"Running decrypt command: {cmd}")
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # Check if file was created
        if os.path.isfile(output_file):
            return output_file
        elif os.path.isfile(f"{name}.mkv"):
            return f"{name}.mkv"
        elif os.path.isfile(f"{name}.mp4"):
            return f"{name}.mp4"
        
        return output_file
    except Exception as e:
        print(f"Error decrypting video: {e}")
        return None


def duration(filename):
    """Get video duration using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        return float(result.stdout)
    except:
        return 0


async def send_vid(bot: Client, m: Message, cc, filename, thumb, name, prog, channel_id):
    """Send video file to Telegram with thumbnail and progress."""
    try:
        # Generate thumbnail if not provided
        subprocess.run(f'ffmpeg -i "{filename}" -ss 00:01:00 -vframes 1 "{filename}.jpg"', shell=True)
        await prog.delete(True)
        
        reply = await bot.send_message(channel_id, f"**⥣ Uploading ...** » `{name}`")
        
        thumbnail = None
        if thumb == "no" or thumb == "/d":
            thumbnail = f"{filename}.jpg"
        elif thumb and (thumb.startswith("http://") or thumb.startswith("https://")):
            thumbnail = thumb
        
        dur = int(duration(filename))
        start_time = time.time()
        
        try:
            if thumbnail and os.path.exists(thumbnail):
                await bot.send_video(
                    channel_id,
                    filename,
                    caption=cc,
                    supports_streaming=True,
                    height=720,
                    width=1280,
                    thumb=thumbnail,
                    duration=dur,
                    progress=progress_bar,
                    progress_args=(reply, start_time)
                )
            else:
                await bot.send_video(
                    channel_id,
                    filename,
                    caption=cc,
                    supports_streaming=True,
                    height=720,
                    width=1280,
                    duration=dur,
                    progress=progress_bar,
                    progress_args=(reply, start_time)
                )
        except Exception:
            await bot.send_document(
                channel_id,
                filename,
                caption=cc,
                progress=progress_bar,
                progress_args=(reply, start_time)
            )
        
        # Cleanup
        if os.path.exists(filename):
            os.remove(filename)
        if os.path.exists(f"{filename}.jpg"):
            os.remove(f"{filename}.jpg")
        
        await reply.delete(True)
        
    except Exception as e:
        print(f"Error sending video: {e}")
        raise
