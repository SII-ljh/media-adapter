# -*- coding: utf-8 -*-
"""
Bilibili Signal Source Adapter

Implements BaseSignalSource interface for Bilibili platform.
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

class SearchVideosInput(BaseModel):
    """Input schema for search_videos tool."""
    keywords: str = Field(..., description="Search keywords, multiple keywords separated by comma")
    limit: int = Field(default=20, description="Maximum number of results to return", ge=1, le=100)
    order: str = Field(default="totalrank", description="Sort order: totalrank, click, pubdate, dm, stow")


class GetVideoDetailInput(BaseModel):
    """Input schema for get_video_detail tool."""
    video_id: str = Field(..., description="Video BV ID or full URL")


class GetVideoCommentsInput(BaseModel):
    """Input schema for get_video_comments tool."""
    video_id: str = Field(..., description="Video BV ID or full URL")
    limit: int = Field(default=50, description="Maximum number of comments to return", ge=1, le=200)


class GetUpInfoInput(BaseModel):
    """Input schema for get_up_info tool."""
    mid: str = Field(..., description="UP主 user ID (mid) or space URL")


# ============== Adapter Implementation ==============

class BilibiliSignalAdapter(BaseSignalSource):
    """
    Bilibili Signal Source Adapter.

    Provides tools for:
    - Searching videos by keywords
    - Getting video details
    - Getting video comments (danmaku/comments)
    - Getting UP主 (creator) information
    """

    def __init__(self, headless: bool = True):
        super().__init__(
            platform="bilibili",
            name="Bilibili Adapter",
            description="Signal source adapter for Bilibili video platform"
        )
        self.headless = headless
        self._crawler = None

    async def initialize(self) -> bool:
        """Initialize the crawler."""
        try:
            from media_adapter.platforms.bilibili import BilibiliCrawler
            from media_adapter import config

            config.HEADLESS = self.headless
            self._crawler = BilibiliCrawler()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[BilibiliAdapter] Initialization failed: {e}")
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
                name="bilibili_search_videos",
                description="Search Bilibili videos by keywords. Returns list of videos with title, author, views, danmaku count.",
                func=self.search_videos,
                args_schema=SearchVideosInput,
            ),
            AdapterTool(
                name="bilibili_get_video_detail",
                description="Get detailed information about a specific Bilibili video including stats and tags.",
                func=self.get_video_detail,
                args_schema=GetVideoDetailInput,
            ),
            AdapterTool(
                name="bilibili_get_video_comments",
                description="Get comments for a specific Bilibili video.",
                func=self.get_video_comments,
                args_schema=GetVideoCommentsInput,
            ),
            AdapterTool(
                name="bilibili_get_up_info",
                description="Get information about a Bilibili UP主 (creator) including follower count and video stats.",
                func=self.get_up_info,
                args_schema=GetUpInfoInput,
            ),
        ]

    async def search_videos(
        self,
        keywords: str,
        limit: int = 20,
        order: str = "totalrank"
    ) -> ToolResult:
        """Search Bilibili videos by keywords."""
        try:
            from media_adapter.platforms.bilibili.client import BilibiliClient
            from playwright.async_api import async_playwright

            results = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = BilibiliClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                keyword_list = [k.strip() for k in keywords.split(",")]
                for keyword in keyword_list:
                    try:
                        videos = await client.search_video_by_keyword(
                            keyword=keyword,
                            page=1,
                            page_size=limit // len(keyword_list),
                            order=order,
                        )
                        for video in videos.get("result", []):
                            results.append({
                                "bvid": video.get("bvid", ""),
                                "aid": video.get("aid", ""),
                                "title": video.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
                                "author": video.get("author", ""),
                                "mid": video.get("mid", ""),
                                "play": video.get("play", 0),
                                "danmaku": video.get("video_review", 0),
                                "favorites": video.get("favorites", 0),
                                "pubdate": video.get("pubdate", 0),
                                "duration": video.get("duration", ""),
                                "description": video.get("description", ""),
                                "keyword": keyword,
                            })
                    except Exception as e:
                        print(f"[BilibiliAdapter] Error searching keyword '{keyword}': {e}")

                await browser.close()

            return ToolResult(
                success=True,
                data=results[:limit],
                metadata={"total": len(results), "keywords": keyword_list, "platform": self.platform}
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_video_detail(self, video_id: str) -> ToolResult:
        """Get detailed information about a video."""
        try:
            from media_adapter.platforms.bilibili.help import parse_video_info_from_url

            if "bilibili.com" in video_id:
                video_id = parse_video_info_from_url(video_id)

            from media_adapter.platforms.bilibili.client import BilibiliClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = BilibiliClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                video_detail = await client.get_video_info(video_id)
                await browser.close()

            if video_detail:
                data = video_detail.get("data", {})
                return ToolResult(
                    success=True,
                    data={
                        "bvid": data.get("bvid", video_id),
                        "aid": data.get("aid", ""),
                        "title": data.get("title", ""),
                        "desc": data.get("desc", ""),
                        "author": data.get("owner", {}).get("name", ""),
                        "mid": data.get("owner", {}).get("mid", ""),
                        "view": data.get("stat", {}).get("view", 0),
                        "danmaku": data.get("stat", {}).get("danmaku", 0),
                        "reply": data.get("stat", {}).get("reply", 0),
                        "favorite": data.get("stat", {}).get("favorite", 0),
                        "coin": data.get("stat", {}).get("coin", 0),
                        "share": data.get("stat", {}).get("share", 0),
                        "like": data.get("stat", {}).get("like", 0),
                        "pubdate": data.get("pubdate", 0),
                        "duration": data.get("duration", 0),
                        "tname": data.get("tname", ""),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"Video not found: {video_id}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_video_comments(self, video_id: str, limit: int = 50) -> ToolResult:
        """Get comments for a video."""
        try:
            from media_adapter.platforms.bilibili.help import parse_video_info_from_url

            if "bilibili.com" in video_id:
                video_id = parse_video_info_from_url(video_id)

            from media_adapter.platforms.bilibili.client import BilibiliClient
            from playwright.async_api import async_playwright

            comments = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = BilibiliClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                # Get video aid first
                video_info = await client.get_video_info(video_id)
                aid = video_info.get("data", {}).get("aid", "")

                if aid:
                    result = await client.get_video_all_comments(
                        video_id=aid,
                        crawl_interval=0.5,
                        is_fetch_sub_comments=False,
                    )
                    for comment in result[:limit]:
                        comments.append({
                            "rpid": comment.get("rpid", ""),
                            "content": comment.get("content", {}).get("message", ""),
                            "author": comment.get("member", {}).get("uname", ""),
                            "mid": comment.get("member", {}).get("mid", ""),
                            "like": comment.get("like", 0),
                            "rcount": comment.get("rcount", 0),
                            "ctime": comment.get("ctime", 0),
                        })

                await browser.close()

            return ToolResult(
                success=True,
                data=comments[:limit],
                metadata={"total": len(comments), "video_id": video_id, "platform": self.platform}
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_up_info(self, mid: str) -> ToolResult:
        """Get UP主 (creator) information."""
        try:
            if "bilibili.com" in mid:
                import re
                match = re.search(r'/(\d+)', mid)
                if match:
                    mid = match.group(1)

            from media_adapter.platforms.bilibili.client import BilibiliClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = BilibiliClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                user_info = await client.get_user_info(mid)
                await browser.close()

            if user_info:
                data = user_info.get("data", {})
                return ToolResult(
                    success=True,
                    data={
                        "mid": data.get("mid", mid),
                        "name": data.get("name", ""),
                        "sex": data.get("sex", ""),
                        "sign": data.get("sign", ""),
                        "level": data.get("level", 0),
                        "fans": data.get("fans", 0),
                        "attention": data.get("attention", 0),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"UP not found: {mid}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._initialized = False
