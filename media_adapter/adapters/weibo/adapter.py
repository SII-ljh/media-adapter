# -*- coding: utf-8 -*-
"""
Weibo Signal Source Adapter

Implements BaseSignalSource interface for Weibo platform.
Supports QR code login and search functionality.
"""

import asyncio
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from media_adapter.adapters.base import (
    BaseSignalSource,
    SignalEvent,
    AdapterTool,
    ToolResult,
)
from media_adapter.platforms.weibo.help import filter_search_result_card
from media_adapter.platforms.weibo.field import SearchType
from media_adapter.utils.cookie_manager import (
    get_cookie_manager,
    parse_cookie_string,
    format_cookies_for_playwright,
)
from media_adapter.utils.output_manager import get_output_manager
from media_adapter.utils.browser_session import (
    get_browser_session,
    close_browser_session,
    BrowserSession,
)


def _parse_cookie_string(cookie_str: str) -> Dict[str, str]:
    """Parse cookie string to dictionary."""
    return parse_cookie_string(cookie_str)


def _get_default_headers(cookie_str: str = "") -> Dict[str, str]:
    """Get default headers for Weibo requests."""
    from media_adapter.utils import utils
    headers = {
        "User-Agent": utils.get_mobile_user_agent(),
        "Origin": "https://m.weibo.cn",
        "Referer": "https://m.weibo.cn",
        "Content-Type": "application/json;charset=UTF-8",
    }
    if cookie_str:
        headers["Cookie"] = cookie_str
    return headers


# ============== Tool Input Schemas ==============

class SearchWeiboInput(BaseModel):
    """Input schema for search_weibo tool."""
    keywords: str = Field(..., description="Search keywords, multiple keywords separated by comma")
    limit: int = Field(default=20, description="Maximum number of results to return", ge=1, le=100)


class GetWeiboDetailInput(BaseModel):
    """Input schema for get_weibo_detail tool."""
    weibo_id: str = Field(..., description="Weibo ID (mid) or full URL")


class GetWeiboCommentsInput(BaseModel):
    """Input schema for get_weibo_comments tool."""
    weibo_id: str = Field(..., description="Weibo ID or full URL")
    limit: int = Field(default=50, description="Maximum number of comments to return", ge=1, le=200)


class GetUserInfoInput(BaseModel):
    """Input schema for get_user_info tool."""
    user_id: str = Field(..., description="User ID or profile URL")


# ============== Adapter Implementation ==============

