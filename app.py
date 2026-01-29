import telebot
import requests
import threading
import time
import random
import os
import uuid
import logging
import gc
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from flask import Flask
from fake_useragent import UserAgent
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings()

# ==========================================
# 🎯 ULTRA BULK SITE CHECKER v4.1 - IMPROVED
# ==========================================
BOT_TOKEN = "8468244120:AAGXjaczSUzqCF9xTRtoShEzhmx406XEhCE"
OWNER_ID = 5963548505

MAX_THREADS = 150
CHUNK_SIZE = 200
REQUEST_TIMEOUT = 8
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
    return f"🎯 ULTRA v4.1 | Verified: {len(VERIFIED_PROXIES)} | Saved", 200

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

def format_proxy(proxy_str):
    """Format proxy string to proper format"""
    proxy_str = proxy_str.strip()
    
    if ':' not in proxy_str:
        return None
    
    parts = proxy_str.split(':')
    
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return f"http://{user}:{pwd}@{ip}:{port}"
    elif len(parts) == 2:
        ip, port = parts
        return f"http://{ip}:{port}"
    
    return None

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
# 🔍 ADVANCED SITE CHECKER (IMPROVED)
# ==========================================

def find_between(data, first, last):
    """Extract text between two strings"""
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except:
        return None

def create_session_ultra():
    """Create optimized session with verified proxies"""
    session = requests.Session()
    
    if VERIFIED_PROXIES:
        proxy = random.choice(VERIFIED_PROXIES)
        proxy_url = format_proxy(proxy)
        if proxy_url:
            session.proxies = {"http": proxy_url, "https": proxy_url}
    
    retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=MAX_THREADS, pool_maxsize=MAX_THREADS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session

