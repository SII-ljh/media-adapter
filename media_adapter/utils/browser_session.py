# -*- coding: utf-8 -*-
"""
Browser Session Manager for Media Adapter

Simple and reliable session management:
1. Read cookies from txt file
2. Try to login with cookies
3. If cookies expired, do QR login
4. Save new cookies back to file
"""

import asyncio
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    platform: str
    playwright: Any
    browser: Any
    context: Any
    page: Any
    client: Any
    cookie_str: str
    cookie_dict: Dict[str, str]
    created_at: datetime
    is_logged_in: bool = False


class BrowserSessionManager:
    """
    Simple browser session manager.

    - Uses cookies from txt file
    - Falls back to QR login if cookies expired
    - Saves new cookies back to file
    """

    def __init__(self):
        self._sessions: Dict[str, BrowserSession] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, platform: str) -> asyncio.Lock:
        if platform not in self._locks:
            self._locks[platform] = asyncio.Lock()
        return self._locks[platform]

    async def get_session(
        self,
        platform: str,
        headless: bool = False,
        cookies_dir: Optional[str] = None,
        force_new: bool = False,
    ) -> BrowserSession:
        """Get or create a browser session."""
        async with self._get_lock(platform):
            if platform in self._sessions and not force_new:
                session = self._sessions[platform]
                try:
                    await session.page.title()
                    return session
                except Exception:
                    await self._cleanup_session(platform)

            session = await self._create_session(platform, headless, cookies_dir)
            self._sessions[platform] = session
            return session

    async def _create_session(
        self,
        platform: str,
        headless: bool,
        cookies_dir: Optional[str],
    ) -> BrowserSession:
        """Create a new browser session."""
        from playwright.async_api import async_playwright
        from media_adapter.resources import get_stealth_js_path
        from media_adapter.utils.cookie_manager import (
            get_cookie_manager,
            parse_cookie_string,
            format_cookies_for_playwright,
        )
        from media_adapter import config

        platform_config = self._get_platform_config(platform)

        # Get cookie manager
        if cookies_dir:
            cookie_manager = get_cookie_manager(cookies_dir)
        else:
            cookie_manager = get_cookie_manager(getattr(config, "COOKIES_DIR", "./cookies"))

        # Read cookies from file
        cookie_str = cookie_manager.get_cookie(platform)
        if not cookie_str:
            cookie_str = getattr(config, "COOKIES", "")
        cookie_dict = parse_cookie_string(cookie_str)

        print(f"[BrowserSession] Starting browser for {platform}...")
        if cookie_str:
            print(f"[BrowserSession] Found cookies in file, will try to use them")
        else:
            print(f"[BrowserSession] No cookies found, will need to login")

        # Launch browser (fresh instance every time)
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        # Create context
        context = await browser.new_context(
            user_agent=platform_config["user_agent"],
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        # Add stealth script
        await context.add_init_script(path=get_stealth_js_path())

        # Inject cookies from file
        if cookie_str:
            print(f"[BrowserSession] Injecting cookies...")
            for domain in platform_config["cookie_domains"]:
                cookies = format_cookies_for_playwright(cookie_str, domain)
                if cookies:
                    await context.add_cookies(cookies)

        # Create page and navigate
        page = await context.new_page()

        print(f"[BrowserSession] Navigating to {platform_config['index_url']}...")
        try:
            await page.goto(
                platform_config["index_url"],
                wait_until="domcontentloaded",
                timeout=60000
            )
        except Exception:
            await page.goto(
                platform_config["index_url"],
                wait_until="load",
                timeout=60000
            )

        await asyncio.sleep(3)

        # Setup client and check/perform login
        client, is_logged_in = await self._setup_client_and_login(
            platform, context, page, cookie_str, cookie_dict, headless, cookie_manager
        )

        # Get final cookies
        from media_adapter.utils import utils
        final_cookie_str, final_cookie_dict = utils.convert_cookies(
            await context.cookies()
        )

        return BrowserSession(
            platform=platform,
            playwright=p,
            browser=browser,
            context=context,
            page=page,
            client=client,
            cookie_str=final_cookie_str,
            cookie_dict=final_cookie_dict,
            created_at=datetime.now(),
            is_logged_in=is_logged_in,
        )

    def _get_platform_config(self, platform: str) -> Dict[str, Any]:
        """Get platform-specific configuration."""
        configs = {
            "xhs": {
                "index_url": "https://www.xiaohongshu.com/explore",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "cookie_domains": [".xiaohongshu.com"],
            },
            "weibo": {
                "index_url": "https://m.weibo.cn",
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                "cookie_domains": [".weibo.cn", ".weibo.com"],
            },
            "douyin": {
                "index_url": "https://www.douyin.com",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "cookie_domains": [".douyin.com"],
            },
        }
        return configs.get(platform, configs["xhs"])

    async def _setup_client_and_login(
        self,
        platform: str,
        context: Any,
        page: Any,
        cookie_str: str,
        cookie_dict: Dict[str, str],
        headless: bool,
        cookie_manager: Any,
    ) -> Tuple[Any, bool]:
        """Setup client and perform login if needed."""
        if platform == "xhs":
            return await self._setup_xhs_client(context, page, cookie_str, cookie_dict, headless, cookie_manager)
        elif platform == "weibo":
            return await self._setup_weibo_client(context, page, cookie_str, cookie_dict, headless, cookie_manager)
        elif platform == "douyin":
            return await self._setup_douyin_client(context, page, cookie_str, cookie_dict, headless, cookie_manager)
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    async def _setup_xhs_client(
        self,
        context: Any,
        page: Any,
        cookie_str: str,
        cookie_dict: Dict[str, str],
        headless: bool,
        cookie_manager: Any,
    ) -> Tuple[Any, bool]:
        """Setup XHS client."""
        from media_adapter.platforms.xhs.client import XiaoHongShuClient
        from media_adapter.platforms.xhs.login import XiaoHongShuLogin
        from media_adapter.utils import utils
        from media_adapter import config

        # Get latest cookies from browser
        current_cookie_str, current_cookie_dict = utils.convert_cookies(
            await context.cookies()
        )
        if current_cookie_str:
            cookie_str = current_cookie_str
            cookie_dict = current_cookie_dict

        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.xiaohongshu.com",
            "referer": "https://www.xiaohongshu.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        client = XiaoHongShuClient(
            timeout=60,
            headers=headers,
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        # Check if logged in
        print("[XHS] Checking login status...")
        is_logged_in = await client.pong()

        if is_logged_in:
            print("[XHS] Cookie valid, already logged in")
        else:
            print("[XHS] Cookie invalid or expired, need to login...")

            if headless:
                print("[XHS] Warning: Headless mode - cannot do QR login")
                return client, False

            # QR login
            login_obj = XiaoHongShuLogin(
                login_type=config.LOGIN_TYPE,
                login_phone="",
                browser_context=context,
                context_page=page,
                cookie_str=cookie_str,
            )
            await login_obj.begin()

            # Update client
            await client.update_cookies(browser_context=context)
            is_logged_in = True
            print("[XHS] Login successful")

        # Save cookies to file
        if is_logged_in:
            new_cookie_str, _ = utils.convert_cookies(await context.cookies())
            if new_cookie_str:
                cookie_manager.save_cookie("xhs", new_cookie_str)
                print("[XHS] Cookies saved to file")

        return client, is_logged_in

    async def _setup_weibo_client(
        self,
        context: Any,
        page: Any,
        cookie_str: str,
        cookie_dict: Dict[str, str],
        headless: bool,
        cookie_manager: Any,
    ) -> Tuple[Any, bool]:
        """Setup Weibo client."""
        from media_adapter.platforms.weibo.client import WeiboClient
        from media_adapter.platforms.weibo.login import WeiboLogin
        from media_adapter.utils import utils
        from media_adapter import config

        mobile_url = "https://m.weibo.cn"
        pc_url = "https://weibo.com"

        # Get cookies for mobile site
        mobile_cookie_str, mobile_cookie_dict = utils.convert_cookies(
            await context.cookies(urls=[mobile_url])
        )
        if not mobile_cookie_str and cookie_str:
            mobile_cookie_str = cookie_str
            mobile_cookie_dict = cookie_dict

        headers = {
            "User-Agent": utils.get_mobile_user_agent(),
            "Origin": "https://m.weibo.cn",
            "Referer": "https://m.weibo.cn",
            "Content-Type": "application/json;charset=UTF-8",
        }
        if mobile_cookie_str:
            headers["Cookie"] = mobile_cookie_str

        client = WeiboClient(
            timeout=60,
            headers=headers,
            playwright_page=page,
            cookie_dict=mobile_cookie_dict,
        )

        # Check if logged in
        print("[Weibo] Checking login status...")
        is_logged_in = await client.pong()

        if is_logged_in:
            print("[Weibo] Cookie valid, already logged in")
        else:
            print("[Weibo] Cookie invalid or expired, need to login...")

            if headless:
                print("[Weibo] Warning: Headless mode - cannot do QR login")
                return client, False

            # Navigate to PC site for QR login
            await page.goto(pc_url)
            await asyncio.sleep(2)

            login_obj = WeiboLogin(
                login_type=config.LOGIN_TYPE,
                login_phone="",
                browser_context=context,
                context_page=page,
                cookie_str=cookie_str,
            )
            await login_obj.begin()

            # Go back to mobile site
            print("[Weibo] Redirecting to mobile site...")
            await page.goto(mobile_url)
            await asyncio.sleep(3)

            # Update client
            await client.update_cookies(browser_context=context, urls=[mobile_url])
            mobile_cookie_str, mobile_cookie_dict = utils.convert_cookies(
                await context.cookies(urls=[mobile_url])
            )
            client.headers["Cookie"] = mobile_cookie_str
            client.cookie_dict = mobile_cookie_dict
            is_logged_in = True
            print("[Weibo] Login successful")

        # Save cookies to file
        if is_logged_in:
            new_cookie_str, _ = utils.convert_cookies(await context.cookies())
            if new_cookie_str:
                cookie_manager.save_cookie("weibo", new_cookie_str)
                print("[Weibo] Cookies saved to file")

        return client, is_logged_in

    async def _setup_douyin_client(
        self,
        context: Any,
        page: Any,
        cookie_str: str,
        cookie_dict: Dict[str, str],
        headless: bool,
        cookie_manager: Any,
    ) -> Tuple[Any, bool]:
        """Setup Douyin client."""
        from media_adapter.platforms.douyin.client import DouYinClient
        from media_adapter.platforms.douyin.login import DouYinLogin
        from media_adapter.utils import utils
        from media_adapter import config

        # Get latest cookies from browser
        current_cookie_str, current_cookie_dict = utils.convert_cookies(
            await context.cookies()
        )
        if current_cookie_str:
            cookie_str = current_cookie_str
            cookie_dict = current_cookie_dict

        user_agent = await page.evaluate("() => navigator.userAgent")

        headers = {
            "User-Agent": user_agent,
            "Host": "www.douyin.com",
            "Origin": "https://www.douyin.com/",
            "Referer": "https://www.douyin.com/",
            "Content-Type": "application/json;charset=UTF-8",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        client = DouYinClient(
            timeout=60,
            headers=headers,
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        # Check if logged in
        print("[Douyin] Checking login status...")
        is_logged_in = await client.pong(browser_context=context)

        if is_logged_in:
            print("[Douyin] Cookie valid, already logged in")
        else:
            print("[Douyin] Cookie invalid or expired, need to login...")

            if headless:
                print("[Douyin] Warning: Headless mode - cannot do QR login")
                return client, False

            # QR login
            login_obj = DouYinLogin(
                login_type=config.LOGIN_TYPE,
                login_phone="",
                browser_context=context,
                context_page=page,
                cookie_str="",
            )
            await login_obj.begin()

            # Wait for login to complete
            await asyncio.sleep(3)

            # Update client
            await client.update_cookies(browser_context=context)
            new_cookie_str, new_cookie_dict = utils.convert_cookies(
                await context.cookies()
            )
            client.headers["Cookie"] = new_cookie_str
            client.cookie_dict = new_cookie_dict
            is_logged_in = True
            print("[Douyin] Login successful")

        # Save cookies to file
        if is_logged_in:
            new_cookie_str, _ = utils.convert_cookies(await context.cookies())
            if new_cookie_str:
                cookie_manager.save_cookie("douyin", new_cookie_str)
                print("[Douyin] Cookies saved to file")

        return client, is_logged_in

    async def _cleanup_session(self, platform: str):
        """Cleanup a specific session."""
        if platform in self._sessions:
            session = self._sessions[platform]
            try:
                await session.browser.close()
            except Exception:
                pass
            try:
                await session.playwright.stop()
            except Exception:
                pass
            del self._sessions[platform]

    async def close_session(self, platform: str):
        """Close a specific platform's session."""
        async with self._get_lock(platform):
            await self._cleanup_session(platform)

    async def close_all(self):
        """Close all sessions."""
        for platform in list(self._sessions.keys()):
            await self.close_session(platform)

    def has_session(self, platform: str) -> bool:
        """Check if a session exists for the platform."""
        return platform in self._sessions


# Global session manager instance
_session_manager: Optional[BrowserSessionManager] = None


def get_session_manager() -> BrowserSessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = BrowserSessionManager()
    return _session_manager


async def get_browser_session(
    platform: str,
    headless: bool = False,
    cookies_dir: Optional[str] = None,
    force_new: bool = False,
) -> BrowserSession:
    """Convenience function to get a browser session."""
    manager = get_session_manager()
    return await manager.get_session(platform, headless, cookies_dir, force_new)


async def close_browser_session(platform: str):
    """Close a browser session."""
    manager = get_session_manager()
    await manager.close_session(platform)


async def close_all_browser_sessions():
    """Close all browser sessions."""
    manager = get_session_manager()
    await manager.close_all()
