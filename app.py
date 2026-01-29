import telebot
import requests
import threading
import time
import random
import os
import logging
import gc
import re
import json
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask
from fake_useragent import UserAgent
import urllib3
from urllib.parse import urljoin, urlparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 🔧 CONFIG
# ==========================================
BOT_TOKEN = "8468244120:AAGXjaczSUzqCF9xTRtoShEzhmx406XEhCE"
OWNER_ID = 5963548505

MAX_THREADS = 200
CHUNK_SIZE = 250
REQUEST_TIMEOUT = 12
BATCH_SEND = 20
PROXY_CHECK_THREADS = 150
HTTP_TIMEOUT_SHORT = 8
HTTP_TIMEOUT_MEDIUM = 12

VERIFIED_PROXIES_FILE = "verified_proxies.txt"
WORKING_SITES_FILE = "workingsites.txt"

bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
PROXY_POOL = []
VERIFIED_PROXIES = []
USER_AGENTS = UserAgent()
LOG_CHAT_ID = None
TELEGRAM_HANDLER = None

ACTIVE_TASKS = {
    'proxy_verify': False,
    'site_check': False,
    'current_sites': 0,
    'current_proxies': 0,
}

# ==========================================
# 📱 TELEGRAM LOGGING HANDLER
# ==========================================
class TelegramLogHandler(logging.Handler):
    def __init__(self, bot, chat_id, buffer_size=3):
        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.buffer = []
        self.buffer_size = buffer_size
        self.last_send = time.time()
        self.lock = threading.Lock()
    
    def emit(self, record):
        try:
            with self.lock:
                msg = self.format(record)
                self.buffer.append(msg)
                
                if len(self.buffer) >= self.buffer_size or (time.time() - self.last_send) > 2:
                    self.flush_buffer()
        except:
            pass
    
    def flush_buffer(self):
        try:
            if not self.buffer:
                return
            
            text = "\n".join(self.buffer)
            
            if len(text) > 4000:
                for i in range(0, len(text), 3900):
                    chunk = text[i:i+3900]
                    try:
                        self.bot.send_message(self.chat_id, f"<code>{chunk}</code>", parse_mode='HTML')
                        time.sleep(0.1)
                    except:
                        pass
            else:
                self.bot.send_message(self.chat_id, f"<code>{text}</code>", parse_mode='HTML')
            
            self.buffer = []
            self.last_send = time.time()
        except:
            pass

# ==========================================
# 🔧 LOGGING SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ultra_bot.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ==========================================
# 🎯 GATEWAY SIGNATURES
# ==========================================
GATEWAY_SIGNATURES = {
    'THANK YOU': 'Approved',
    'ORDER CONFIRM': 'Approved',
    'APPROVED': 'Approved',
    'AUTHORIZED': 'Approved',
    'ACCEPTED': 'Approved',
    '3D': 'OTP Required',
    'OTP': 'OTP Required',
    'CHALLENGE': 'OTP Required',
    'VERIFY': 'OTP Required',
    'REDIRECT': 'OTP Required',
    'CAPTCHA': 'CAPTCHA Protected',
    'ROBOT': 'CAPTCHA Protected',
    'RECAPTCHA': 'CAPTCHA Protected',
    'VERIFICATION': 'CAPTCHA Protected',
    'CHALLENGE-REQUIRED': 'CAPTCHA Protected',
    'GATED': 'Gated/Locked',
    'LOCKED': 'Gated/Locked',
    'PAUSED': 'Gated/Locked',
    'RESTRICTED': 'Gated/Locked',
    'MAINTENANCE': 'Gated/Locked',
}

DEAD_SIGNALS = {
    'DECLINED': 'Declined',
    'DENIED': 'Denied',
    'FAILED': 'Failed',
    'ERROR': 'Error',
    'TIMEOUT': 'Timeout',
    'CONNECTION': 'Connection Error',
    'REFUSED': 'Connection Refused',
    'INVALID': 'Invalid',
    'EXPIRED': 'Card Expired',
}

# ==========================================
# 💾 FILE MANAGEMENT
# ==========================================