def check_site_ultra(site_url):
    """ULTRA site checker - IMPROVED DETECTION"""
    try:
        session = create_session_ultra()
        site_url = site_url.strip()
        
        if not site_url.startswith('http'):
            site_url = f"https://{site_url}"
        
        site_url = site_url.rstrip('/')
        
        headers = {
            'User-Agent': USER_AGENTS.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # STEP 1: Homepage check
        try:
            r = session.get(site_url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False, allow_redirects=True)
            if r.status_code >= 500:
                return ("DEAD", "500 Error", "N/A")
            if r.status_code == 403:
                return ("BLOCKED", "IP Blocked", "N/A")
            if r.status_code == 404:
                return ("DEAD", "404 Not Found", "N/A")
        except requests.exceptions.Timeout:
            return ("DEAD", "Timeout", "N/A")
        except Exception as e:
            return ("DEAD", "Connect Error", "N/A")
        
        # STEP 2: Try both JSON and HTML products
        variant_id = None
        product_found = False
        
        # Try JSON API first
        try:
            for limit in [50, 100, 250]:
                prod_json = session.get(f"{site_url}/products.json?limit={limit}", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
                if prod_json.status_code == 200:
                    try:
                        data = prod_json.json()
                        products = data.get('products', [])
                        if products:
                            product_found = True
                            for p in products:
                                for v in p.get('variants', []):
                                    if v.get('available'):
                                        variant_id = v.get('id')
                                        break
                                if variant_id:
                                    break
                            if variant_id:
                                break
                    except:
                        pass
        except:
            pass
        
        # Try HTML products page
        if not product_found:
            try:
                prod_page = session.get(f"{site_url}/products", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
                if prod_page.status_code == 200 and len(prod_page.text) > 500:
                    if "product" in prod_page.text.lower() or "variant" in prod_page.text.lower():
                        product_found = True
                        # Try to extract variant from HTML
                        variants = re.findall(r'"id":(\d+)', prod_page.text)
                        if variants:
                            variant_id = variants[0]
            except:
                pass
        
        if not product_found:
            return ("DEAD", "No Products Found", "N/A")
        
        if not variant_id:
            return ("GATED", "Products Locked/No Variants", "N/A")
        
        # STEP 3: Add to cart
        try:
            cart_headers = headers.copy()
            cart_headers['X-Requested-With'] = 'XMLHttpRequest'
            
            cart = session.post(
                f"{site_url}/cart/add.js",
                data={'id': variant_id, 'quantity': 1},
                headers=cart_headers,
                timeout=REQUEST_TIMEOUT,
                verify=False
            )
        except:
            return ("DEAD", "Cart Failed", "N/A")
        
        # STEP 4: Checkout page
        try:
            checkout = session.get(f"{site_url}/checkout", headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            
            captcha_check = checkout.text.lower()
            if any(x in captcha_check for x in ["captcha", "challenge", "recaptcha", "hcaptcha", "cf_challenge", "cloudflare", "turnstile"]):
                return ("CAPTCHA", "CAPTCHA Protected", "N/A")
            
            checkout_url = checkout.url
        except:
            return ("DEAD", "Checkout Failed", "N/A")
        
        # STEP 5: Extract auth token
        auth_token = find_between(checkout.text, 'name="authenticity_token" value="', '"')
        
        if not auth_token:
            try:
                soup = BeautifulSoup(checkout.text, 'html.parser')
                token_elem = soup.find('input', {'name': 'authenticity_token'})
                if token_elem:
                    auth_token = token_elem.get('value')
            except:
                pass
        
        if not auth_token:
            return ("DEAD", "No Auth Token", "N/A")
        
        # STEP 6: Submit shipping
        ship_data = {
            '_method': 'patch',
            'authenticity_token': auth_token,
            'previous_step': 'contact_information',
            'step': 'shipping_method',
            'checkout[email]': f"test{random.randint(10000,99999)}@gmail.com",
            'checkout[shipping_address][first_name]': 'Test',
            'checkout[shipping_address][last_name]': 'User',
            'checkout[shipping_address][address1]': f"{random.randint(100,999)} Main St",
            'checkout[shipping_address][city]': 'New York',
            'checkout[shipping_address][country]': 'US',
            'checkout[shipping_address][province]': 'NY',
            'checkout[shipping_address][zip]': '10001',
            'checkout[shipping_address][phone]': f"+1{random.randint(2000000000,9999999999)}"
        }
        
        try:
            ship_req = session.post(checkout_url, data=ship_data, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
            
            if "captcha" in ship_req.text.lower() or "challenge" in ship_req.url.lower():
                return ("CAPTCHA", "CAPTCHA at Shipping", "N/A")
            
            if ship_req.status_code >= 500:
                return ("DEAD", "Server Error at Shipping", "N/A")
        except:
            return ("DEAD", "Shipping Submit Failed", "N/A")
        
        # STEP 7: Get payment gateway
        gateway_id = find_between(ship_req.text, 'name="checkout[payment_gateway]" value="', '"')
        
        if not gateway_id:
            try:
                soup = BeautifulSoup(ship_req.text, 'html.parser')
                gw_elem = soup.find('input', {'name': 'checkout[payment_gateway]'})
                if gw_elem:
                    gateway_id = gw_elem.get('value')
            except:
                pass
        
        if not gateway_id:
            return ("GATED", "No Payment Gateway", "N/A")
        
        # GATEWAY DETECTED = LIVE ✅
        return ("LIVE", "Gateway Detected", gateway_id)
    
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
            futures = {executor.submit(check_site_ultra, site): site for site in chunk}
            
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
🎯 <b>ULTRA BULK SITE CHECKER v4.1</b>

✅ <b>FEATURES:</b>
• Check 40K+ sites ULTRA FAST
• 150 parallel threads
• Proxy verification (100 parallel)
• 💾 AUTO-SAVE verified proxies
• Multi-variant detection
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
                    formatted_sites.append(f"https://{line}")
                else:
                    formatted_sites.append(line)
            
            bot.reply_to(m, f"📥 <b>✅ {len(formatted_sites)} SITES DETECTED</b>\n🎯 Starting check!", parse_mode='HTML')
            threading.Thread(target=run_ultra_bulk_check, args=(m, formatted_sites), daemon=True).start()
        
        else:
            bot.reply_to(m, f"❌ Could not detect!\n\n📊 Found: {len(proxy_lines)} proxies, {len(site_lines)} sites", parse_mode='HTML')
    
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)[:100]}", parse_mode='HTML')

if __name__ == "__main__":
    initial_count = load_verified_proxies()
    logger.info(f"🎯 ULTRA CHECKER v4.1 STARTED - {initial_count} proxies loaded")
    start_keep_alive()
    bot.infinity_polling()
