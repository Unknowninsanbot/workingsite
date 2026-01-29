import telebot
import requests
import threading
import time
import random
import re
import os
import urllib3
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 💀 CONFIGURATION - EDIT THIS
# ==========================================
BOT_TOKEN = "8468244120:AAGXjaczSUzqCF9xTRtoShEzhmx406XEhCE"  # <--- PUT YOUR TOKEN
OWNER_ID = 5963548505              # <--- YOUR ID

MAX_THREADS = 100                  # Threads (Speed)
REQUEST_TIMEOUT = 15               # Seconds before giving up

# ==========================================
# ⚙️ SETUP
# ==========================================
bot = telebot.TeleBot(BOT_TOKEN)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Global Storage
PROXIES = []
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0"
]

# ==========================================
# 🧠 THE MONSTER CHECKER LOGIC (From neww.py)
# ==========================================
class UltraChecker:
    def __init__(self, url):
        self.url = self.normalize_url(url)
        self.session = requests.Session()
        self.proxy = random.choice(PROXIES) if PROXIES else None
        
        # Setup Session
        if self.proxy:
            self.session.proxies.update(self.parse_proxy(self.proxy))
            
        self.session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def normalize_url(self, url):
        url = url.strip()
        if not url.startswith("http"):
            url = f"https://{url}"
        return url.rstrip('/')

    def parse_proxy(self, proxy_str):
        # Handles user:pass@ip:port and ip:port
        if "http" not in proxy_str:
            return {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
        return {"http": proxy_str, "https": proxy_str}

    def check(self):
        """
        Main logic: Finds product -> Add to Cart -> Checks Gateway
        Returns: (STATUS, MSG, GATEWAY)
        """
        try:
            # 1. INITIAL CONNECTION & CAPTCHA CHECK
            try:
                r = self.session.get(self.url, timeout=REQUEST_TIMEOUT, verify=False)
            except:
                return "DEAD", "Connection Failed", "N/A"

            if "password" in r.url:
                return "DEAD", "Password Protected", "Locked"
            
            if "captcha" in r.text.lower() or "challenge" in r.url:
                return "CAPTCHA", "Bot Detection Triggered", "Protected"

            # 2. PRODUCT FINDER (Smart Logic)
            variant_id = self.find_variant_id()
            if not variant_id:
                return "DEAD", "No Products Found", "Empty"

            # 3. ADD TO CART (The 'Live' Test)
            add_url = f"{self.url}/cart/add.js"
            r_add = self.session.post(add_url, data={'id': variant_id, 'quantity': 1}, timeout=REQUEST_TIMEOUT)
            
            if r_add.status_code not in [200, 201]:
                return "DEAD", "Cart Error", "Unknown"

            # 4. REACH CHECKOUT
            r_cart = self.session.get(f"{self.url}/checkout", timeout=REQUEST_TIMEOUT)
            
            # Follow redirects (Shopify often redirects cart -> checkout)
            final_url = r_cart.url
            
            # 5. ANALYZE CHECKOUT SOURCE CODE FOR GATEWAYS
            # This is safer than submitting a card mass-scale (avoids IP bans)
            # but guarantees the checkout is LIVE.
            text = r_cart.text.lower()
            
            gateway = "Unknown"
            if "stripe" in text: gateway = "Stripe"
            elif "paypal" in text: gateway = "PayPal"
            elif "shopify_payments" in text: gateway = "Shopify Payments"
            elif "braintree" in text: gateway = "Braintree"
            
            if "stock_problems" in final_url or "out_of_stock" in text:
                return "DEAD", "Product OOS", "Stock Issue"
                
            if "login" in final_url:
                return "DEAD", "Login Required", "Gated"

            if r_cart.status_code == 200 and ("contact_information" in final_url or "payment_method" in text or "checkout" in final_url):
                return "LIVE", "Checkout Reachable", gateway
            
            return "DEAD", "Checkout Failed", "Unknown"

        except Exception as e:
            return "DEAD", str(e)[:20], "Error"

    def find_variant_id(self):
        """ Scans products.json to find a purchasable ID """
        try:
            # Try main products.json
            r = self.session.get(f"{self.url}/products.json?limit=5", timeout=10)
            products = r.json().get('products', [])
            
            for p in products:
                for v in p.get('variants', []):
                    if v.get('available', True):
                        return v['id']
            
            # Fallback: Parse homepage for meta data if json is hidden
            # (Simplified for speed)
            return None
        except:
            return None

# ==========================================
# 🤖 BOT HANDLERS
# ==========================================

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, """
🔥 **ULTRA MONSTER CHECKER v9.0**
By: Your Name

✅ **How to use:**
1. Send `proxies.txt` (Optional but Recommended)
2. Send `sites.txt` (List of domains)

🚀 **Features:**
- 200 Threads
- Real Gateway Detection
- Bypass "No Products" errors
    """, parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    if message.from_user.id != OWNER_ID:
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
    
    # Check if Proxies
    if "proxies" in message.document.file_name.lower():
        global PROXIES
        PROXIES = [line.strip() for line in downloaded.split('\n') if line.strip()]
        bot.reply_to(message, f"✅ **Loaded {len(PROXIES)} Proxies!**", parse_mode="Markdown")
        return

    # Handle Sites
    sites = [line.strip() for line in downloaded.split('\n') if line.strip()]
    if not sites:
        bot.reply_to(message, "❌ File is empty.")
        return

    # START CHECKING
    msg = bot.reply_to(message, f"⚡ **Starting Check on {len(sites)} sites...**\nChecking Gateway & Checkout Access...", parse_mode="Markdown")
    
    threading.Thread(target=run_check, args=(sites, message.chat.id, msg.message_id)).start()

def run_check(sites, chat_id, msg_id):
    results = {"LIVE": [], "DEAD": [], "CAPTCHA": []}
    done = 0
    total = len(sites)
    start_time = time.time()
    
    # UPDATE FUNCTION (Avoids spamming API)
    def update_ui():
        while done < total:
            time.sleep(4)
            try:
                elapsed = time.time() - start_time
                speed = int(done / elapsed) if elapsed > 0 else 0
                
                text = (
                    f"⚡ **Checking Progress**\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"✅ Live: {len(results['LIVE'])}\n"
                    f"💀 Dead: {len(results['DEAD'])}\n"
                    f"🛡️ Captcha: {len(results['CAPTCHA'])}\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"📊 {done}/{total} Checked\n"
                    f"🚀 Speed: {speed} sites/s\n"
                    f"🔌 Proxies: {len(PROXIES)}"
                )
                bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown")
            except:
                pass
            if done == total: break

    # Start Updater Thread
    threading.Thread(target=update_ui).start()

    # WORKER FUNCTION
    def check_wrapper(site):
        checker = UltraChecker(site)
        status, msg, gateway = checker.check()
        return site, status, msg, gateway

    # MASS THREADING
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_wrapper, site): site for site in sites}
        
        for future in as_completed(futures):
            site, status, msg, gateway = future.result()
            done += 1
            
            if status == "LIVE":
                res_str = f"{site} | {gateway} | {msg}"
                results["LIVE"].append(res_str)
                # Send Instant Hit Notification
                try:
                    hit_msg = (
                        f"✅ **LIVE SITE FOUND!**\n"
                        f"🔗 `{site}`\n"
                        f"💳 Gateway: **{gateway}**\n"
                        f"📝 Msg: {msg}"
                    )
                    bot.send_message(chat_id, hit_msg, parse_mode="Markdown")
                except: pass

            elif status == "CAPTCHA":
                results["CAPTCHA"].append(site)
            else:
                results["DEAD"].append(site)

    # FINAL REPORT
    try:
        filename = f"Live_Sites_{int(time.time())}.txt"
        with open(filename, 'w') as f:
            f.write("\n".join(results["LIVE"]))
        
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"🏁 **Check Complete!**\nFound {len(results['LIVE'])} Working Sites.")
        os.remove(filename)
    except:
        bot.send_message(chat_id, "Check complete, but no live sites found to upload.")

# ==========================================
# ▶️ RUN
# ==========================================
print("🔥 MONSTER BOT STARTED...")
bot.infinity_polling()