def load_verified_proxies():
    global VERIFIED_PROXIES
    if os.path.exists(VERIFIED_PROXIES_FILE):
        try:
            with open(VERIFIED_PROXIES_FILE, 'r') as f:
                VERIFIED_PROXIES = [line.strip() for line in f.readlines() if line.strip()]
            logger.info(f"✅ Loaded {len(VERIFIED_PROXIES)} verified proxies")
            return len(VERIFIED_PROXIES)
        except:
            return 0
    return 0

def save_verified_proxies():
    try:
        with open(VERIFIED_PROXIES_FILE, 'w') as f:
            for proxy in VERIFIED_PROXIES:
                f.write(proxy + '\n')
        logger.info(f"✅ Saved {len(VERIFIED_PROXIES)} verified proxies")
        return True
    except:
        return False

# ==========================================
# 🌐 FLASK KEEP-ALIVE
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return f"🔥 SHOPIFY BOT v2.0 | Verified: {len(VERIFIED_PROXIES)} | Production Ready", 200

def run_web_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except:
        pass

def start_keep_alive():
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()

# ==========================================
# 🔧 PROXY UTILITIES
# ==========================================

def is_proxy_line(line):
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
    line = line.strip().lower()
    if not '.' in line or len(line) < 4:
        return False
    tlds = ['.com', '.net', '.org', '.io', '.co', '.shop', '.store', '.xyz', '.dev', '.uk', '.us', '.ca', '.fr', '.de', '.app', '.in', '.ga', '.cf']
    if any(tld in line for tld in tlds):
        return True
    if '.' in line and not ':' in line:
        return True
    return False

