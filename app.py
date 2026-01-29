import telebot
import threading
import time
import os
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# CONFIG
# ==========================================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 5963548505

MAX_THREADS = 50
REQUEST_TIMEOUT = 10

bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
VERIFIED_PROXIES = []

# ==========================================
# SIMPLE COMMANDS
# ==========================================

@bot.message_handler(commands=['start'])
def start(m):
    """Start command"""
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    text = """
🔥 SHOPIFY SITE CHECKER v6.0

✅ /stats - Show statistics
✅ /proxies - List loaded proxies
✅ /clear - Clear all

📤 Send sites.txt file to check sites
Full gateway detection included!
"""
    bot.reply_to(m, text)

@bot.message_handler(commands=['stats'])
def stats(m):
    """Stats command"""
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    text = f"📊 Proxies: {len(VERIFIED_PROXIES)}\n✅ Threads: {MAX_THREADS}"
    bot.reply_to(m, text)

@bot.message_handler(commands=['proxies'])
def proxies(m):
    """Show proxies"""
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    if not VERIFIED_PROXIES:
        bot.reply_to(m, "❌ No proxies")
        return
    
    text = f"🔌 {len(VERIFIED_PROXIES)} proxies:\n\n"
    for i, p in enumerate(VERIFIED_PROXIES[:5], 1):
        text += f"{i}. {p}\n"
    
    bot.reply_to(m, text)

@bot.message_handler(commands=['clear'])
def clear(m):
    """Clear proxies"""
    if str(m.from_user.id) != str(OWNER_ID):
        return
    
    VERIFIED_PROXIES.clear()
    bot.reply_to(m, "✅ Cleared")

# ==========================================
# FULL SITE CHECKING LOGIC
# ==========================================

def check_site_gateway(site_url):
    """
    🔥 COMPLETE SITE CHECKING LOGIC
    Detects: Payment gateways, CAPTCHA, auth, redirects, content
    Returns: (status, gateway, details)
    """
    try:
        site_url = site_url.strip()
        if not site_url.startswith(('http://', 'https://')):
            site_url = f"https://{site_url}"
        
        site_url = site_url.rstrip('/')
        
        # Enhanced headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        r = requests.get(site_url, headers=headers, timeout=REQUEST_TIMEOUT, verify=False, allow_redirects=True)
        
        response_text = r.text
        response_upper = response_text.upper()
        
        # ========== PAYMENT GATEWAY DETECTION ==========
        gateways = [
            ('STRIPE_SIGNATURE', 'Stripe'),
            ('STRIPE.COM', 'Stripe'),
            ('STRIPE"', 'Stripe'),
            ('STRIPE\'', 'Stripe'),
            ('STRIPE_PUBLISHABLE', 'Stripe'),
            ('PAYPAL', 'PayPal'),
            ('SQUARE', 'Square'),
            ('BRAINTREE', 'Braintree'),
            ('AUTHORIZE.NET', 'Authorize.net'),
            ('ADYEN', 'Adyen'),
            ('WORLDPAY', 'Worldpay'),
            ('2CHECKOUT', '2Checkout'),
            ('PAYMENT_METHOD', 'Payment Gateway'),
            ('CREDIT_CARD', 'Credit Card'),
            ('CHECKOUT', 'Checkout Active'),
            ('ADD_TO_CART', 'Shopping Cart'),
        ]
        
        for signal, name in gateways:
            if signal in response_upper:
                return ("LIVE", name, f"✅ {name}")
        
        # ========== SHOPIFY SPECIFIC ==========
        if 'SHOPIFY' in response_upper:
            if any(x in response_upper for x in ['CDN.SHOPIFY.COM', 'MYSHOPIFY', 'SHOPIFY PAY']):
                if len(response_text) > 1000:
                    return ("LIVE", "Shopify", "✅ Shopify store")
        
        # ========== SECURITY & CAPTCHA ==========
        captcha_signals = [
            'RECAPTCHA', 'CAPTCHA', 'BOT_CHECK', 'VERIFY YOU',
            'ROBOT', 'CHALLENGE', 'CLOUDFLARE', 'CF_CLEARANCE',
            'WAF', 'INCAPSULA', 'AKAMAI', 'SHIELD',
        ]
        
        for signal in captcha_signals:
            if signal in response_upper:
                return ("CAPTCHA", "Protected", f"🛡️ {signal}")
        
        # ========== AUTHENTICATION ==========
        auth_signals = [
            'PASSWORD REQUIRED', 'AUTHENTICATE', 'LOGIN REQUIRED',
            'AUTHORIZATION', 'FORBIDDEN', 'ACCESS DENIED', 'RESTRICTED',
        ]
        
        for signal in auth_signals:
            if signal in response_upper:
                return ("GATED", "Auth", f"🔐 {signal}")
        
        # ========== MAINTENANCE / CLOSED ==========
        if 'COMING SOON' in response_upper or 'MAINTENANCE' in response_upper or 'CLOSED' in response_upper:
            return ("GATED", "Closed", "🔄 Not active")
        
        # ========== FORM DETECTION ==========
        if '<FORM' in response_upper and ('CHECKOUT' in response_upper or 'PAYMENT' in response_upper):
            return ("LIVE", "Checkout", "✅ Checkout found")
        
        # ========== STATUS CODE ==========
        if r.status_code == 404:
            return ("DEAD", "404", "❌ Not found")
        elif r.status_code in [403, 500, 503]:
            return ("DEAD", f"{r.status_code}", f"❌ Error")
        elif r.status_code >= 400:
            return ("DEAD", f"HTTP {r.status_code}", f"❌ Error")
        
        # ========== REDIRECT CHECK ==========
        if r.history and len(r.history) > 5:
            return ("DEAD", "Redirects", f"🔄 Too many")
        
        if 'PARKED' in response_upper:
            return ("DEAD", "Parked", "📍 Parked")
        
        # ========== CONTENT SIZE ==========
        content_size = len(response_text)
        
        if content_size < 100:
            return ("DEAD", "Empty", "⚠️ No content")
        
        # ========== NEGATIVE KEYWORDS ==========
        negative = ['SUSPENDED', 'DISABLED', 'DEACTIVATED', 'EXPIRED', 'REMOVED']
        for word in negative:
            if word in response_upper:
                return ("DEAD", "Disabled", f"❌ {word}")
        
        # ========== POSITIVE INDICATORS ==========
        positive = ['PRODUCT', 'ADD TO CART', 'BUY NOW', 'ORDER', 'SHOP', 'PRICE', 'SALE']
        positive_count = sum(1 for word in positive if word in response_upper)
        
        if positive_count >= 2:
            return ("LIVE", "Store", "✅ Active")
        
        if content_size > 2000:
            return ("UNKNOWN", "Large", "⚠️ Manual check")
        
        return ("DEAD", "Unknown", "⚠️ Unknown")
    
    except requests.exceptions.Timeout:
        return ("DEAD", "Timeout", "⏱️ Timeout")
    except requests.exceptions.ConnectionError:
        return ("DEAD", "Connection", "🌐 Failed")
    except requests.exceptions.SSLError:
        return ("DEAD", "SSL", "🔒 SSL error")
    except Exception as e:
        return ("ERROR", "Error", str(e)[:30])

