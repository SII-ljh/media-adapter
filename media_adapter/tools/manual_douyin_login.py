
import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(src_dir)

from playwright.async_api import async_playwright
from media_adapter.utils import utils
from media_adapter.utils.cookie_manager import get_cookie_manager, format_cookies_for_playwright

async def manual_login():
    print("=== Starting Manual Douyin Login Tool (Persistent Mode) ===")
    
    # 1. Setup Persistent User Data Directory
    # Matches logic in media_adapter/utils/browser_session.py
    user_data_base_dir = Path.home() / ".media_adapter" / "browser_data"
    douyin_user_data_dir = user_data_base_dir / "douyin"
    
    # Ensure directory exists
    if not douyin_user_data_dir.exists():
        douyin_user_data_dir.mkdir(parents=True, exist_ok=True)
        
    print(f"[Info] User Data Directory: {douyin_user_data_dir}")
    print("[Info] This logic guarantees strict session alignment with the main crawler.")

    cookies_dir = "./cookies"
    
    async with async_playwright() as p:
        # 2. Launch Browser with PERSISTENT CONTEXT
        # This is the key: it loads/saves to the specific folder, just like a real Chrome profile.
        print("[Info] Launching Chrome with Persistent Context...")
        
        # Args matched from browser_session.py to ensure identical fingerprint
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox", 
            "--disable-setuid-sandbox",
        ]
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(douyin_user_data_dir),
            headless=False, # Must be visible for manual login
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            args=args,
            ignore_default_args=["--enable-automation"],
        )
        
        # Get the page (persistent context usually opens one by default)
        pages = context.pages
        page = pages[0] if pages else await context.new_page()
        
        # 3. Go to Douyin
        print("[Info] Opening Douyin.com...")
        await page.goto("https://www.douyin.com", timeout=60000)
        
        # 4. Wait for user action
        print("\n" + "="*50)
        print("ACTION REQUIRED: Please scan the QR code in the browser window.")
        print("Once logged in, the session is saved PERMANENTLY in the folder.")
        print("The script will check for login status every 2 seconds.")
        print("="*50 + "\n")
        
        # 5. Polling for login
        max_wait = 600 # 10 minutes allow for slow scanning
        logged_in = False
        
        for i in range(max_wait // 2):
            # Check cookies for logic status
            cookies = await context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            
            is_login_cookie = cookie_dict.get("LOGIN_STATUS") == "1"
            is_login_local = False
            try:
                ls = await page.evaluate("() => window.localStorage")
                if ls.get("HasUserLogin") == "1":
                    is_login_local = True
            except:
                pass
                
            if(is_login_cookie or is_login_local):
                print(f"\n[Success] Login detected! (Cookie: {is_login_cookie}, LocalStorage: {is_login_local})")
                logged_in = True
                break
            
            sys.stdout.write(f"\rWaiting for login... {i*2}s")
            sys.stdout.flush()
            await asyncio.sleep(2)
            
        if not logged_in:
            print("\n[Error] Timeout waiting for login.")
            await context.close()
            return

        # 6. Save Cookies as Text backup (Optional but good for debug)
        # Even without this, the user_data_dir has already saved the session.
        # But we update the cookie file just in case other parts of the system read it.
        try:
           # Get current cookies
           all_cookies = await context.cookies()
           cookie_str = ""
           for c in all_cookies:
               cookie_str += f"{c['name']}={c['value']};"
           
           # Write to douyin_cookies.txt locally (relative to CWD)
           # Ensure ./cookies exists
           if not os.path.exists("./cookies"):
               os.makedirs("./cookies")

           with open("./cookies/douyin_cookies.txt", "w", encoding="utf-8") as f:
               f.write("# Auto-saved by manual_douyin_login.py\n")
               f.write(cookie_str)
               
           print(f"[Success] Cookies backed up to ./cookies/douyin_cookies.txt")
           
        except Exception as e:
            print(f"[Error] Failed to backup text cookies: {e}")
            
        print("\n[IMPORTANT]")
        print("Session data saved to: ~/.media_adapter/browser_data/douyin")
        print("You should NOT need to login again for this platform.")
        print("Closing in 3 seconds...")
            
        await asyncio.sleep(3)
        await context.close()
        print("=== Done ===")

if __name__ == "__main__":
    asyncio.run(manual_login())