def test_proxy_quick_connect(proxy):
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
    global VERIFIED_PROXIES
    ACTIVE_TASKS['proxy_verify'] = True
    ACTIVE_TASKS['current_proxies'] = len(proxies)
    
    logger.info(f"🔌 Starting proxy verification for {len(proxies)} proxies")
    
    if message:
        try:
            status_msg = bot.send_message(message.chat.id, f"⚡ <b>VERIFYING {len(proxies)} PROXIES</b>\n🔄 {PROXY_CHECK_THREADS} threads...", parse_mode='HTML')
        except:
            status_msg = None
    else:
        status_msg = None
    
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
            if status_msg and time.time() - last_update > 2:
                try:
                    pct = int((checked / total) * 100)
                    bot.edit_message_text(
                        f"⚡ <b>PROXY VERIFICATION</b>\n✅ Alive: {len(verified)}\n💀 Dead: {checked - len(verified)}\n📊 {pct}%",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode='HTML'
                    )
                    last_update = time.time()
                except:
                    pass
    
    VERIFIED_PROXIES.extend(verified)
    save_verified_proxies()
    
    logger.info(f"✅ Proxy verification complete! Verified: {len(verified)}/{total}")
    
    if status_msg:
        try:
            bot.edit_message_text(
                f"✅ <b>PROXY VERIFICATION COMPLETE!</b>\n✅ Verified: {len(verified)}\n💀 Dead: {total - len(verified)}\n📊 Total Saved: {len(VERIFIED_PROXIES)}",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
        except:
            pass
    
    ACTIVE_TASKS['proxy_verify'] = False
    ACTIVE_TASKS['current_proxies'] = 0
    return verified

# ==========================================
# 🔍 ADVANCED SHOPIFY PRODUCT DETECTOR v2.0
# ==========================================

def create_session(shop_url, proxies=None):
    """Create session with proper headers"""
    session = requests.Session()
    session.trust_env = False if proxies else True
    session.headers.update({
        'User-Agent': USER_AGENTS.random,
        'Accept': 'application/json',
        'Accept-Language': 'en-US',
        'Content-Type': 'application/json',
        'Origin': shop_url,
        'Referer': f'{shop_url}/',
    })
    
    if proxies:
        try:
            session.proxies.update(proxies)
        except Exception:
            pass
    
    return session

def get_cheapest_product(session, shop_url):
    """Auto-detect cheapest product on Shopify store - FIXED VERSION"""
    
    logger.info(f"🔎 Scanning: {shop_url}")
    
    all_products = []
    
    def extract_products(products_list):
        """Extract all available products with prices"""
        candidates = []
        
        for product in products_list or []:
            try:
                pid = str(product.get('id') or "")
                title = product.get('title', 'Unknown')
                variants = product.get('variants') or []
                
                if not pid:
                    continue
                
                # CASE 1: Has variants
                if variants:
                    for v in variants:
                        try:
                            vid = str(v.get('id') or "")
                            price_str = str(v.get('price') or v.get('price_amount') or "0")
                            
                            try:
                                price = float(price_str)
                            except (ValueError, TypeError):
                                continue
                            
                            if price <= 0:
                                continue
                            
                            available = v.get('available', None)
                            
                            if available is None:
                                inv_q = v.get('inventory_quantity')
                                inv_pol = (v.get('inventory_policy') or "").lower()
                                available = (isinstance(inv_q, (int, float)) and inv_q > 0) or inv_pol == "continue"
                            
                            if not available:
                                continue
                            
                            candidate = {
                                'product_id': pid,
                                'variant_id': vid,
                                'price': price,
                                'price_str': price_str,
                                'title': title
                            }
                            
                            candidates.append(candidate)
                            all_products.append(candidate)
                        except Exception:
                            continue
                
                # CASE 2: No variants but product-level price
                else:
                    try:
                        price = None
                        price_str = None
                        
                        if 'price' in product:
                            price_str = str(product.get('price', '0'))
                            try:
                                price = float(price_str)
                            except:
                                price = None
                        
                        if price is None and 'price_min' in product:
                            price_str = str(product.get('price_min', '0'))
                            try:
                                price = float(price_str)
                            except:
                                price = None
                        
                        if price is None or price <= 0:
                            continue
                        
                        vid = str(pid)
                        
                        candidate = {
                            'product_id': pid,
                            'variant_id': vid,
                            'price': price,
                            'price_str': price_str,
                            'title': title
                        }
                        
                        candidates.append(candidate)
                        all_products.append(candidate)
                    except (ValueError, TypeError):
                        continue
            
            except Exception:
                continue
        
        if candidates:
            candidates.sort(key=lambda x: x['price'])
            return candidates[0]
        
        return None
    
    # TRY 1: /products.json
    try:
        time.sleep(random.uniform(0.3, 0.8))
        url = f"{shop_url}/products.json?limit=250"
        r = session.get(url, timeout=HTTP_TIMEOUT_SHORT, verify=False)
        
        if r.status_code == 200:
            data = r.json()
            products = data if isinstance(data, list) else data.get('products', [])
            
            if products:
                result = extract_products(products)
                if result:
                    logger.info(f"✅ Found: {result['title']} (${result['price_str']})")
                    return result
    except Exception:
        pass
    
    # TRY 2: /collections/all/products.json
    try:
        time.sleep(random.uniform(0.3, 0.8))
        url = f"{shop_url}/collections/all/products.json?limit=250"
        r = session.get(url, timeout=HTTP_TIMEOUT_SHORT, verify=False)
        
        if r.status_code == 200:
            data = r.json()
            products = data if isinstance(data, list) else data.get('products', [])
            
            if products:
                result = extract_products(products)
                if result:
                    logger.info(f"✅ Found: {result['title']} (${result['price_str']})")
                    return result
    except Exception:
        pass
    
    # TRY 3: Sitemap
    handles = []
    try:
        url = f"{shop_url}/sitemap_products_1.xml"
        r = session.get(url, timeout=HTTP_TIMEOUT_SHORT, verify=False)
        
        if r.status_code == 200 and r.text:
            try:
                root = ET.fromstring(r.text)
                ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                
                for loc in root.findall('.//sm:url/sm:loc', ns):
                    loc_text = (loc.text or "").strip()
                    
                    if not loc_text:
                        continue
                    
                    m = re.search(r"/products/([^/?#]+)", loc_text)
                    
                    if m:
                        handles.append(m.group(1))
                    
                    if len(handles) >= 20:
                        break
            except Exception:
                pass
    except Exception:
        pass
    
    best = None
    for handle in handles:
        try:
            url = f"{shop_url}/products/{handle}.js"
            r = session.get(url, timeout=HTTP_TIMEOUT_MEDIUM, verify=False)
            
            if r.status_code != 200:
                continue
            
            data = r.json()
            product = {
                "id": data.get('id'),
                "title": data.get('title'),
                "variants": data.get('variants', [])
            }
            
            cand = extract_products([product])
            
            if cand and ((best is None) or cand['price'] < best['price']):
                best = cand
        except Exception:
            continue
    
    if best:
        logger.info(f"✅ Found via sitemap: {best['title']} (${best['price_str']})")
        return best
    
    # Return first product if any found
    if all_products:
        all_products.sort(key=lambda x: x['price'])
        logger.info(f"✅ Found: {all_products[0]['title']} (${all_products[0]['price_str']})")
        return all_products[0]
    
    logger.warning(f"❌ No products found: {shop_url}")
    return None

def parse_response(response_text, status_code):
    """Parse site response to determine store status"""
    if not response_text:
        if status_code == 403:
            return ("BLOCKED", "403 Forbidden", "Unknown")
        elif status_code == 404:
            return ("DEAD", "404 Not Found", "Unknown")
        elif status_code >= 500:
            return ("DEAD", f"HTTP {status_code}", "Unknown")
        else:
            return ("DEAD", f"HTTP {status_code}", "Unknown")
    
    response_upper = response_text.upper()
    
    # 🚨 CAPTCHA (FIRST PRIORITY)
    captcha_signals = [
        'RECAPTCHA', 'CAPTCHA', 'BOT CHECK', 'ROBOT CHECK', 
        'VERIFY HUMAN', 'CHALLENGE-REQUIRED', 'CLOUDFLARE', 'WAF',
        'I\'M NOT A ROBOT', 'CHALLENGE_VALIDATION', 'CF_CLEARANCE', 'AKAMAI',
        '_CHALLENGE_TOKEN', 'CF_BOT_MANAGEMENT', 'BLOCKED_BY_WAF', 'AKAM'
    ]
    
    for signal in captcha_signals:
        if signal in response_upper:
            return ("CAPTCHA", f"CAPTCHA - {signal}", "Unknown")
    
    # 🔐 PASSWORD/GATED
    if 'PASSWORD' in response_upper or 'AUTHENTICATE' in response_upper:
        return ("GATED", "Password Protected", "Locked")
    
    if 'COMING SOON' in response_upper or 'MAINTENANCE' in response_upper:
        return ("GATED", "Maintenance Mode", "Locked")
    
    # 💳 GATEWAY DETECTION
    gateway_map = {
        'STRIPE': 'Stripe',
        'STRIPE_SIGNATURE': 'Stripe',
        'STRIPE.COM': 'Stripe',
        'SHOPIFY_PAYMENTS': 'Shopify Payments',
        'SHOPIFY PAY': 'Shopify Pay',
        'PAYPAL': 'PayPal',
        'SQUARE': 'Square',
        'BRAINTREE': 'Braintree',
        'AUTHORIZE.NET': 'Authorize.net',
        'AMAZON PAY': 'Amazon Pay',
        'ADYEN': 'Adyen',
    }
    
    for signal, gateway in gateway_map.items():
        if signal in response_upper:
            return ("LIVE", f"Gateway: {gateway} ✅", gateway)
    
    # ✅ GENERAL LIVE DETECTION
    if any(x in response_upper for x in ['SHOPIFY', 'CDN.SHOPIFY.COM', 'MYSHOPIFY']):
        if len(response_text) > 500:
            return ("LIVE", "Shopify Store ✅", "Shopify")
    
    # 💀 DEAD KEYWORDS
    dead_keywords = [
        'DECLINED', 'DENIED', 'FAILED', 'ERROR', 'TIMEOUT',
        'CONNECTION REFUSED', 'INVALID', 'EXPIRED', 'CLOSED',
        'SUSPENDED', 'DISABLED', 'DEACTIVATED', 'REMOVED'
    ]
    
    for signal in dead_keywords:
        if signal in response_upper:
            return ("DEAD", signal, "Unknown")
    
    if len(response_text) < 200:
        return ("DEAD", "Minimal Response", "Unknown")
    
    return ("UNKNOWN", f"HTTP {status_code}", "Unknown")

def check_site(site_url, proxy=None):
    """Check single Shopify site"""
    try:
        site_url = site_url.strip()
        if site_url.startswith('https://'):
            site_url = site_url.replace('https://', '')
        if site_url.startswith('http://'):
            site_url = site_url.replace('http://', '')
        site_url = site_url.rstrip('/')
        
        site_full = f"https://{site_url}"
        
        headers = {
            'User-Agent': USER_AGENTS.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
        }
        
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
                r = requests.get(site_full, headers=headers, proxies=proxy_dict, timeout=REQUEST_TIMEOUT, verify=False, allow_redirects=True)
            else:
                r = requests.get(site_full, headers=headers, timeout=REQUEST_TIMEOUT, verify=False, allow_redirects=True)
        else:
            r = requests.get(site_full, headers=headers, timeout=REQUEST_TIMEOUT, verify=False, allow_redirects=True)
        
        status, msg, gateway = parse_response(r.text, r.status_code)
        return (status, msg, gateway)
    
    except requests.exceptions.Timeout:
        return ("DEAD", "Timeout", "Unknown")
    except requests.exceptions.ConnectionError:
        return ("DEAD", "Connection Error", "Unknown")
    except Exception as e:
        return ("DEAD", str(e)[:30], "Unknown")

# ==========================================
# 🧵 BULK CHECKER
# ==========================================

def run_bulk_check(message, sites):
    """Run bulk site check"""
    
    ACTIVE_TASKS['site_check'] = True
    ACTIVE_TASKS['current_sites'] = len(sites)
    
    logger.info("=" * 80)
    logger.info(f"🔥 CHECKING: {len(sites)} SITES")
    logger.info("=" * 80)
    
    if not sites:
        logger.error("❌ No sites")
        ACTIVE_TASKS['site_check'] = False
        return
    
    if not VERIFIED_PROXIES:
        logger.error(f"❌ NO PROXIES!")
        try:
            bot.send_message(message.chat.id, "⚠️ NO PROXIES! Upload proxies first!", parse_mode='HTML')
        except:
            pass
        ACTIVE_TASKS['site_check'] = False
        return
    
    logger.info(f"✅ Proxies: {len(VERIFIED_PROXIES)} | Threads: {MAX_THREADS}")
    
    try:
        bot.send_message(message.chat.id, f"🔥 CHECKING {len(sites)} SITES\n🔌 {len(VERIFIED_PROXIES)} Proxies\n📱 Logs: LIVE below\n⏱️ Starting...", parse_mode='HTML')
    except:
        pass
    
    live_sites = []
    stats = {'live': 0, 'dead': 0, 'captcha': 0, 'otp': 0, 'gated': 0, 'blocked': 0, 'error': 0, 'unknown': 0}
    checked = 0
    total = len(sites)
    start_time = time.time()
    status_msg = None
    
    try:
        status_msg = bot.send_message(message.chat.id, "🔄 Initializing...", parse_mode='HTML')
    except:
        pass
    
    chunks = [sites[i:i+CHUNK_SIZE] for i in range(0, len(sites), CHUNK_SIZE)]
    logger.info(f"📊 {len(chunks)} chunks created")
    
    try:
        for chunk_idx, chunk in enumerate(chunks):
            logger.info(f"📦 Chunk {chunk_idx + 1}/{len(chunks)}")
            
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                futures = {}
                for site in chunk:
                    proxy = random.choice(VERIFIED_PROXIES) if VERIFIED_PROXIES else None
                    futures[executor.submit(check_site, site, proxy)] = site
                
                for future in as_completed(futures):
                    try:
                        status, msg, gateway = future.result()
                        site = futures[future]
                        checked += 1
                        
                        if status == "LIVE":
                            stats['live'] += 1
                            live_data = f"{site} | {gateway} | {msg}"
                            live_sites.append(live_data)
                            logger.info(f"✅ LIVE: {site} | {gateway}")
                            if len(live_sites) % BATCH_SEND == 0:
                                send_batch_results(message.chat.id, live_sites[-BATCH_SEND:], stats['live'])
                        elif status == "CAPTCHA":
                            stats['captcha'] += 1
                        elif status == "OTP":
                            stats['otp'] += 1
                        elif status == "GATED":
                            stats['gated'] += 1
                        elif status == "BLOCKED":
                            stats['blocked'] += 1
                        elif status == "ERROR":
                            stats['error'] += 1
                        elif status == "UNKNOWN":
                            stats['unknown'] += 1
                        else:
                            stats['dead'] += 1
                        
                        if checked % 50 == 0:
                            pct = int((checked / total) * 100) if total > 0 else 0
                            elapsed = int(time.time() - start_time)
                            speed = checked // max(elapsed, 1)
                            
                            logger.info(f"📊 {checked}/{total} ({pct}%) | LIVE: {stats['live']} | {speed}/s")
                            
                            if status_msg:
                                try:
                                    bar = "█" * int(pct/10) + "░" * (10-int(pct/10))
                                    bot.edit_message_text(
                                        f"🔥 CHECKING\n<code>{bar}</code> {pct}%\n📊 {checked}/{total}\n✅ LIVE: {stats['live']}\n🛡️ CAPTCHA: {stats['captcha']}\n💀 DEAD: {stats['dead']}\n⏱️ {elapsed}s ({speed}/s)",
                                        message.chat.id,
                                        status_msg.message_id,
                                        parse_mode='HTML'
                                    )
                                except:
                                    pass
                    except:
                        pass
            
            gc.collect()
            time.sleep(0.1)
        
        elapsed = int(time.time() - start_time)
        speed = total // max(elapsed, 1)
        
        logger.info("=" * 80)
        logger.info("✅ CHECK COMPLETE!")
        logger.info(f"✅ LIVE: {stats['live']} | 🛡️ CAPTCHA: {stats['captcha']} | 💀 DEAD: {stats['dead']}")
        logger.info(f"⏱️ {elapsed}s | ⚡ {speed} sites/sec")
        logger.info("=" * 80)
        
        final_report = f"""
✅ <b>CHECK COMPLETE!</b>

📊 <b>RESULTS:</b>
✅ LIVE: <code>{stats['live']}</code>
🛡️ CAPTCHA: <code>{stats['captcha']}</code>
🔐 OTP/3D: <code>{stats['otp']}</code>
🔒 GATED: <code>{stats['gated']}</code>
⛔ BLOCKED: <code>{stats['blocked']}</code>
💀 DEAD: <code>{stats['dead']}</code>

⏱️ Time: <code>{elapsed}s</code> | Speed: <code>{speed}/s</code>
🔥 Mode: Production Ready
"""
        
        try:
            bot.send_message(message.chat.id, final_report, parse_mode='HTML')
        except:
            pass
        
        if live_sites and len(live_sites) % BATCH_SEND != 0:
            remaining = len(live_sites) % BATCH_SEND
            send_batch_results(message.chat.id, live_sites[-remaining:], stats['live'])
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        try:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}", parse_mode='HTML')
        except:
            pass
    
    finally:
        ACTIVE_TASKS['site_check'] = False
        ACTIVE_TASKS['current_sites'] = 0

