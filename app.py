import telebot
import requests
import threading
import time
import random
import os
import logging
import gc
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask
from fake_useragent import UserAgent
import urllib3
urllib3.disable_warnings()

# ==========================================
# 🎯 ULTRA BULK SITE CHECKER v5 - APP.PY METHOD
# ==========================================
BOT_TOKEN = "8468244120:AAGXjaczSUzqCF9xTRtoShEzhmx406XEhCE"
OWNER_ID = 5963548505

MAX_THREADS = 150
CHUNK_SIZE = 200
REQUEST_TIMEOUT = 15
BATCH_SEND = 15
PROXY_CHECK_THREADS = 100

VERIFIED_PROXIES_FILE = "verified_proxies.txt"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
PROXY_POOL = []
VERIFIED_PROXIES = []
USER_AGENTS = UserAgent()

# ==========================================
# 💾 FILE MANAGEMENT
# ==========================================

def load_verified_proxies():
    """Load verified proxies from file"""
    global VERIFIED_PROXIES
    if os.path.exists(VERIFIED_PROXIES_FILE):
        try:
            with open(VERIFIED_PROXIES_FILE, 'r') as f:
                VERIFIED_PROXIES = [line.strip() for line in f.readlines() if line.strip()]
            logger.info(f"✅ Loaded {len(VERIFIED_PROXIES)} verified proxies from file")
            return len(VERIFIED_PROXIES)
        except:
            return 0
    return 0

def save_verified_proxies():
    """Save all verified proxies to file"""
    try:
        with open(VERIFIED_PROXIES_FILE, 'w') as f:
            for proxy in VERIFIED_PROXIES:
                f.write(proxy + '\n')
        logger.info(f"✅ Saved {len(VERIFIED_PROXIES)} verified proxies to file")
        return True
    except:
        return False

# ==========================================
# 🌐 FLASK KEEP-ALIVE
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return f"🎯 ULTRA v5 | Verified: {len(VERIFIED_PROXIES)} | App.py Method", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

def start_keep_alive():
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()

# ==========================================
# 🔧 PROXY UTILITIES
# ==========================================

def is_proxy_line(line):
    """Better proxy detection - with or without user:pass"""
    line = line.strip()
    if not ':' in line or len(line) < 7:
        return False
    
    parts = line.split(':')
    
    if len(parts) >= 2:
        ip_part = parts[0]
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_part):
            return True
    
    if len(parts) >= 4:
        return True
    
    return False

def is_site_line(line):
    """Better site detection"""
    line = line.strip().lower()
    if not '.' in line or len(line) < 4:
        return False
    
    tlds = ['.com', '.net', '.org', '.io', '.co', '.shop', '.store', '.xyz', '.dev', '.uk', '.us', '.ca', '.fr', '.de', '.app']
    if any(tld in line for tld in tlds):
        return True
    
    if '.' in line and not ':' in line:
        return True
    
    return False

def test_proxy_quick_connect(proxy):
    """Quick test to see if proxy is reachable"""
    try:
        proxy_parts = proxy.split(':')
        if len(proxy_parts) == 4:
            proxy_url = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"
        elif len(proxy_parts) == 2:
            proxy_url = f"http://{proxy_parts[0]}:{proxy_parts[1]}"
        else:
            return False
        
        proxy_dict = {'http': proxy_url, 'https': proxy_url}
        response = requests.get('http://httpbin.org/ip', proxies=proxy_dict, timeout=5, verify=False)
        return response.status_code == 200
    except:
        return False

def verify_proxy_batch(proxies, message=None):
    """Verify multiple proxies in parallel and AUTO-SAVE"""
    global VERIFIED_PROXIES
    
    if message:
        status_msg = bot.send_message(message.chat.id, f"⚡ <b>VERIFYING {len(proxies)} PROXIES</b>\n🔄 Testing with {PROXY_CHECK_THREADS} threads...", parse_mode='HTML')
    
    verified = []
    checked = 0
    total = len(proxies)
    last_update = time.time()
    
    with ThreadPoolExecutor(max_workers=PROXY_CHECK_THREADS) as executor:
        futures = {executor.submit(test_proxy_quick_connect, p): p for p in proxies}
        
        for future in as_completed(futures):
            checked += 1
            if future.result():
                verified.append(futures[future])
            
            if message and time.time() - last_update > 2:
                try:
                    pct = int((checked / total) * 100)
                    bot.edit_message_text(
                        f"⚡ <b>PROXY VERIFICATION</b>\n✅ Alive: {len(verified)}\n💀 Dead: {checked - len(verified)}\n📊 {pct}% ({checked}/{total})",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode='HTML'
                    )
                    last_update = time.time()
                except:
                    pass
    
    VERIFIED_PROXIES.extend(verified)
    save_verified_proxies()
    
    if message:
        bot.edit_message_text(
            f"✅ <b>PROXY VERIFICATION COMPLETE!</b>\n\n✅ Verified This Batch: {len(verified)}\n💀 Dead: {total - len(verified)}\n\n📊 <b>TOTAL SAVED:</b> {len(VERIFIED_PROXIES)}\n💾 File: <code>verified_proxies.txt</code>",
            message.chat.id,
            status_msg.message_id,
            parse_mode='HTML'
        )
    
    return verified

