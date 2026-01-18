# -*- coding: utf-8 -*-
"""
Zhihu Signal Source Adapter

Implements BaseSignalSource interface for Zhihu platform.
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

class SearchContentInput(BaseModel):
    """Input schema for search_content tool."""
    keywords: str = Field(..., description="Search keywords, multiple keywords separated by comma")
    limit: int = Field(default=20, description="Maximum number of results to return", ge=1, le=100)
    content_type: str = Field(default="general", description="Content type: general, question, answer, article")


class GetQuestionDetailInput(BaseModel):
    """Input schema for get_question_detail tool."""
    question_id: str = Field(..., description="Question ID or full URL")


class GetAnswerDetailInput(BaseModel):
    """Input schema for get_answer_detail tool."""
    answer_id: str = Field(..., description="Answer ID or full URL")


class GetAnswerCommentsInput(BaseModel):
    """Input schema for get_answer_comments tool."""
    answer_id: str = Field(..., description="Answer ID or full URL")
    limit: int = Field(default=50, description="Maximum number of comments to return", ge=1, le=200)


class GetUserInfoInput(BaseModel):
    """Input schema for get_user_info tool."""
    user_id: str = Field(..., description="User url_token or profile URL")


# ============== Adapter Implementation ==============

class ZhihuSignalAdapter(BaseSignalSource):
    """
    Zhihu Signal Source Adapter.

    Provides tools for:
    - Searching questions/answers/articles by keywords
    - Getting question details
    - Getting answer details and comments
    - Getting user information
    """

    def __init__(self, headless: bool = True):
        super().__init__(
            platform="zhihu",
            name="Zhihu Adapter",
            description="Signal source adapter for Zhihu Q&A platform"
        )
        self.headless = headless
        self._crawler = None

    async def initialize(self) -> bool:
        """Initialize the crawler."""
        try:
            from media_adapter.platforms.zhihu import ZhihuCrawler
            from media_adapter import config

            config.HEADLESS = self.headless
            self._crawler = ZhihuCrawler()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[ZhihuAdapter] Initialization failed: {e}")
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
                name="zhihu_search_content",
                description="Search Zhihu content by keywords. Returns questions, answers, and articles.",
                func=self.search_content,
                args_schema=SearchContentInput,
            ),
            AdapterTool(
                name="zhihu_get_question_detail",
                description="Get detailed information about a Zhihu question including answer count and followers.",
                func=self.get_question_detail,
                args_schema=GetQuestionDetailInput,
            ),
            AdapterTool(
                name="zhihu_get_answer_detail",
                description="Get detailed information about a specific Zhihu answer.",
                func=self.get_answer_detail,
                args_schema=GetAnswerDetailInput,
            ),
            AdapterTool(
                name="zhihu_get_answer_comments",
                description="Get comments for a specific Zhihu answer. Useful for sentiment analysis.",
                func=self.get_answer_comments,
                args_schema=GetAnswerCommentsInput,
            ),
            AdapterTool(
                name="zhihu_get_user_info",
                description="Get information about a Zhihu user including follower count and answer stats.",
                func=self.get_user_info,
                args_schema=GetUserInfoInput,
            ),
        ]

    async def search_content(
        self,
        keywords: str,
        limit: int = 20,
        content_type: str = "general"
    ) -> ToolResult:
        """Search Zhihu content by keywords."""
        try:
            from media_adapter.platforms.zhihu.client import ZhihuClient
            from playwright.async_api import async_playwright

            results = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = ZhihuClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                keyword_list = [k.strip() for k in keywords.split(",")]
                for keyword in keyword_list:
                    try:
                        # Map content_type to search_type
                        type_map = {
                            "general": "general",
                            "question": "question",
                            "answer": "general",
                            "article": "article",
                        }
                        search_type = type_map.get(content_type, "general")

                        contents = await client.get_note_by_keyword(
                            keyword=keyword,
                            page=1,
                            sort="default",
                        )
                        for content in contents[:limit // len(keyword_list)]:
                            result_item = {
                                "content_id": content.get("id", ""),
                                "type": content.get("type", ""),
                                "title": content.get("title", ""),
                                "content": content.get("excerpt", "") or content.get("content", ""),
                                "author": content.get("author", {}).get("name", ""),
                                "author_id": content.get("author", {}).get("url_token", ""),
                                "voteup_count": content.get("voteup_count", 0),
                                "comment_count": content.get("comment_count", 0),
                                "created_time": content.get("created_time", 0),
                                "keyword": keyword,
                            }
                            # Add question-specific fields
                            if content.get("type") == "answer":
                                result_item["question_id"] = content.get("question", {}).get("id", "")
                                result_item["question_title"] = content.get("question", {}).get("title", "")
                            results.append(result_item)
                    except Exception as e:
                        print(f"[ZhihuAdapter] Error searching keyword '{keyword}': {e}")

                await browser.close()

            return ToolResult(
                success=True,
                data=results[:limit],
                metadata={"total": len(results), "keywords": keyword_list, "platform": self.platform}
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_question_detail(self, question_id: str) -> ToolResult:
        """Get question details."""
        try:
            if "zhihu.com" in question_id:
                import re
                match = re.search(r'/question/(\d+)', question_id)
                if match:
                    question_id = match.group(1)

            from media_adapter.platforms.zhihu.client import ZhihuClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = ZhihuClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                question_detail = await client.get_question_by_id(question_id)
                await browser.close()

            if question_detail:
                return ToolResult(
                    success=True,
                    data={
                        "question_id": question_detail.get("id", question_id),
                        "title": question_detail.get("title", ""),
                        "detail": question_detail.get("detail", ""),
                        "answer_count": question_detail.get("answer_count", 0),
                        "follower_count": question_detail.get("follower_count", 0),
                        "comment_count": question_detail.get("comment_count", 0),
                        "created": question_detail.get("created", 0),
                        "updated_time": question_detail.get("updated_time", 0),
                        "topics": [t.get("name", "") for t in question_detail.get("topics", [])],
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"Question not found: {question_id}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_answer_detail(self, answer_id: str) -> ToolResult:
        """Get answer details."""
        try:
            if "zhihu.com" in answer_id:
                import re
                match = re.search(r'/answer/(\d+)', answer_id)
                if match:
                    answer_id = match.group(1)

            from media_adapter.platforms.zhihu.client import ZhihuClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = ZhihuClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                answer_detail = await client.get_answer_by_id(answer_id)
                await browser.close()

            if answer_detail:
                return ToolResult(
                    success=True,
                    data={
                        "answer_id": answer_detail.get("id", answer_id),
                        "content": answer_detail.get("content", ""),
                        "excerpt": answer_detail.get("excerpt", ""),
                        "author": answer_detail.get("author", {}).get("name", ""),
                        "author_id": answer_detail.get("author", {}).get("url_token", ""),
                        "voteup_count": answer_detail.get("voteup_count", 0),
                        "comment_count": answer_detail.get("comment_count", 0),
                        "created_time": answer_detail.get("created_time", 0),
                        "updated_time": answer_detail.get("updated_time", 0),
                        "question_id": answer_detail.get("question", {}).get("id", ""),
                        "question_title": answer_detail.get("question", {}).get("title", ""),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"Answer not found: {answer_id}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_answer_comments(self, answer_id: str, limit: int = 50) -> ToolResult:
        """Get comments for an answer."""
        try:
            if "zhihu.com" in answer_id:
                import re
                match = re.search(r'/answer/(\d+)', answer_id)
                if match:
                    answer_id = match.group(1)

            from media_adapter.platforms.zhihu.client import ZhihuClient
            from playwright.async_api import async_playwright

            comments = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = ZhihuClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                result = await client.get_answer_all_comments(
                    answer_id=answer_id,
                    crawl_interval=0.5,
                )
                for comment in result[:limit]:
                    comments.append({
                        "comment_id": comment.get("id", ""),
                        "content": comment.get("content", ""),
                        "author": comment.get("author", {}).get("name", ""),
                        "author_id": comment.get("author", {}).get("url_token", ""),
                        "vote_count": comment.get("vote_count", 0),
                        "created_time": comment.get("created_time", 0),
                        "reply_count": comment.get("child_comment_count", 0),
                    })

                await browser.close()

            return ToolResult(
                success=True,
                data=comments[:limit],
                metadata={"total": len(comments), "answer_id": answer_id, "platform": self.platform}
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def get_user_info(self, user_id: str) -> ToolResult:
        """Get user information."""
        try:
            if "zhihu.com" in user_id:
                import re
                match = re.search(r'/people/([a-zA-Z0-9_-]+)', user_id)
                if match:
                    user_id = match.group(1)

            from media_adapter.platforms.zhihu.client import ZhihuClient
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()

                client = ZhihuClient(
                    timeout=60,
                    playwright_page=await context.new_page(),
                    cookie_dict={},
                )

                user_info = await client.get_creator_info(user_id)
                await browser.close()

            if user_info:
                return ToolResult(
                    success=True,
                    data={
                        "url_token": user_info.get("url_token", user_id),
                        "name": user_info.get("name", ""),
                        "headline": user_info.get("headline", ""),
                        "description": user_info.get("description", ""),
                        "follower_count": user_info.get("follower_count", 0),
                        "following_count": user_info.get("following_count", 0),
                        "answer_count": user_info.get("answer_count", 0),
                        "articles_count": user_info.get("articles_count", 0),
                        "voteup_count": user_info.get("voteup_count", 0),
                        "thanked_count": user_info.get("thanked_count", 0),
                    },
                    metadata={"platform": self.platform}
                )
            return ToolResult(success=False, error=f"User not found: {user_id}", metadata={"platform": self.platform})

        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"platform": self.platform})

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._initialized = False