# ==========================================
# FILE HANDLER
# ==========================================

def is_site_line(line):
    """Detect if line is a domain"""
    line = line.strip().lower()
    if not line or len(line) < 4:
        return False
    
    line = line.replace('https://', '').replace('http://', '')
    line = line.split('/')[0]
    
    if '.' not in line:
        return False
    
    tlds = ['.com', '.net', '.org', '.io', '.co', '.shop', '.store', '.xyz', '.dev', '.myshopify', '.app']
    return any(tld in line for tld in tlds)

def check_sites_batch(sites, message):
    """Check all sites with LIVE progress updates"""
    
    live_sites = []
    stats = {'live': 0, 'captcha': 0, 'gated': 0, 'dead': 0, 'error': 0, 'unknown': 0}
    checked = 0
    total = len(sites)
    start_time = time.time()
    
    try:
        status_msg = bot.send_message(
            message.chat.id,
            f"🔥 Checking {total} sites...\n0/{total} (0%)",
            parse_mode='HTML'
        )
    except:
        status_msg = None
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {}
        for site in sites:
            futures[executor.submit(check_site_gateway, site)] = site
        
        for future in as_completed(futures):
            try:
                status, gateway, details = future.result()
                site = futures[future]
                checked += 1
                
                if status == "LIVE":
                    stats['live'] += 1
                    live_sites.append(f"{site} | {gateway}")
                    print(f"✅ LIVE: {site} | {gateway}")
                elif status == "CAPTCHA":
                    stats['captcha'] += 1
                elif status == "GATED":
                    stats['gated'] += 1
                elif status == "ERROR":
                    stats['error'] += 1
                elif status == "UNKNOWN":
                    stats['unknown'] += 1
                else:
                    stats['dead'] += 1
                
                # Update every 25 sites
                if checked % 25 == 0 and status_msg:
                    try:
                        elapsed = int(time.time() - start_time)
                        speed = checked // max(elapsed, 1)
                        pct = int((checked / total) * 100)
                        bar = "█" * int(pct/10) + "░" * (10-int(pct/10))
                        
                        bot.edit_message_text(
                            f"🔥 <b>CHECKING SITES</b>\n<code>{bar}</code> {pct}%\n\n"
                            f"📊 <b>Progress:</b> {checked}/{total}\n"
                            f"✅ <b>LIVE:</b> {stats['live']}\n"
                            f"🛡️ <b>CAPTCHA:</b> {stats['captcha']}\n"
                            f"🔒 <b>GATED:</b> {stats['gated']}\n"
                            f"💀 <b>DEAD:</b> {stats['dead']}\n\n"
                            f"⏱️ {elapsed}s | Speed: {speed}/s",
                            message.chat.id,
                            status_msg.message_id,
                            parse_mode='HTML'
                        )
                    except:
                        pass
            except:
                pass
    
    elapsed = int(time.time() - start_time)
    
    # Final report
    report = f"""
✅ <b>CHECK COMPLETE!</b>

📊 <b>FINAL RESULTS:</b>
✅ <b>LIVE:</b> <code>{stats['live']}</code>
🛡️ <b>CAPTCHA:</b> <code>{stats['captcha']}</code>
🔒 <b>GATED:</b> <code>{stats['gated']}</code>
💀 <b>DEAD:</b> <code>{stats['dead']}</code>
❓ <b>UNKNOWN:</b> <code>{stats['unknown']}</code>
⚠️ <b>ERROR:</b> <code>{stats['error']}</code>

⏱️ <b>Time:</b> <code>{elapsed}s</code>
📈 <b>Total:</b> <code>{checked}/{total}</code>
⚡ <b>Speed:</b> <code>{checked//max(elapsed,1)}/s</code>
"""
    
    try:
        bot.send_message(message.chat.id, report, parse_mode='HTML')
    except:
        pass
    
    # Export live sites
    if live_sites:
        try:
            filename = f"live_sites_{int(time.time())}.txt"
            with open(filename, 'w') as f:
                f.write("\n".join(live_sites))
            with open(filename, 'rb') as f:
                bot.send_document(message.chat.id, f, caption=f"✅ {len(live_sites)} LIVE SITES FOUND")
            os.remove(filename)
            print(f"✅ Exported {len(live_sites)} live sites")
        except:
            pass
    
    print(f"✅ Complete: {stats['live']} LIVE | {stats['captcha']} CAPTCHA | {stats['gated']} GATED | {stats['dead']} DEAD")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    """Handle file upload"""
    
    if str(message.from_user.id) != str(OWNER_ID):
        return
    
    print(f"📥 File: {message.document.file_name}")
    
    try:
        # Download file
        file_info = bot.get_file(message.document.file_id)
        file_data = bot.download_file(file_info.file_path)
        
        # Decode
        try:
            data = file_data.decode('utf-8', errors='ignore')
        except:
            data = str(file_data, errors='ignore')
        
        # Parse lines
        lines = [l.strip() for l in data.split('\n') if l.strip()]
        print(f"📊 Read {len(lines)} lines from file")
        
        # Detect sites
        sites = [l for l in lines if is_site_line(l)]
        print(f"🔍 Detected {len(sites)} sites")
        
        if len(sites) >= 1:
            # Clean URLs
            formatted_sites = [l.replace('https://', '').replace('http://', '').rstrip('/') for l in sites]
            
            bot.reply_to(
                message, 
                f"📥 <b>SITES DETECTED!</b>\n✅ Found: {len(formatted_sites)} sites\n🔥 Starting check with full logic...", 
                parse_mode='HTML'
            )
            print(f"🌐 Starting site check for {len(formatted_sites)} sites...")
            threading.Thread(target=check_sites_batch, args=(formatted_sites, message), daemon=True).start()
        
        else:
            print("❌ No valid sites detected")
            bot.reply_to(message, "❌ NO VALID SITES DETECTED", parse_mode='HTML')
    
    except Exception as e:
        print(f"❌ Error: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)[:100]}", parse_mode='HTML')

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    print("=" * 70)
    print("🔥 SHOPIFY SITE CHECKER BOT v6.0 - FULL COMPLEX LOGIC")
    print("=" * 70)
    print("✅ Complete gateway detection enabled")
    print("✅ CAPTCHA detection enabled")
    print("✅ Auth detection enabled")
    print("✅ Content analysis enabled")
    print("✅ Live progress updates enabled")
    print("✅ Ready for file uploads")
    print("=" * 70)
    
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Bot error: {e}")
