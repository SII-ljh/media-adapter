# -*- coding: utf-8 -*-
"""
Media Adapter - A multi-platform social media data crawler

Supports: Xiaohongshu, Douyin, Kuaishou, Bilibili, Weibo, Tieba, Zhihu

Example usage:
    from media_adapter import XiaoHongShuCrawler, config

    # Configure the crawler
    config.PLATFORM = "xhs"
    config.CRAWLER_TYPE = "search"

    # Create and run crawler
    crawler = XiaoHongShuCrawler()
    await crawler.start()
"""

from media_adapter._version import __version__

# Core abstractions
from media_adapter.core.base_crawler import (
    AbstractCrawler,
    AbstractLogin,
    AbstractStore,
    AbstractStoreImage,
    AbstractStoreVideo,
    AbstractApiClient,
)

# Platform crawlers
from media_adapter.platforms.xhs import XiaoHongShuCrawler
from media_adapter.platforms.douyin import DouYinCrawler
from media_adapter.platforms.kuaishou import KuaishouCrawler
from media_adapter.platforms.bilibili import BilibiliCrawler
from media_adapter.platforms.weibo import WeiboCrawler
from media_adapter.platforms.tieba import TieBaCrawler
from media_adapter.platforms.zhihu import ZhihuCrawler

# Aliases for convenience
DouyinCrawler = DouYinCrawler
XhsCrawler = XiaoHongShuCrawler
TiebaCrawler = TieBaCrawler

# Crawler factory
from media_adapter.app import CrawlerFactory

# Context variables
from media_adapter.context import (
    request_keyword_var,
    crawler_type_var,
    comment_tasks_var,
    db_conn_pool_var,
    source_keyword_var,
)

# Configuration module
from media_adapter import config

# Database module
from media_adapter.database import db

__all__ = [
    # Version
    "__version__",

    # Core abstractions
    "AbstractCrawler",
    "AbstractLogin",
    "AbstractStore",
    "AbstractStoreImage",
    "AbstractStoreVideo",
    "AbstractApiClient",

    # Platform crawlers
    "XiaoHongShuCrawler",
    "DouYinCrawler",
    "KuaishouCrawler",
    "BilibiliCrawler",
    "WeiboCrawler",
    "TieBaCrawler",
    "ZhihuCrawler",
    # Aliases
    "DouyinCrawler",
    "XhsCrawler",
    "TiebaCrawler",

    # Factories
    "CrawlerFactory",

    # Context variables
    "request_keyword_var",
    "crawler_type_var",
    "comment_tasks_var",
    "db_conn_pool_var",
    "source_keyword_var",

    # Modules
    "config",
    "db",
]
