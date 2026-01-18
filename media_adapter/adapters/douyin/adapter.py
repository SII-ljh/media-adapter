# -*- coding: utf-8 -*-
"""
Douyin (TikTok China) Signal Source Adapter

Implements BaseSignalSource interface for Douyin platform.
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
from media_adapter.platforms.douyin.field import (
    SearchChannelType,
    SearchSortType,
    PublishTimeType,
)
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


def _get_default_headers(cookie_str: str = "", user_agent: str = "") -> Dict[str, str]:
    """Get default headers for Douyin requests."""
    if not user_agent:
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    headers = {
        "User-Agent": user_agent,
        "Host": "www.douyin.com",
        "Origin": "https://www.douyin.com/",
        "Referer": "https://www.douyin.com/",
        "Content-Type": "application/json;charset=UTF-8",
    }
    if cookie_str:
        headers["Cookie"] = cookie_str
    return headers


# ============== Tool Input Schemas ==============

class SearchVideosInput(BaseModel):
    """Input schema for search_videos tool."""
    keywords: str = Field(..., description="Search keywords, multiple keywords separated by comma")
    limit: int = Field(default=20, description="Maximum number of results to return", ge=1, le=100)
    sort_by: str = Field(default="general", description="Sort method: general, hot, time")


class GetVideoDetailInput(BaseModel):
    """Input schema for get_video_detail tool."""
    video_id: str = Field(..., description="Video ID or full URL (aweme_id)")


class GetVideoCommentsInput(BaseModel):
    """Input schema for get_video_comments tool."""
    video_id: str = Field(..., description="Video ID or full URL")
    limit: int = Field(default=50, description="Maximum number of comments to return", ge=1, le=200)


class GetCreatorInfoInput(BaseModel):
    """Input schema for get_creator_info tool."""
    creator_id: str = Field(..., description="Creator user ID (sec_uid) or profile URL")


# ============== Adapter Implementation ==============

class DouyinSignalAdapter(BaseSignalSource):
    """
    Douyin Signal Source Adapter.

    Supports QR code login and provides tools for:
    - Searching videos by keywords
    - Getting video details
    - Getting video comments
    - Getting creator information

    Example:
        adapter = DouyinSignalAdapter(cookies_dir="./cookies", output_dir="./output")
        await adapter.initialize()
        result = await adapter.search_videos(keywords="Python教程", limit=20)
    """

    def __init__(
        self,
        headless: bool = True,
        cookies_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize Douyin adapter.

        Args:
            headless: Whether to run browser in headless mode (must be False for QR login)
            cookies_dir: Directory containing cookie files (default: from config)
            output_dir: Directory to save output (default: from config)
        """
        super().__init__(
            platform="douyin",
            name="Douyin Adapter",
            description="Signal source adapter for Douyin (TikTok China) platform"
        )
        self.headless = headless
        self._browser = None
        self._context = None
        self._page = None
        self._client = None
        self._session: Optional[BrowserSession] = None
        self.cookies_dir = cookies_dir
        self.output_dir = output_dir
        self._use_session_manager = True

    def _get_cookie(self) -> str:
        """Get cookie string from cookie manager or config."""
        from media_adapter import config

        if self.cookies_dir:
            cookie_manager = get_cookie_manager(self.cookies_dir)
        else:
            cookie_manager = get_cookie_manager(getattr(config, "COOKIES_DIR", "./cookies"))

        cookie_str = cookie_manager.get_cookie("douyin")

        if not cookie_str:
            cookie_str = getattr(config, "COOKIES", "")

        return cookie_str

    def _get_output_manager(self):
        """Get output manager for saving results."""
        return get_output_manager(
            platform="douyin",
            output_dir=self.output_dir,
        )

    async def _get_session(self, force_new: bool = False) -> BrowserSession:
        """Get or create a browser session."""
        if self._use_session_manager:
            self._session = await get_browser_session(
                platform="douyin",
                headless=self.headless,
                cookies_dir=self.cookies_dir,
                force_new=force_new,
            )
            return self._session
        else:
            return await self._create_standalone_session()

    async def _create_standalone_session(self) -> BrowserSession:
        """Create a standalone session."""
        from playwright.async_api import async_playwright
        from media_adapter.resources import get_stealth_js_path
        from media_adapter.platforms.douyin.client import DouYinClient
        from media_adapter.platforms.douyin.login import DouYinLogin
        from media_adapter import config
        from media_adapter.utils import utils

        cookie_str = self._get_cookie()
        cookie_dict = _parse_cookie_string(cookie_str)

        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=self.headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
        )

        await context.add_init_script(path=get_stealth_js_path())

        if cookie_str:
            cookies = format_cookies_for_playwright(cookie_str, ".douyin.com")
            await context.add_cookies(cookies)

        page = await context.new_page()
        try:
            await page.goto("https://www.douyin.com", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            await page.goto("https://www.douyin.com", wait_until="load", timeout=60000)
        await asyncio.sleep(3)

        user_agent = await page.evaluate("() => navigator.userAgent")
        client = DouYinClient(
            timeout=60,
            headers=_get_default_headers(cookie_str, user_agent),
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        is_logged_in = await client.pong(browser_context=context)

        if not is_logged_in and not self.headless:
            print("[Douyin] Starting QR code login...")
            login_obj = DouYinLogin(
                login_type=config.LOGIN_TYPE,
                login_phone="",
                browser_context=context,
                context_page=page,
                cookie_str=cookie_str,
            )
            await login_obj.begin()
            await client.update_cookies(browser_context=context)
            new_cookie_str, new_cookie_dict = utils.convert_cookies(await context.cookies())
            client.headers["Cookie"] = new_cookie_str
            client.cookie_dict = new_cookie_dict
            cookie_str = new_cookie_str
            cookie_dict = new_cookie_dict
            is_logged_in = True

        from datetime import datetime
        return BrowserSession(
            platform="douyin",
            browser=browser,
            context=context,
            page=page,
            client=client,
            cookie_str=cookie_str,
            cookie_dict=cookie_dict,
            created_at=datetime.now(),
            is_logged_in=is_logged_in,
        )

    async def initialize(self) -> bool:
        """Initialize the browser and prepare for login if needed."""
        try:
            from media_adapter import config
            config.HEADLESS = self.headless
            self._initialized = True
            return True
        except Exception as e:
            print(f"[DouyinAdapter] Initialization failed: {e}")
            return False

    async def _ensure_login(self, context, page) -> tuple:
        """Ensure user is logged in, trigger QR login if needed."""
        from media_adapter.platforms.douyin.client import DouYinClient
        from media_adapter.platforms.douyin.login import DouYinLogin
        from media_adapter import config
        from media_adapter.utils import utils

        # Get current cookies from browser
        cookie_str, cookie_dict = utils.convert_cookies(await context.cookies())

        # Create client to check login status
        user_agent = await page.evaluate("() => navigator.userAgent")
        client = DouYinClient(
            timeout=60,
            headers=_get_default_headers(cookie_str, user_agent),
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        # Check if already logged in
        if await client.pong(browser_context=context):
            print("[DouyinAdapter] Already logged in")
            return cookie_str, cookie_dict, client

        # Not logged in, trigger login
        print("[DouyinAdapter] Not logged in, starting QR code login...")
        login_obj = DouYinLogin(
            login_type=config.LOGIN_TYPE,
            login_phone="",
            browser_context=context,
            context_page=page,
            cookie_str=config.COOKIES,
        )
        await login_obj.begin()

        # Update cookies after login
        await client.update_cookies(browser_context=context)
        cookie_str, cookie_dict = utils.convert_cookies(await context.cookies())

        # Update client headers with new cookies
        client.headers["Cookie"] = cookie_str
        client.cookie_dict = cookie_dict

        print("[DouyinAdapter] Login successful")
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
                name="douyin_search_videos",
                description="Search Douyin videos by keywords. Returns structured list of videos with title, author, likes, plays, etc.",
                func=self.search_videos,
                args_schema=SearchVideosInput,
            ),
            AdapterTool(
                name="douyin_get_video_detail",
                description="Get detailed information about a specific Douyin video including full description, stats, and music info.",
                func=self.get_video_detail,
                args_schema=GetVideoDetailInput,
            ),
            AdapterTool(
                name="douyin_get_video_comments",
                description="Get comments for a specific Douyin video. Useful for sentiment analysis.",
                func=self.get_video_comments,
                args_schema=GetVideoCommentsInput,
            ),
            AdapterTool(
                name="douyin_get_creator_info",
                description="Get information about a Douyin creator/influencer including follower count and video stats.",
                func=self.get_creator_info,
                args_schema=GetCreatorInfoInput,
            ),
        ]

    # Alias for compatibility with test script
    async def search_notes(self, keywords: str, limit: int = 20, sort_by: str = "general", save_results: bool = False) -> ToolResult:
        """Alias for search_videos to maintain compatibility."""
        return await self.search_videos(keywords=keywords, limit=limit, sort_by=sort_by, save_results=save_results)

    async def search_videos(
        self,
        keywords: str,
        limit: int = 20,
        sort_by: str = "general",
        save_results: bool = False,
    ) -> ToolResult:
        """
        Search Douyin videos by keywords.

        Args:
            keywords: Search keywords (comma separated for multiple)
            limit: Maximum number of results
            sort_by: Sort method
            save_results: Whether to save results to file

        Returns:
            ToolResult with list of videos
        """
        try:
            # Get or reuse browser session
            session = await self._get_session()

            if not session.is_logged_in:
                cookie_str = self._get_cookie()
                if not cookie_str and self.headless:
                    return ToolResult(
                        success=False,
                        error="No cookies found and headless mode enabled. Please add cookies to cookies/douyin_cookies.txt or run with headless=False for QR login.",
                        metadata={"platform": self.platform}
                    )

            client = session.client
            results = []

            # Search for each keyword
            # Search for each keyword
            keyword_list = [k.strip() for k in keywords.split(",")]
            limit_per_keyword = limit // len(keyword_list) if keyword_list else limit

            for keyword in keyword_list:
                keyword_results = []
                offset = 0
                while len(keyword_results) < limit_per_keyword:
                    try:
                        print(f"  Searching '{keyword}' offset {offset}...")
                        response = await client.search_info_by_keyword(
                            keyword=keyword,
                            offset=offset,
                            search_channel=SearchChannelType.GENERAL,
                            sort_type=SearchSortType.GENERAL,
                            publish_time=PublishTimeType.UNLIMITED,
                        )
                        
                        if not response:
                            break

                        videos = response.get("data", [])
                        if not videos:
                            break

                        for video in videos:
                            if len(keyword_results) >= limit_per_keyword:
                                break
                            
                            aweme = video.get("aweme_info", {})
                            if aweme:
                                keyword_results.append({
                                    "note_id": aweme.get("aweme_id", ""),
                                    "video_id": aweme.get("aweme_id", ""),
                                    "title": aweme.get("desc", ""),
                                    "author": aweme.get("author", {}).get("nickname", ""),
                                    "author_id": aweme.get("author", {}).get("sec_uid", ""),
                                    "liked_count": aweme.get("statistics", {}).get("digg_count", 0),
                                    "digg_count": aweme.get("statistics", {}).get("digg_count", 0),
                                    "comment_count": aweme.get("statistics", {}).get("comment_count", 0),
                                    "share_count": aweme.get("statistics", {}).get("share_count", 0),
                                    "play_count": aweme.get("statistics", {}).get("play_count", 0),
                                    "collect_count": aweme.get("statistics", {}).get("collect_count", 0),
                                    "create_time": aweme.get("create_time", 0),
                                    "keyword": keyword,
                                })
                        
                        if not response.get("has_more", 0):
                            break
                            
                        offset = response.get("cursor", offset + 10)
                        await asyncio.sleep(2)  # Respectful delay

                    except Exception as e:
                        print(f"[DouyinAdapter] Error searching keyword '{keyword}': {e}")
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
                    suffix="videos"
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

    async def get_video_detail(self, video_id: str) -> ToolResult:
        """Get detailed information about a specific video."""
        try:
            from media_adapter.platforms.douyin.help import parse_video_info_from_url

            # Ensure video_id is a string
            video_id = str(video_id)

            # Extract video_id if URL is provided
            if "douyin.com" in video_id:
                video_info = parse_video_info_from_url(video_id)
                video_id = video_info.aweme_id

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            video_detail = await client.get_video_by_id(video_id)

            if video_detail:
                return ToolResult(
                    success=True,
                    data={
                        "video_id": video_detail.get("aweme_id", video_id),
                        "title": video_detail.get("desc", ""),
                        "author": video_detail.get("author", {}).get("nickname", ""),
                        "author_id": video_detail.get("author", {}).get("sec_uid", ""),
                        "digg_count": video_detail.get("statistics", {}).get("digg_count", 0),
                        "comment_count": video_detail.get("statistics", {}).get("comment_count", 0),
                        "share_count": video_detail.get("statistics", {}).get("share_count", 0),
                        "play_count": video_detail.get("statistics", {}).get("play_count", 0),
                        "collect_count": video_detail.get("statistics", {}).get("collect_count", 0),
                        "create_time": video_detail.get("create_time", 0),
                        "duration": video_detail.get("duration", 0),
                        "music": video_detail.get("music", {}),
                    },
                    metadata={"platform": self.platform}
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Video not found: {video_id}",
                    metadata={"platform": self.platform}
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    async def get_video_comments(self, video_id: str, limit: int = 50) -> ToolResult:
        """Get comments for a specific video."""
        try:
            from media_adapter.platforms.douyin.help import parse_video_info_from_url

            # Ensure video_id is a string
            video_id = str(video_id)

            if "douyin.com" in video_id:
                video_info = parse_video_info_from_url(video_id)
                video_id = video_info.aweme_id

            comments = []

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            cursor = 0
            while len(comments) < limit:
                result = await client.get_aweme_all_comments(
                    aweme_id=video_id,
                    cursor=cursor,
                    count=20,
                )
                if not result or "comments" not in result:
                    break

                for comment in result.get("comments", []):
                    comments.append({
                        "comment_id": comment.get("cid", ""),
                        "content": comment.get("text", ""),
                        "author": comment.get("user", {}).get("nickname", ""),
                        "author_id": comment.get("user", {}).get("sec_uid", ""),
                        "digg_count": comment.get("digg_count", 0),
                        "create_time": comment.get("create_time", 0),
                        "reply_comment_total": comment.get("reply_comment_total", 0),
                    })

                cursor = result.get("cursor", 0)
                if not result.get("has_more", False):
                    break

            return ToolResult(
                success=True,
                data=comments[:limit],
                metadata={
                    "total": len(comments),
                    "video_id": video_id,
                    "platform": self.platform,
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    async def get_creator_info(self, creator_id: str) -> ToolResult:
        """Get information about a creator."""
        try:
            from media_adapter.platforms.douyin.help import parse_creator_info_from_url

            # Ensure creator_id is a string
            creator_id = str(creator_id)

            # Extract sec_uid if URL is provided
            if "douyin.com" in creator_id:
                creator_info = parse_creator_info_from_url(creator_id)
                creator_id = creator_info.sec_user_id

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            user_info = await client.get_user_info(creator_id)

            if user_info:
                return ToolResult(
                    success=True,
                    data={
                        "sec_uid": user_info.get("sec_uid", creator_id),
                        "nickname": user_info.get("nickname", ""),
                        "signature": user_info.get("signature", ""),
                        "unique_id": user_info.get("unique_id", ""),
                        "follower_count": user_info.get("follower_count", 0),
                        "following_count": user_info.get("following_count", 0),
                        "total_favorited": user_info.get("total_favorited", 0),
                        "aweme_count": user_info.get("aweme_count", 0),
                        "favoriting_count": user_info.get("favoriting_count", 0),
                        "ip_location": user_info.get("ip_location", ""),
                    },
                    metadata={"platform": self.platform}
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Creator not found: {creator_id}",
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