def send_batch_results(chat_id, sites, total):
    try:
        text = "\n".join(sites)
        filename = f"live_sites_{int(time.time())}.txt"
        with open(filename, 'w') as f:
            f.write(text)
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✅ Live Sites | Total: {total}")
        os.remove(filename)
        logger.info(f"📤 Batch sent ({len(sites)} sites)")
    except Exception as e:
        logger.error(f"❌ Send error: {e}")

# ==========================================
# 🤖 BOT HANDLERS
# ==========================================

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, """
🔥 <b>SHOPIFY MASS SITE FINDER BOT v2.0</b>

✅ WORKING PRODUCT DETECTION
✅ REAL GATEWAY IDENTIFICATION
✅ TELEGRAM LIVE LOGS
✅ 200 PARALLEL THREADS
✅ 500+ SITES/MIN

📤 <b>STEPS:</b>
1️⃣ Upload proxies.txt
2️⃣ Upload sites.txt
3️⃣ LIVE logs below!

/proxies /load /clear /stats
""", parse_mode='HTML')

@bot.message_handler(commands=['proxies', 'showproxy'])
def show_proxies(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    if not VERIFIED_PROXIES:
        bot.reply_to(m, "❌ No proxies", parse_mode='HTML')
        return
    
    msg = f"🔌 {len(VERIFIED_PROXIES)} Proxies:\n\n"
    for i, proxy in enumerate(VERIFIED_PROXIES[:10], 1):
        msg += f"{i}. {proxy}\n"
    
    bot.reply_to(m, msg, parse_mode='HTML')

@bot.message_handler(commands=['load'])
def load_proxies(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    count = load_verified_proxies()
    bot.reply_to(m, f"✅ Loaded {count} proxies" if count > 0 else "❌ No saved proxies", parse_mode='HTML')

@bot.message_handler(commands=['clear'])
def clear_proxies(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    VERIFIED_PROXIES.clear()
    bot.reply_to(m, "✅ Cleared", parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def show_stats(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    bot.reply_to(m, f"""
📊 <b>BOT STATS:</b>

✅ Verified: {len(VERIFIED_PROXIES)}
🔥 Threads: {MAX_THREADS}
⏱️ Timeout: {REQUEST_TIMEOUT}s

🧵 Status:
• Check: {'🔴 Running' if ACTIVE_TASKS['site_check'] else '⚪ Idle'}
• Verify: {'🔴 Running' if ACTIVE_TASKS['proxy_verify'] else '⚪ Idle'}
""", parse_mode='HTML')

@bot.message_handler(content_types=['document'])
def handle_file(m):
    global LOG_CHAT_ID, TELEGRAM_HANDLER
    
    if str(m.from_user.id) != str(OWNER_ID):
        bot.reply_to(m, "❌ Unauthorized", parse_mode='HTML')
        return
    
    if LOG_CHAT_ID is None:
        LOG_CHAT_ID = m.chat.id
        TELEGRAM_HANDLER = TelegramLogHandler(bot, LOG_CHAT_ID, buffer_size=3)
        TELEGRAM_HANDLER.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
        TELEGRAM_HANDLER.setFormatter(formatter)
        logger.addHandler(TELEGRAM_HANDLER)
        logger.info("📱 TELEGRAM LOGGING ACTIVATED!")
        time.sleep(1)
    
    try:
        logger.info(f"📥 File: {m.document.file_name}")
        file_info = bot.get_file(m.document.file_id)
        data = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
        
        lines = [line.strip() for line in data.split('\n') if line.strip()]
        logger.info(f"📊 {len(lines)} lines")
        
        proxy_lines = [l for l in lines if is_proxy_line(l)]
        site_lines = [l for l in lines if is_site_line(l)]
        
        logger.info(f"📋 {len(proxy_lines)} proxies, {len(site_lines)} sites")
        
        if len(proxy_lines) > len(site_lines) and len(proxy_lines) > 0:
            PROXY_POOL.extend(proxy_lines)
            bot.reply_to(m, f"📥 {len(proxy_lines)} PROXIES\n🔄 Verifying...", parse_mode='HTML')
            logger.info(f"🔌 Starting verification...")
            threading.Thread(target=verify_proxy_batch, args=(proxy_lines, m), daemon=True).start()
        
        elif len(site_lines) > 0:
            formatted_sites = [l.replace('https://', '').replace('http://', '').rstrip('/') for l in site_lines]
            
            bot.reply_to(m, f"📥 {len(formatted_sites)} SITES\n🔥 Starting check!", parse_mode='HTML')
            logger.info(f"🌐 Starting check...")
            threading.Thread(target=run_bulk_check, args=(m, formatted_sites), daemon=True).start()
        
        else:
            bot.reply_to(m, f"❌ No data!\n📊 {len(proxy_lines)} proxies, {len(site_lines)} sites", parse_mode='HTML')
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        bot.reply_to(m, f"❌ Error: {str(e)[:100]}", parse_mode='HTML')

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔥 SHOPIFY MASS SITE FINDER BOT v2.0 - PRODUCTION READY")
    logger.info("=" * 80)
    
    initial_count = load_verified_proxies()
    logger.info(f"✅ Loaded {initial_count} proxies")
    
    start_keep_alive()
    logger.info("✅ Keep-alive started")
    logger.info("🤖 Bot ready! Send files to start!")
    
    bot.infinity_polling()
