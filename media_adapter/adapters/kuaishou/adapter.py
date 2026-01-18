# -*- coding: utf-8 -*-
"""
Kuaishou Signal Source Adapter

Implements BaseSignalSource interface for Kuaishou platform.
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


# ============== Tool Input Schemas ==============

class SearchVideosInput(BaseModel):
    """Input schema for search_videos tool."""
    keywords: str = Field(..., description="Search keywords, multiple keywords separated by comma")
    limit: int = Field(default=20, description="Maximum number of results to return", ge=1, le=100)


class GetVideoDetailInput(BaseModel):
    """Input schema for get_video_detail tool."""
    video_id: str = Field(..., description="Video ID (photo_id) or full URL")


class GetVideoCommentsInput(BaseModel):
    """Input schema for get_video_comments tool."""
    video_id: str = Field(..., description="Video ID or full URL")
    limit: int = Field(default=50, description="Maximum number of comments to return", ge=1, le=200)


class GetCreatorInfoInput(BaseModel):
    """Input schema for get_creator_info tool."""
    creator_id: str = Field(..., description="Creator user ID or profile URL")


# ============== Adapter Implementation ==============

class KuaishouSignalAdapter(BaseSignalSource):
    """
    Kuaishou Signal Source Adapter.

    Provides tools for:
    - Searching videos by keywords
    - Getting video details
    - Getting video comments
    - Getting creator information
    """

    def __init__(self, headless: bool = True):
        super().__init__(
            platform="kuaishou",
            name="Kuaishou Adapter",
            description="Signal source adapter for Kuaishou platform"
        )
        self.headless = headless
        self._crawler = None

    async def initialize(self) -> bool:
        """Initialize the crawler."""
        try:
            from media_adapter.platforms.kuaishou import KuaishouCrawler
            from media_adapter import config

            config.HEADLESS = self.headless
            self._crawler = KuaishouCrawler()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[KuaishouAdapter] Initialization failed: {e}")
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
                name="kuaishou_search_videos",
                description="Search Kuaishou videos by keywords. Returns list of videos with title, author, likes, views.",
                func=self.search_videos,
                args_schema=SearchVideosInput,
            ),
            AdapterTool(
                name="kuaishou_get_video_detail",
                description="Get detailed information about a specific Kuaishou video.",
                func=self.get_video_detail,
                args_schema=GetVideoDetailInput,
            ),
            AdapterTool(
                name="kuaishou_get_video_comments",
                description="Get comments for a specific Kuaishou video.",
                func=self.get_video_comments,
                args_schema=GetVideoCommentsInput,
            ),
            AdapterTool(
                name="kuaishou_get_creator_info",
                description="Get information about a Kuaishou creator/influencer.",
                func=self.get_creator_info,
                args_schema=GetCreatorInfoInput,
            ),
        ]

    async def search_videos(
        self,
        keywords: str,
        limit: int = 20
    ) -> ToolResult:
        """Search Kuaishou videos by keywords."""
        try:
            from media_adapter.platforms.kuaishou.client import KuaishouClient
            from playwright.async_api import async_playwright

            results = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = KuaishouClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                keyword_list = [k.strip() for k in keywords.split(",")]
                for keyword in keyword_list:
                    try:
                        videos = await client.search_info_by_keyword(
                            keyword=keyword,
                            pcursor="",
                        )
                        for video in videos.get("visionSearchPhoto", {}).get("feeds", [])[:limit // len(keyword_list)]:
                            results.append({
                                "video_id": video.get("photo", {}).get("id", ""),
                                "title": video.get("photo", {}).get("caption", ""),
                                "author": video.get("author", {}).get("name", ""),
                                "author_id": video.get("author", {}).get("id", ""),
                                "like_count": video.get("photo", {}).get("likeCount", 0),
                                "comment_count": video.get("photo", {}).get("commentCount", 0),
                                "view_count": video.get("photo", {}).get("viewCount", 0),
                                "keyword": keyword,
                            })
                    except Exception as e:
                        print(f"[KuaishouAdapter] Error searching keyword '{keyword}': {e}")

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
            from media_adapter.platforms.kuaishou.help import parse_video_info_from_url

            if "kuaishou.com" in video_id:
                video_id = parse_video_info_from_url(video_id)

            from media_adapter.platforms.kuaishou.client import KuaishouClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = KuaishouClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                video_detail = await client.get_video_info(video_id)
                await browser.close()

            if video_detail:
                photo = video_detail.get("visionVideoDetail", {}).get("photo", {})
                return ToolResult(
                    success=True,
                    data={
                        "video_id": photo.get("id", video_id),
                        "title": photo.get("caption", ""),
                        "author": video_detail.get("visionVideoDetail", {}).get("author", {}).get("name", ""),
                        "like_count": photo.get("likeCount", 0),
                        "comment_count": photo.get("commentCount", 0),
                        "view_count": photo.get("viewCount", 0),
                        "share_count": photo.get("shareCount", 0),
                        "timestamp": photo.get("timestamp", 0),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"Video not found: {video_id}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_video_comments(self, video_id: str, limit: int = 50) -> ToolResult:
        """Get comments for a video."""
        try:
            from media_adapter.platforms.kuaishou.help import parse_video_info_from_url

            if "kuaishou.com" in video_id:
                video_id = parse_video_info_from_url(video_id)

            from media_adapter.platforms.kuaishou.client import KuaishouClient
            from playwright.async_api import async_playwright

            comments = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = KuaishouClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                pcursor = ""
                while len(comments) < limit:
                    result = await client.get_video_all_comments(
                        photo_id=video_id,
                        pcursor=pcursor,
                    )
                    if not result:
                        break

                    for comment in result.get("visionCommentList", {}).get("rootComments", []):
                        comments.append({
                            "comment_id": comment.get("commentId", ""),
                            "content": comment.get("content", ""),
                            "author": comment.get("authorName", ""),
                            "author_id": comment.get("authorId", ""),
                            "like_count": comment.get("likedCount", 0),
                            "timestamp": comment.get("timestamp", 0),
                        })

                    pcursor = result.get("visionCommentList", {}).get("pcursor", "")
                    if not pcursor:
                        break

                await browser.close()

            return ToolResult(
                success=True,
                data=comments[:limit],
                metadata={"total": len(comments), "video_id": video_id, "platform": self.platform}
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_creator_info(self, creator_id: str) -> ToolResult:
        """Get creator information."""
        try:
            if "kuaishou.com" in creator_id:
                import re
                match = re.search(r'/profile/([a-zA-Z0-9_]+)', creator_id)
                if match:
                    creator_id = match.group(1)

            from media_adapter.platforms.kuaishou.client import KuaishouClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = KuaishouClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                user_info = await client.get_user_info(creator_id)
                await browser.close()

            if user_info:
                user = user_info.get("visionProfile", {}).get("userProfile", {})
                return ToolResult(
                    success=True,
                    data={
                        "user_id": user.get("user_id", creator_id),
                        "name": user.get("user_name", ""),
                        "sex": user.get("sex", ""),
                        "description": user.get("user_text", ""),
                        "fan": user.get("ownerCount", {}).get("fan", 0),
                        "follow": user.get("ownerCount", {}).get("follow", 0),
                        "photo_public": user.get("ownerCount", {}).get("photo_public", 0),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"Creator not found: {creator_id}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._initialized = False
