# -*- coding: utf-8 -*-
"""
Baidu Tieba Signal Source Adapter

Implements BaseSignalSource interface for Baidu Tieba platform.
"""

import asyncio
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


# ============== Tool Input Schemas ==============

class SearchPostsInput(BaseModel):
    """Input schema for search_posts tool."""
    keywords: str = Field(..., description="Search keywords, multiple keywords separated by comma")
    limit: int = Field(default=20, description="Maximum number of results to return", ge=1, le=100)


class GetPostDetailInput(BaseModel):
    """Input schema for get_post_detail tool."""
    post_id: str = Field(..., description="Post ID (tid) or full URL")


class GetPostCommentsInput(BaseModel):
    """Input schema for get_post_comments tool."""
    post_id: str = Field(..., description="Post ID or full URL")
    limit: int = Field(default=50, description="Maximum number of comments to return", ge=1, le=200)


class GetTiebaInfoInput(BaseModel):
    """Input schema for get_tieba_info tool."""
    tieba_name: str = Field(..., description="Tieba name (贴吧名称)")


# ============== Adapter Implementation ==============

class TiebaSignalAdapter(BaseSignalSource):
    """
    Baidu Tieba Signal Source Adapter.

    Provides tools for:
    - Searching posts by keywords
    - Getting post details
    - Getting post replies
    - Getting tieba (forum) information
    """

    def __init__(self, headless: bool = True):
        super().__init__(
            platform="tieba",
            name="Tieba Adapter",
            description="Signal source adapter for Baidu Tieba forum platform"
        )
        self.headless = headless
        self._crawler = None

    async def initialize(self) -> bool:
        """Initialize the crawler."""
        try:
            from media_adapter.platforms.tieba import TieBaCrawler
            from media_adapter import config

            config.HEADLESS = self.headless
            self._crawler = TieBaCrawler()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[TiebaAdapter] Initialization failed: {e}")
            return False

    async def check_trigger(
        self,
        keywords: List[str],
        threshold: int = 100,
        **kwargs
    ) -> List[SignalEvent]:
        """Trigger Mode: Check for anomalies (placeholder)."""
        # TODO: Implement actual trigger logic
        return []

    def get_tools(self) -> List[AdapterTool]:
        """Reference Mode: Get available tools."""
        return [
            AdapterTool(
                name="tieba_search_posts",
                description="Search Baidu Tieba posts by keywords. Returns list of posts with title, author, reply count.",
                func=self.search_posts,
                args_schema=SearchPostsInput,
            ),
            AdapterTool(
                name="tieba_get_post_detail",
                description="Get detailed information about a specific Tieba post (thread).",
                func=self.get_post_detail,
                args_schema=GetPostDetailInput,
            ),
            AdapterTool(
                name="tieba_get_post_replies",
                description="Get replies for a specific Tieba post.",
                func=self.get_post_comments,
                args_schema=GetPostCommentsInput,
            ),
            AdapterTool(
                name="tieba_get_forum_info",
                description="Get information about a Tieba forum (贴吧) including member count and post count.",
                func=self.get_tieba_info,
                args_schema=GetTiebaInfoInput,
            ),
        ]

    async def search_posts(
        self,
        keywords: str,
        limit: int = 20
    ) -> ToolResult:
        """Search Tieba posts by keywords."""
        try:
            from media_adapter.platforms.tieba.client import TieBaClient
            from playwright.async_api import async_playwright

            results = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = TieBaClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                keyword_list = [k.strip() for k in keywords.split(",")]
                for keyword in keyword_list:
                    try:
                        posts = await client.get_notes_by_keyword(
                            keyword=keyword,
                            page=1,
                        )
                        for post in posts[:limit // len(keyword_list)]:
                            results.append({
                                "post_id": post.get("tid", ""),
                                "title": post.get("title", ""),
                                "content": post.get("content", ""),
                                "author": post.get("author_name", ""),
                                "author_id": post.get("author_portrait", ""),
                                "tieba_name": post.get("fname", ""),
                                "reply_num": post.get("reply_num", 0),
                                "create_time": post.get("create_time", ""),
                                "keyword": keyword,
                            })
                    except Exception as e:
                        print(f"[TiebaAdapter] Error searching keyword '{keyword}': {e}")

                await browser.close()

            return ToolResult(
                success=True,
                data=results[:limit],
                metadata={"total": len(results), "keywords": keyword_list, "platform": self.platform}
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_post_detail(self, post_id: str) -> ToolResult:
        """Get detailed information about a post."""
        try:
            if "tieba.baidu.com" in post_id:
                import re
                match = re.search(r'/p/(\d+)', post_id)
                if match:
                    post_id = match.group(1)

            from media_adapter.platforms.tieba.client import TieBaClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = TieBaClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                post_detail = await client.get_note_by_id(post_id)
                await browser.close()

            if post_detail:
                return ToolResult(
                    success=True,
                    data={
                        "post_id": post_detail.get("tid", post_id),
                        "title": post_detail.get("title", ""),
                        "content": post_detail.get("content", ""),
                        "author": post_detail.get("author_name", ""),
                        "author_id": post_detail.get("author_portrait", ""),
                        "tieba_name": post_detail.get("fname", ""),
                        "reply_num": post_detail.get("reply_num", 0),
                        "create_time": post_detail.get("create_time", ""),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"Post not found: {post_id}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_post_comments(self, post_id: str, limit: int = 50) -> ToolResult:
        """Get replies for a post."""
        try:
            if "tieba.baidu.com" in post_id:
                import re
                match = re.search(r'/p/(\d+)', post_id)
                if match:
                    post_id = match.group(1)

            from media_adapter.platforms.tieba.client import TieBaClient
            from playwright.async_api import async_playwright

            comments = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = TieBaClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                result = await client.get_note_all_comments(
                    note_detail={},
                    note_id=post_id,
                    crawl_interval=0.5,
                )
                for comment in result[:limit]:
                    comments.append({
                        "comment_id": comment.get("pid", ""),
                        "content": comment.get("content", ""),
                        "author": comment.get("author_name", ""),
                        "author_id": comment.get("author_portrait", ""),
                        "floor": comment.get("floor", 0),
                        "create_time": comment.get("create_time", ""),
                    })

                await browser.close()

            return ToolResult(
                success=True,
                data=comments[:limit],
                metadata={"total": len(comments), "post_id": post_id, "platform": self.platform}
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_tieba_info(self, tieba_name: str) -> ToolResult:
        """Get tieba (forum) information."""
        try:
            from media_adapter.platforms.tieba.client import TieBaClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = TieBaClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                tieba_info = await client.get_tieba_info(tieba_name)
                await browser.close()

            if tieba_info:
                return ToolResult(
                    success=True,
                    data={
                        "tieba_name": tieba_info.get("fname", tieba_name),
                        "slogan": tieba_info.get("slogan", ""),
                        "member_num": tieba_info.get("member_num", 0),
                        "post_num": tieba_info.get("post_num", 0),
                        "thread_num": tieba_info.get("thread_num", 0),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"Tieba not found: {tieba_name}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._initialized = False
