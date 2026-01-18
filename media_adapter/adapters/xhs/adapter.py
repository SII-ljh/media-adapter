# -*- coding: utf-8 -*-
"""
Xiaohongshu (Little Red Book) Signal Source Adapter

Implements BaseSignalSource interface for Xiaohongshu platform.
Provides both Trigger mode and Reference Tools mode.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from media_adapter.adapters.base import (
    BaseSignalSource,
    SignalEvent,
    SignalEventType,
    SignalSeverity,
    AdapterTool,
    ToolResult,
)
from media_adapter.platforms.xhs.field import SearchSortType
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
    """Get default headers for XHS requests."""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://www.xiaohongshu.com",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.xiaohongshu.com/",
        "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }
    if cookie_str:
        headers["Cookie"] = cookie_str
    return headers


# ============== Tool Input Schemas ==============

class SearchNotesInput(BaseModel):
    """Input schema for search_notes tool."""
    keywords: str = Field(..., description="Search keywords, multiple keywords separated by comma")
    limit: int = Field(default=20, description="Maximum number of results to return", ge=1, le=100)
    sort_by: str = Field(default="general", description="Sort method: general, hot, time")


class GetNoteDetailInput(BaseModel):
    """Input schema for get_note_detail tool."""
    note_id: str = Field(..., description="Note ID or full URL")


class GetNoteCommentsInput(BaseModel):
    """Input schema for get_note_comments tool."""
    note_id: str = Field(..., description="Note ID or full URL")
    limit: int = Field(default=50, description="Maximum number of comments to return", ge=1, le=200)


class GetCreatorInfoInput(BaseModel):
    """Input schema for get_creator_info tool."""
    creator_id: str = Field(..., description="Creator user ID or profile URL")


# ============== Adapter Implementation ==============

class XhsSignalAdapter(BaseSignalSource):
    """
    Xiaohongshu Signal Source Adapter.

    Provides tools for:
    - Searching notes by keywords
    - Getting note details
    - Getting note comments
    - Getting creator information

    Example:
        adapter = XhsSignalAdapter(cookies_dir="./cookies", output_dir="./output")
        await adapter.initialize()

        # Trigger mode
        events = await adapter.check_trigger(keywords=["Python", "编程"])

        # Reference mode
        tools = adapter.get_tools()
        result = await tools[0].func(keywords="Python教程", limit=10)
    """

    def __init__(
        self,
        headless: bool = True,
        cookies_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize Xiaohongshu adapter.

        Args:
            headless: Whether to run browser in headless mode
            cookies_dir: Directory containing cookie files (default: from config)
            output_dir: Directory to save output (default: from config)
        """
        super().__init__(
            platform="xhs",
            name="Xiaohongshu Adapter",
            description="Signal source adapter for Xiaohongshu (Little Red Book) platform"
        )
        self.headless = headless
        self._crawler = None
        self._client = None
        self._session: Optional[BrowserSession] = None
        self.cookies_dir = cookies_dir
        self.output_dir = output_dir
        self._use_session_manager = True  # Use shared session manager

    async def _get_session(self, force_new: bool = False) -> BrowserSession:
        """Get or create a browser session."""
        if self._use_session_manager:
            self._session = await get_browser_session(
                platform="xhs",
                headless=self.headless,
                cookies_dir=self.cookies_dir,
                force_new=force_new,
            )
            return self._session
        else:
            # Fallback to creating new session each time
            return await self._create_standalone_session()

    async def _create_standalone_session(self) -> BrowserSession:
        """Create a standalone session (not managed by session manager)."""
        from playwright.async_api import async_playwright
        from media_adapter.resources import get_stealth_js_path
        from media_adapter.platforms.xhs.client import XiaoHongShuClient
        from media_adapter.platforms.xhs.login import XiaoHongShuLogin
        from media_adapter import config

        cookie_str = self._get_cookie()
        cookie_dict = _parse_cookie_string(cookie_str)

        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=self.headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
        )

        await context.add_init_script(path=get_stealth_js_path())

        if cookie_str:
            cookies = format_cookies_for_playwright(cookie_str, ".xiaohongshu.com")
            await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        client = XiaoHongShuClient(
            timeout=60,
            headers=_get_default_headers(cookie_str),
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        is_logged_in = await client.pong()

        if not is_logged_in and not self.headless:
            print("[XHS] Starting QR code login...")
            login_obj = XiaoHongShuLogin(
                login_type=config.LOGIN_TYPE,
                login_phone="",
                browser_context=context,
                context_page=page,
                cookie_str=cookie_str,
            )
            await login_obj.begin()
            await client.update_cookies(browser_context=context)
            is_logged_in = True

        from media_adapter.utils.browser_session import BrowserSession
        from datetime import datetime

        return BrowserSession(
            platform="xhs",
            browser=browser,
            context=context,
            page=page,
            client=client,
            cookie_str=cookie_str,
            cookie_dict=cookie_dict,
            created_at=datetime.now(),
            is_logged_in=is_logged_in,
        )

    def _get_cookie(self) -> str:
        """Get cookie string from cookie manager or config."""
        from media_adapter import config

        # First try cookie manager
        if self.cookies_dir:
            cookie_manager = get_cookie_manager(self.cookies_dir)
        else:
            cookie_manager = get_cookie_manager(getattr(config, "COOKIES_DIR", "./cookies"))

        cookie_str = cookie_manager.get_cookie("xhs")

        # Fallback to config.COOKIES
        if not cookie_str:
            cookie_str = getattr(config, "COOKIES", "")

        return cookie_str

    def _get_output_manager(self):
        """Get output manager for saving results."""
        return get_output_manager(
            platform="xhs",
            output_dir=self.output_dir,
        )

    async def initialize(self) -> bool:
        """Initialize the crawler and login."""
        try:
            from media_adapter.platforms.xhs import XiaoHongShuCrawler
            from media_adapter import config

            # Configure settings
            config.HEADLESS = self.headless

            self._crawler = XiaoHongShuCrawler()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[XhsAdapter] Initialization failed: {e}")
            return False

    async def check_trigger(
        self,
        keywords: List[str],
        threshold: int = 100,
        **kwargs
    ) -> List[SignalEvent]:
        """
        Trigger Mode: Check for anomalies based on keywords.

        This is a placeholder implementation. In production, this would:
        - Monitor keyword mention frequency
        - Detect sudden spikes in engagement
        - Track sentiment changes
        - Identify viral content

        Args:
            keywords: Keywords to monitor
            threshold: Engagement threshold for triggering events
            **kwargs: Additional parameters

        Returns:
            List of SignalEvent objects
        """
        # TODO: Implement actual trigger logic
        # Currently returns empty list (no events triggered)
        events = []

        # Placeholder: In production, implement actual monitoring logic here
        # Example structure for when anomaly is detected:
        #
        # if anomaly_detected:
        #     event = SignalEvent(
        #         event_id=str(uuid.uuid4()),
        #         event_type=SignalEventType.KEYWORD_SPIKE,
        #         severity=SignalSeverity.HIGH,
        #         platform=self.platform,
        #         title=f"Keyword spike detected: {keyword}",
        #         description=f"Unusual activity detected for keyword '{keyword}'",
        #         keywords=keywords,
        #         data={"keyword": keyword, "count": mention_count},
        #     )
        #     events.append(event)

        return events

    def get_tools(self) -> List[AdapterTool]:
        """
        Reference Mode: Get available tools for Agent invocation.

        Returns:
            List of AdapterTool objects
        """
        return [
            AdapterTool(
                name="xhs_search_notes",
                description="Search Xiaohongshu notes by keywords. Returns structured list of notes with title, author, likes, etc.",
                func=self.search_notes,
                args_schema=SearchNotesInput,
            ),
            AdapterTool(
                name="xhs_get_note_detail",
                description="Get detailed information about a specific Xiaohongshu note including full content, images, and stats.",
                func=self.get_note_detail,
                args_schema=GetNoteDetailInput,
            ),
            AdapterTool(
                name="xhs_get_note_comments",
                description="Get comments for a specific Xiaohongshu note. Useful for sentiment analysis.",
                func=self.get_note_comments,
                args_schema=GetNoteCommentsInput,
            ),
            AdapterTool(
                name="xhs_get_creator_info",
                description="Get information about a Xiaohongshu creator/influencer including follower count and recent posts.",
                func=self.get_creator_info,
                args_schema=GetCreatorInfoInput,
            ),
        ]

    async def search_notes(
        self,
        keywords: str,
        limit: int = 20,
        sort_by: str = "general",
        save_results: bool = False,
    ) -> ToolResult:
        """
        Search Xiaohongshu notes by keywords.

        Args:
            keywords: Search keywords (comma separated for multiple)
            limit: Maximum number of results
            sort_by: Sort method (general, hot, time)
            save_results: Whether to save results to file

        Returns:
            ToolResult with list of notes
        """
        try:
            # Get or reuse browser session
            session = await self._get_session()

            if not session.is_logged_in:
                # Check if we have cookies to try
                cookie_str = self._get_cookie()
                if not cookie_str and self.headless:
                    return ToolResult(
                        success=False,
                        error="No cookies found and headless mode enabled. Please add cookies to cookies/xhs_cookies.txt or run with headless=False for QR login.",
                        metadata={"platform": self.platform}
                    )

            client = session.client
            results = []

            # Map sort_by string to SearchSortType enum
            sort_type_map = {
                "general": SearchSortType.GENERAL,
                "hot": SearchSortType.MOST_POPULAR,
                "time": SearchSortType.LATEST,
            }
            sort_type = sort_type_map.get(sort_by, SearchSortType.GENERAL)

            # Search for each keyword
            keyword_list = [k.strip() for k in keywords.split(",")]
            limit_per_keyword = limit // len(keyword_list) if keyword_list else limit

            for keyword in keyword_list:
                keyword_results = []
                page = 1
                while len(keyword_results) < limit_per_keyword:
                    try:
                        print(f"  Searching '{keyword}' page {page}...")
                        response = await client.get_note_by_keyword(
                            keyword=keyword,
                            page=page,
                            sort=sort_type,
                        )
                        
                        if not response:
                            break

                        # Get notes from items field
                        notes = response.get("items", [])
                        if not notes:
                            break
                            
                        # Filter out rec_query and hot_query items
                        notes = [n for n in notes if n.get("model_type") not in ("rec_query", "hot_query")]
                        
                        if not notes:
                            # If we filtered everything out but there were items, we should probably try next page
                            # But if raw items were empty, we stopped above.
                            pass

                        for note in notes:
                            if len(keyword_results) >= limit_per_keyword:
                                break
                                
                            # note_card contains the main note information
                            note_card = note.get("note_card", note)  # fallback to note itself
                            user_info = note_card.get("user", {})
                            interact_info = note_card.get("interact_info", {})

                            keyword_results.append({
                                "note_id": note.get("id", ""),
                                "title": note_card.get("display_title", note_card.get("title", "")),
                                "desc": note_card.get("desc", ""),
                                "author": user_info.get("nickname", user_info.get("nick_name", "")),
                                "author_id": user_info.get("user_id", ""),
                                "liked_count": interact_info.get("liked_count", note_card.get("liked_count", 0)),
                                "collected_count": interact_info.get("collected_count", note_card.get("collected_count", 0)),
                                "comment_count": interact_info.get("comment_count", note_card.get("comments_count", 0)),
                                "type": note_card.get("type", ""),
                                "keyword": keyword,
                                "xsec_token": note.get("xsec_token", ""),
                            })
                        
                        # Check if there are more pages
                        if not response.get("has_more", False):
                            break
                            
                        page += 1
                        await asyncio.sleep(2)  # Respectful delay

                    except Exception as e:
                        print(f"[XhsAdapter] Error searching keyword '{keyword}': {e}")
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
                    suffix="notes"
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
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    async def get_note_detail(self, note_id: str, xsec_token: str = "", save_result: bool = False) -> ToolResult:
        """
        Get detailed information about a specific note.

        Args:
            note_id: Note ID or full URL
            xsec_token: Security token (optional, obtained from search results)
            save_result: Whether to save result to file

        Returns:
            ToolResult with note details
        """
        try:
            from media_adapter.platforms.xhs.help import parse_note_info_from_note_url

            # Ensure note_id is a string
            note_id = str(note_id)

            # Extract note_id and xsec_token if URL is provided
            xsec_token_from_url = xsec_token
            if "xiaohongshu.com" in note_id or "xhslink.com" in note_id:
                note_url_info = parse_note_info_from_note_url(note_id)
                note_id = note_url_info.note_id
                if not xsec_token_from_url and note_url_info.xsec_token:
                    xsec_token_from_url = note_url_info.xsec_token

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            note_detail = await client.get_note_by_id(
                note_id=note_id,
                xsec_source="pc_search",
                xsec_token=xsec_token_from_url,
            )

            if note_detail:
                return ToolResult(
                    success=True,
                    data={
                        "note_id": note_detail.get("note_id", note_id),
                        "title": note_detail.get("title", ""),
                        "desc": note_detail.get("desc", ""),
                        "content": note_detail.get("desc", ""),
                        "author": note_detail.get("user", {}).get("nickname", ""),
                        "author_id": note_detail.get("user", {}).get("user_id", ""),
                        "liked_count": note_detail.get("interact_info", {}).get("liked_count", 0),
                        "collected_count": note_detail.get("interact_info", {}).get("collected_count", 0),
                        "comment_count": note_detail.get("interact_info", {}).get("comment_count", 0),
                        "share_count": note_detail.get("interact_info", {}).get("share_count", 0),
                        "create_time": note_detail.get("time", ""),
                        "last_update_time": note_detail.get("last_update_time", ""),
                        "image_list": note_detail.get("image_list", []),
                        "tag_list": note_detail.get("tag_list", []),
                    },
                    metadata={"platform": self.platform}
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Note not found: {note_id}",
                    metadata={"platform": self.platform}
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"platform": self.platform}
            )

    async def get_note_comments(
        self,
        note_id: str,
        limit: int = 50,
        xsec_token: str = ""
    ) -> ToolResult:
        """
        Get comments for a specific note.

        Args:
            note_id: Note ID or full URL
            limit: Maximum number of comments
            xsec_token: Security token (optional, obtained from search results)

        Returns:
            ToolResult with list of comments
        """
        try:
            from media_adapter.platforms.xhs.help import parse_note_info_from_note_url

            # Ensure note_id is a string
            note_id = str(note_id)

            # Extract note_id and xsec_token if URL is provided
            xsec_token_from_url = xsec_token
            if "xiaohongshu.com" in note_id or "xhslink.com" in note_id:
                note_url_info = parse_note_info_from_note_url(note_id)
                note_id = note_url_info.note_id
                if not xsec_token_from_url and note_url_info.xsec_token:
                    xsec_token_from_url = note_url_info.xsec_token

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client
            comments = []

            cursor = ""
            while len(comments) < limit:
                result = await client.get_note_comments(
                    note_id=note_id,
                    xsec_token=xsec_token_from_url,
                    cursor=cursor,
                )
                if not result or "comments" not in result:
                    break

                for comment in result.get("comments", []):
                    comments.append({
                        "comment_id": comment.get("id", ""),
                        "content": comment.get("content", ""),
                        "author": comment.get("user_info", {}).get("nickname", ""),
                        "author_id": comment.get("user_info", {}).get("user_id", ""),
                        "liked_count": comment.get("like_count", 0),
                        "create_time": comment.get("create_time", ""),
                        "sub_comment_count": comment.get("sub_comment_count", 0),
                    })

                cursor = result.get("cursor", "")
                if not result.get("has_more", False):
                    break

            return ToolResult(
                success=True,
                data=comments[:limit],
                metadata={
                    "total": len(comments),
                    "note_id": note_id,
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
        """
        Get information about a creator.

        Args:
            creator_id: Creator user ID or profile URL

        Returns:
            ToolResult with creator information
        """
        try:
            import re

            # Ensure creator_id is a string
            creator_id = str(creator_id)

            # Extract creator_id if URL is provided
            if "xiaohongshu.com" in creator_id:
                match = re.search(r'/user/profile/([a-zA-Z0-9]+)', creator_id)
                if match:
                    creator_id = match.group(1)

            # Get or reuse browser session
            session = await self._get_session()
            client = session.client

            user_info = await client.get_creator_info(creator_id)

            if user_info:
                return ToolResult(
                    success=True,
                    data={
                        "user_id": user_info.get("user_id", creator_id),
                        "nickname": user_info.get("nickname", ""),
                        "desc": user_info.get("desc", ""),
                        "gender": user_info.get("gender", ""),
                        "ip_location": user_info.get("ip_location", ""),
                        "follows": user_info.get("follows", 0),
                        "fans": user_info.get("fans", 0),
                        "interaction": user_info.get("interaction", 0),
                        "level": user_info.get("level", {}),
                        "tags": user_info.get("tags", []),
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
        if self._crawler:
            try:
                if hasattr(self._crawler, 'browser_context') and self._crawler.browser_context:
                    await self._crawler.browser_context.close()
            except Exception:
                pass
        self._initialized = False