class WeiboSignalAdapter(BaseSignalSource):
    """
    Weibo Signal Source Adapter.

    Supports QR code login and provides tools for:
    - Searching weibo posts by keywords
    - Getting weibo details
    - Getting weibo comments
    - Getting user information

    Example:
        adapter = WeiboSignalAdapter(cookies_dir="./cookies", output_dir="./output")
        await adapter.initialize()
        result = await adapter.search_weibo(keywords="Python编程", limit=20)
    """

    def __init__(
        self,
        headless: bool = True,
        cookies_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize Weibo adapter.

        Args:
            headless: Whether to run browser in headless mode (must be False for QR login)
            cookies_dir: Directory containing cookie files (default: from config)
            output_dir: Directory to save output (default: from config)
        """
        super().__init__(
            platform="weibo",
            name="Weibo Adapter",
            description="Signal source adapter for Weibo microblog platform"
        )
        self.headless = headless
        self._browser = None
        self._context = None
        self._page = None
        self._client = None
        self.mobile_index_url = "https://m.weibo.cn"
        self.pc_index_url = "https://weibo.com"
        self.cookies_dir = cookies_dir
        self.output_dir = output_dir
        self._session: Optional[BrowserSession] = None
        self._use_session_manager = True

    async def _get_session(self, force_new: bool = False) -> BrowserSession:
        """Get or create a browser session."""
        if self._use_session_manager:
            self._session = await get_browser_session(
                platform="weibo",
                headless=self.headless,
                cookies_dir=self.cookies_dir,
                force_new=force_new,
            )
            return self._session
        else:
            raise NotImplementedError("Standalone session not implemented for Weibo")

    def _get_cookie(self) -> str:
        """Get cookie string from cookie manager or config."""
        from media_adapter import config

        # First try cookie manager
        if self.cookies_dir:
            cookie_manager = get_cookie_manager(self.cookies_dir)
        else:
            cookie_manager = get_cookie_manager(getattr(config, "COOKIES_DIR", "./cookies"))

        cookie_str = cookie_manager.get_cookie("weibo")

        # Fallback to config.COOKIES
        if not cookie_str:
            cookie_str = getattr(config, "COOKIES", "")

        return cookie_str

    def _get_output_manager(self):
        """Get output manager for saving results."""
        return get_output_manager(
            platform="weibo",
            output_dir=self.output_dir,
        )

    async def initialize(self) -> bool:
        """Initialize the browser and prepare for login if needed."""
        try:
            from media_adapter import config
            config.HEADLESS = self.headless
            self._initialized = True
            return True
        except Exception as e:
            print(f"[WeiboAdapter] Initialization failed: {e}")
            return False

    async def _ensure_login(self, context, page) -> tuple:
        """Ensure user is logged in, trigger QR login if needed."""
        from media_adapter.platforms.weibo.client import WeiboClient
        from media_adapter.platforms.weibo.login import WeiboLogin
        from media_adapter import config
        from media_adapter.utils import utils

        # Get current cookies from browser (mobile site cookies)
        cookie_str, cookie_dict = utils.convert_cookies(
            await context.cookies(urls=[self.mobile_index_url])
        )

        # Create client to check login status
        client = WeiboClient(
            timeout=60,
            headers=_get_default_headers(cookie_str),
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        # Check if already logged in
        if await client.pong():
            print("[WeiboAdapter] Already logged in")
            return cookie_str, cookie_dict, client

        # Not logged in, trigger login
        print("[WeiboAdapter] Not logged in, starting QR code login...")

        # Navigate to PC site for QR code login
        await page.goto(self.pc_index_url)
        await asyncio.sleep(2)

        login_obj = WeiboLogin(
            login_type=config.LOGIN_TYPE,
            login_phone="",
            browser_context=context,
            context_page=page,
            cookie_str=config.COOKIES,
        )
        await login_obj.begin()

        # After login, redirect to mobile site and get mobile cookies
        print("[WeiboAdapter] Login successful, redirecting to mobile site...")
        await page.goto(self.mobile_index_url)
        await asyncio.sleep(3)

        # Update cookies after login (mobile site only)
        await client.update_cookies(
            browser_context=context,
            urls=[self.mobile_index_url]
        )
        cookie_str, cookie_dict = utils.convert_cookies(
            await context.cookies(urls=[self.mobile_index_url])
        )

        # Update client headers with new cookies
        client.headers["Cookie"] = cookie_str
        client.cookie_dict = cookie_dict

        print("[WeiboAdapter] Login successful")
        return cookie_str, cookie_dict, client

    async def check_trigger(
        self,
        keywords: List[str],
        threshold: int = 100,
        **kwargs
    ) -> List[SignalEvent]:
        """Trigger Mode: Check for anomalies (placeholder)."""
        return []

    def get_tools(self) -> List[AdapterTool]:
        """Reference Mode: Get available tools."""
        return [
            AdapterTool(
                name="weibo_search_posts",
                description="Search Weibo posts by keywords. Returns list of posts with content, author, reposts, comments, likes.",
                func=self.search_weibo,
                args_schema=SearchWeiboInput,
            ),
            AdapterTool(
                name="weibo_get_post_detail",
                description="Get detailed information about a specific Weibo post.",
                func=self.get_weibo_detail,
                args_schema=GetWeiboDetailInput,
            ),
            AdapterTool(
                name="weibo_get_post_comments",
                description="Get comments for a specific Weibo post. Useful for sentiment analysis.",
                func=self.get_weibo_comments,
                args_schema=GetWeiboCommentsInput,
            ),
            AdapterTool(
                name="weibo_get_user_info",
                description="Get information about a Weibo user including follower count and post stats.",
                func=self.get_user_info,
                args_schema=GetUserInfoInput,
            ),
        ]

    # Alias for compatibility with test script
    async def search_notes(self, keywords: str, limit: int = 20, save_results: bool = False) -> ToolResult:
        """Alias for search_weibo to maintain compatibility."""
        return await self.search_weibo(keywords=keywords, limit=limit, save_results=save_results)

    async def search_weibo(
        self,
        keywords: str,
        limit: int = 20,
        save_results: bool = False,
    ) -> ToolResult:
        """Search Weibo posts by keywords."""
        try:
            results = []

            # Get or reuse browser session
            session = await self._get_session()

            if not session.is_logged_in:
                cookie_str = self._get_cookie()
                if not cookie_str and self.headless:
                    return ToolResult(
                        success=False,
                        error="No cookies found and headless mode enabled. Please add cookies to cookies/weibo_cookies.txt or run with headless=False for QR login.",
                        metadata={"platform": self.platform}
                    )

            client = session.client

            # Search for each keyword
            keyword_list = [k.strip() for k in keywords.split(",")]
            limit_per_keyword = limit // len(keyword_list) if keyword_list else limit

            for keyword in keyword_list:
                keyword_results = []
                page = 1
                while len(keyword_results) < limit_per_keyword:
                    try:
                        print(f"  Searching '{keyword}' page {page}...")
                        search_res = await client.get_note_by_keyword(
                            keyword=keyword,
                            page=page,
                            search_type=SearchType.DEFAULT,
                        )
                        
                        if not search_res:
                            break

                        # Filter cards to get actual posts
                        cards = search_res.get("cards", [])
                        if not cards:
                            break
                            
                        note_list = filter_search_result_card(cards)
                        if not note_list:
                            # If page 1 has no results, then probably really no results.
                            # But if page > 1 has no results, maybe we reached the end or just a gap.
                            # We stop to be safe.
                            break

                        for note_item in note_list:
                            if len(keyword_results) >= limit_per_keyword:
                                break
                            
                            mblog = note_item.get("mblog", {})
                            if mblog:
                                text_raw = mblog.get("text_raw", mblog.get("text", ""))
                                keyword_results.append({
                                    "note_id": mblog.get("mblogid", mblog.get("id", "")),
                                    "weibo_id": mblog.get("mblogid", mblog.get("id", "")),
                                    "mid": mblog.get("mid", ""),
                                    "title": text_raw[:50] + "..." if len(text_raw) > 50 else text_raw,
                                    "desc": text_raw,
                                    "content": text_raw,
                                    "author": mblog.get("user", {}).get("screen_name", ""),
                                    "author_id": mblog.get("user", {}).get("id", ""),
                                    "liked_count": mblog.get("attitudes_count", 0),
                                    "reposts_count": mblog.get("reposts_count", 0),
                                    "comments_count": mblog.get("comments_count", 0),
                                    "attitudes_count": mblog.get("attitudes_count", 0),
                                    "created_at": mblog.get("created_at", ""),
                                    "keyword": keyword,
                                })
                        
                        page += 1
                        await asyncio.sleep(2)  # Respectful delay

                    except Exception as e:
                        print(f"[WeiboAdapter] Error searching keyword '{keyword}': {e}")
                        import traceback
                        traceback.print_exc()
                        break
                
                results.extend(keyword_results)

            final_results = results[:limit]

            # Save results if requested
            saved_path = None
            if save_results and final_results:
                output_manager = self._get_output_manager()
                saved_path = output_manager.save_json(
                    final_results,
                    f"search_{'_'.join(keyword_list[:2])}",
                    suffix="posts"
                )

            return ToolResult(
                success=True,
                data=final_results,
                metadata={
                    "total": len(final_results),
                    "keywords": keyword_list,
                    "platform": self.platform,
                    "saved_path": saved_path,
                }
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    async def get_weibo_detail(self, weibo_id: str) -> ToolResult:
        """Get detailed information about a weibo post."""
        try:
            import re

            # Ensure weibo_id is a string
            weibo_id = str(weibo_id)

            # Extract weibo_id if URL is provided
            if "weibo.com" in weibo_id or "weibo.cn" in weibo_id:
                match = re.search(r'/(\d+)/([a-zA-Z0-9]+)', weibo_id)
                if match:
                    weibo_id = match.group(2)

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            weibo_detail = await client.get_note_info_by_id(weibo_id)

            if weibo_detail:
                return ToolResult(
                    success=True,
                    data={
                        "weibo_id": weibo_detail.get("mblogid", weibo_id),
                        "mid": weibo_detail.get("mid", ""),
                        "content": weibo_detail.get("text_raw", ""),
                        "author": weibo_detail.get("user", {}).get("screen_name", ""),
                        "author_id": weibo_detail.get("user", {}).get("id", ""),
                        "reposts_count": weibo_detail.get("reposts_count", 0),
                        "comments_count": weibo_detail.get("comments_count", 0),
                        "attitudes_count": weibo_detail.get("attitudes_count", 0),
                        "created_at": weibo_detail.get("created_at", ""),
                        "source": weibo_detail.get("source", ""),
                        "region_name": weibo_detail.get("region_name", ""),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(
                success=False,
                error=f"Weibo not found: {weibo_id}",
                metadata={"platform": self.platform}
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    async def get_weibo_comments(self, weibo_id: str, limit: int = 50) -> ToolResult:
        """Get comments for a weibo post."""
        try:
            import re

            # Ensure weibo_id is a string
            weibo_id = str(weibo_id)

            if "weibo.com" in weibo_id or "weibo.cn" in weibo_id:
                match = re.search(r'/(\d+)/([a-zA-Z0-9]+)', weibo_id)
                if match:
                    weibo_id = match.group(2)

            comments = []

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            result = await client.get_note_all_comments(
                note_id=weibo_id,
                crawl_interval=0.5,
            )
            for comment in result[:limit]:
                comments.append({
                    "comment_id": comment.get("id", ""),
                    "content": comment.get("text_raw", ""),
                    "author": comment.get("user", {}).get("screen_name", ""),
                    "author_id": comment.get("user", {}).get("id", ""),
                    "like_count": comment.get("like_count", 0),
                    "created_at": comment.get("created_at", ""),
                })

            return ToolResult(
                success=True,
                data=comments[:limit],
                metadata={
                    "total": len(comments),
                    "weibo_id": weibo_id,
                    "platform": self.platform,
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    # Alias for compatibility with test script
    async def get_creator_info(self, creator_id: str) -> ToolResult:
        """Alias for get_user_info to maintain compatibility."""
        return await self.get_user_info(user_id=creator_id)

    async def get_user_info(self, user_id: str) -> ToolResult:
        """Get user information."""
        try:
            import re

            # Ensure user_id is a string
            user_id = str(user_id)

            if "weibo.com" in user_id or "weibo.cn" in user_id:
                match = re.search(r'/u/(\d+)', user_id) or re.search(r'/(\d+)', user_id)
                if match:
                    user_id = match.group(1)

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            # Use the correct client method
            user_res = await client.get_creator_info_by_id(user_id)
            user_info = user_res.get("userInfo", {}) if user_res else {}

            if user_info:
                return ToolResult(
                    success=True,
                    data={
                        "user_id": user_info.get("id", user_id),
                        "nickname": user_info.get("screen_name", ""),
                        "screen_name": user_info.get("screen_name", ""),
                        "description": user_info.get("description", ""),
                        "followers_count": user_info.get("followers_count", 0),
                        "follow_count": user_info.get("follow_count", 0),
                        "friends_count": user_info.get("friends_count", 0),
                        "statuses_count": user_info.get("statuses_count", 0),
                        "verified": user_info.get("verified", False),
                        "verified_reason": user_info.get("verified_reason", ""),
                        "location": user_info.get("location", ""),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(
                success=False,
                error=f"User not found: {user_id}",
                metadata={"platform": self.platform}
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        self._initialized = False