# ==========================================
# 🔍 SITE CHECKER (APP.PY METHOD)
# ==========================================

def check_site_ultra(site_url, proxy=None):
    """ULTRA site checker - USING EXTERNAL API (FROM app.py METHOD)"""
    try:
        site_url = site_url.strip()
        if site_url.startswith('https://'):
            site_url = site_url.replace('https://', '')
        if site_url.startswith('http://'):
            site_url = site_url.replace('http://', '')
        site_url = site_url.rstrip('/')
        
        # Use external API like app.py does
        test_cc = "5242430428405662|03|2025|328"  # Test card
        api_url = f"https://autoshopify.stormx.pw/index.php?site={site_url}&cc={test_cc}"
        
        headers = {
            'User-Agent': USER_AGENTS.random,
            'Accept': 'application/json, text/javascript, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        try:
            if proxy:
                proxy_parts = proxy.split(':')
                if len(proxy_parts) == 4:
                    proxy_url = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"
                elif len(proxy_parts) == 2:
                    proxy_url = f"http://{proxy_parts[0]}:{proxy_parts[1]}"
                else:
                    proxy_url = None
                
                if proxy_url:
                    proxy_dict = {'http': proxy_url, 'https': proxy_url}
                    response = requests.get(api_url, headers=headers, proxies=proxy_dict, timeout=REQUEST_TIMEOUT, verify=False)
                else:
                    response = requests.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            else:
                response = requests.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    api_response = data.get('Response', '').upper()
                    gateway = data.get('Gateway', 'Unknown')
                    
                    # Check responses
                    if any(x in api_response for x in ["THANK YOU", "APPROVED", "GATEWAY"]):
                        return ("LIVE", "Gateway Detected", gateway)
                    elif "CAPTCHA" in api_response or "CHALLENGE" in api_response:
                        return ("CAPTCHA", "CAPTCHA Protected", gateway)
                    elif "GATED" in api_response or "LOCKED" in api_response:
                        return ("GATED", "Products Locked", gateway)
                    elif any(x in api_response for x in ["DECLINED", "EXPIRED", "INVALID"]):
                        return ("DEAD", api_response[:30], gateway)
                    else:
                        return ("DEAD", api_response[:30], gateway)
                except:
                    return ("DEAD", "Invalid Response", "N/A")
            elif response.status_code == 403:
                return ("BLOCKED", "IP Blocked", "N/A")
            elif response.status_code == 404:
                return ("DEAD", "Not Found", "N/A")
            else:
                return ("DEAD", f"HTTP {response.status_code}", "N/A")
        
        except requests.exceptions.Timeout:
            return ("DEAD", "Timeout", "N/A")
        except Exception as e:
            return ("DEAD", str(e)[:20], "N/A")
    
    except Exception as e:
        return ("ERROR", str(e)[:30], "N/A")

# ==========================================
# 🧵 ULTRA BULK CHECKER
# ==========================================

def run_ultra_bulk_check(message, sites):
    """ULTRA bulk check with real proxies"""
    
    if not sites:
        bot.reply_to(message, "❌ No sites to check!", parse_mode='HTML')
        return
    
    if not VERIFIED_PROXIES:
        bot.reply_to(message, "⚠️ <b>NO VERIFIED PROXIES!</b>\n\n🔌 Upload proxy file and wait for verification!", parse_mode='HTML')
        return
    
    bot.reply_to(message, f"🎯 <b>ULTRA CHECKING {len(sites)} SITES</b>\n🔌 Verified Proxies: {len(VERIFIED_PROXIES)}\n⚙️ {MAX_THREADS} Threads\n⏱️ Starting...", parse_mode='HTML')
    
    live_sites = []
    stats = {'live': 0, 'dead': 0, 'captcha': 0, 'gated': 0, 'blocked': 0, 'error': 0}
    checked = 0
    total = len(sites)
    
    start_time = time.time()
    status_msg = bot.send_message(message.chat.id, "🔄 Initializing...", parse_mode='HTML')
    
    chunks = [sites[i:i+CHUNK_SIZE] for i in range(0, len(sites), CHUNK_SIZE)]
    
    for chunk_idx, chunk in enumerate(chunks):
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {}
            for site in chunk:
                proxy = random.choice(VERIFIED_PROXIES) if VERIFIED_PROXIES else None
                futures[executor.submit(check_site_ultra, site, proxy)] = site
            
            for future in as_completed(futures):
                try:
                    status, msg, gateway = future.result()
                    site = futures[future]
                    checked += 1
                    
                    if status == "LIVE":
                        stats['live'] += 1
                        live_data = f"{site} | {gateway}"
                        live_sites.append(live_data)
                        
                        if len(live_sites) % BATCH_SEND == 0:
                            send_batch_results(message.chat.id, live_sites[-BATCH_SEND:], stats['live'])
                    
                    elif status == "CAPTCHA":
                        stats['captcha'] += 1
                    elif status == "GATED":
                        stats['gated'] += 1
                    elif status == "BLOCKED":
                        stats['blocked'] += 1
                    elif status == "ERROR":
                        stats['error'] += 1
                    else:
                        stats['dead'] += 1
                    
                    if checked % 50 == 0:
                        pct = int((checked / total) * 100)
                        elapsed = int(time.time() - start_time)
                        speed = checked // max(elapsed, 1)
                        
                        try:
                            bar = "█" * int(pct/10) + "░" * (10-int(pct/10))
                            bot.edit_message_text(
                                f"🔄 <b>ULTRA CHECKING</b>\n\n<code>{bar}</code> {pct}%\n📊 {checked}/{total}\n✅ LIVE: {stats['live']}\n🛡️ CAPTCHA: {stats['captcha']}\n💀 DEAD: {stats['dead']}\n⏱️ {elapsed}s ({speed}/sec)",
                                message.chat.id,
                                status_msg.message_id,
                                parse_mode='HTML'
                            )
                        except:
                            pass
                
                except:
                    pass
        
        gc.collect()
        time.sleep(0.2)
    
    elapsed = int(time.time() - start_time)
    speed = total // max(elapsed, 1)
    
    final_report = f"""
✅ <b>ULTRA CHECK COMPLETE!</b>

📊 <b>FINAL RESULTS:</b>
✅ LIVE: <code>{stats['live']}</code>
🛡️ CAPTCHA: <code>{stats['captcha']}</code>
🔒 GATED: <code>{stats['gated']}</code>
⛔ BLOCKED: <code>{stats['blocked']}</code>
💀 DEAD: <code>{stats['dead']}</code>
❌ ERROR: <code>{stats['error']}</code>

📈 Total: <code>{total}</code>
⏱️ Time: <code>{elapsed}s</code>
⚡ Speed: <code>{speed} sites/sec</code>
🔌 Verified Proxies: <code>{len(VERIFIED_PROXIES)}</code>
"""
    
    bot.send_message(message.chat.id, final_report, parse_mode='HTML')
    
    if live_sites and len(live_sites) % BATCH_SEND != 0:
        remaining = len(live_sites) % BATCH_SEND
        send_batch_results(message.chat.id, live_sites[-remaining:], stats['live'])

def send_batch_results(chat_id, sites, total):
    """Send LIVE sites batch"""
    try:
        text = "\n".join(sites)
        filename = f"ultra_live_{int(time.time())}.txt"
        with open(filename, 'w') as f:
            f.write(text)
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✅ Ultra Live Sites | Total: {total}")
        os.remove(filename)
    except Exception as e:
        logger.error(f"Send error: {e}")

# ==========================================
# 🤖 BOT HANDLERS
# ==========================================

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, """
🎯 <b>ULTRA BULK SITE CHECKER v5</b>

✅ <b>FEATURES:</b>
• Check 40K+ sites ULTRA FAST
• 150 parallel threads
• Proxy verification (100 parallel)
• 💾 AUTO-SAVE verified proxies
• External API checking (app.py method)
• Real gateway detection
• Advanced CAPTCHA detection

📤 <b>STEP 1:</b> Upload proxy file
📤 <b>STEP 2:</b> Upload sites file
📤 <b>STEP 3:</b> Get LIVE results!

<b>Proxy Formats:</b>
<code>IP:PORT</code>
<code>IP:PORT:USER:PASS</code>

<b>Sites Format:</b>
<code>example.com</code>
<code>shop.io</code>

/proxies - View verified proxies
/load - Load saved proxies
/clear - Clear all proxies
/stats - Show stats
""", parse_mode='HTML')

@bot.message_handler(commands=['proxies', 'showproxy'])
def show_proxies(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    if not VERIFIED_PROXIES:
        bot.reply_to(m, "❌ No verified proxies!", parse_mode='HTML')
        return
    
    msg = f"🔌 <b>VERIFIED PROXY POOL: {len(VERIFIED_PROXIES)}</b>\n\n"
    for i, proxy in enumerate(VERIFIED_PROXIES[:15], 1):
        msg += f"{i}. {proxy}\n"
    
    if len(VERIFIED_PROXIES) > 15:
        msg += f"\n... and {len(VERIFIED_PROXIES) - 15} more verified"
    
    bot.reply_to(m, msg, parse_mode='HTML')

@bot.message_handler(commands=['load'])
def load_proxies(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    count = load_verified_proxies()
    if count > 0:
        bot.reply_to(m, f"✅ <b>LOADED {count} VERIFIED PROXIES</b>\n\n💾 From: <code>{VERIFIED_PROXIES_FILE}</code>", parse_mode='HTML')
    else:
        bot.reply_to(m, "❌ No saved proxies found", parse_mode='HTML')

@bot.message_handler(commands=['clear'])
def clear_proxies(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    VERIFIED_PROXIES.clear()
    PROXY_POOL.clear()
    bot.reply_to(m, "✅ All proxies cleared!", parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def show_stats(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    bot.reply_to(m, f"""
📊 <b>BOT STATS:</b>

🔌 Proxy Pool: <code>{len(PROXY_POOL)}</code>
✅ Verified: <code>{len(VERIFIED_PROXIES)}</code>
💾 Saved File: <code>{VERIFIED_PROXIES_FILE}</code>
⚙️ Max Threads: <code>{MAX_THREADS}</code>
🔄 Chunk Size: <code>{CHUNK_SIZE}</code>
⏱️ Timeout: <code>{REQUEST_TIMEOUT}s</code>
🔧 Method: <code>External API (app.py)</code>
""", parse_mode='HTML')

@bot.message_handler(content_types=['document'])
def handle_file(m):
    if str(m.from_user.id) != str(OWNER_ID):
        bot.reply_to(m, "❌ Unauthorized", parse_mode='HTML')
        return
    
    try:
        file_info = bot.get_file(m.document.file_id)
        data = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
        
        lines = [line.strip() for line in data.split('\n') if line.strip()]
        
        proxy_lines = [l for l in lines if is_proxy_line(l)]
        site_lines = [l for l in lines if is_site_line(l)]
        
        logger.info(f"Detected: {len(proxy_lines)} proxies, {len(site_lines)} sites")
        
        if len(proxy_lines) > len(site_lines) and len(proxy_lines) > 0:
            if proxy_lines:
                PROXY_POOL.extend(proxy_lines)
                bot.reply_to(m, f"📥 <b>✅ {len(proxy_lines)} PROXIES DETECTED</b>\n\n🔄 Verifying ({PROXY_CHECK_THREADS} threads)...", parse_mode='HTML')
                threading.Thread(target=verify_proxy_batch, args=(proxy_lines, m), daemon=True).start()
            else:
                bot.reply_to(m, "❌ No valid proxies detected", parse_mode='HTML')
        
        elif len(site_lines) > 0:
            formatted_sites = []
            for line in site_lines:
                if not line.startswith('http'):
                    formatted_sites.append(line)
                else:
                    formatted_sites.append(line.replace('https://', '').replace('http://', ''))
            
            bot.reply_to(m, f"📥 <b>✅ {len(formatted_sites)} SITES DETECTED</b>\n🎯 Starting check!", parse_mode='HTML')
            threading.Thread(target=run_ultra_bulk_check, args=(m, formatted_sites), daemon=True).start()
        
        else:
            bot.reply_to(m, f"❌ Could not detect!\n\n📊 Found: {len(proxy_lines)} proxies, {len(site_lines)} sites", parse_mode='HTML')
    
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)[:100]}", parse_mode='HTML')

if __name__ == "__main__":
    initial_count = load_verified_proxies()
    logger.info(f"🎯 ULTRA CHECKER v5 STARTED - {initial_count} proxies loaded - Using External API Method")
    start_keep_alive()
    bot.infinity_polling()
