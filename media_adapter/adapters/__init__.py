# -*- coding: utf-8 -*-
"""
Media Adapter Signal Source Adapters

Provides adapters for various social media platforms that implement
the BaseSignalSource interface for both Trigger and Reference modes.

Supported Platforms:
- xhs: Xiaohongshu (Little Red Book)
- douyin: Douyin (TikTok China)
- kuaishou: Kuaishou
- bilibili: Bilibili
- weibo: Weibo
- tieba: Baidu Tieba
- zhihu: Zhihu
"""

from media_adapter.adapters.base import (
    BaseSignalSource,
    SignalEvent,
    SignalEventType,
    SignalSeverity,
    AdapterTool,
    ToolResult,
)

# Lazy imports to avoid circular dependencies
def get_xhs_adapter():
    from media_adapter.adapters.xhs import XhsSignalAdapter
    return XhsSignalAdapter

def get_douyin_adapter():
    from media_adapter.adapters.douyin import DouyinSignalAdapter
    return DouyinSignalAdapter

def get_kuaishou_adapter():
    from media_adapter.adapters.kuaishou import KuaishouSignalAdapter
    return KuaishouSignalAdapter

def get_bilibili_adapter():
    from media_adapter.adapters.bilibili import BilibiliSignalAdapter
    return BilibiliSignalAdapter

def get_weibo_adapter():
    from media_adapter.adapters.weibo import WeiboSignalAdapter
    return WeiboSignalAdapter

def get_tieba_adapter():
    from media_adapter.adapters.tieba import TiebaSignalAdapter
    return TiebaSignalAdapter

def get_zhihu_adapter():
    from media_adapter.adapters.zhihu import ZhihuSignalAdapter
    return ZhihuSignalAdapter


# Adapter registry
ADAPTER_REGISTRY = {
    "xhs": get_xhs_adapter,
    "douyin": get_douyin_adapter,
    "kuaishou": get_kuaishou_adapter,
    "bilibili": get_bilibili_adapter,
    "weibo": get_weibo_adapter,
    "tieba": get_tieba_adapter,
    "zhihu": get_zhihu_adapter,
}


def create_adapter(platform: str, **kwargs) -> BaseSignalSource:
    """
    Factory function to create an adapter for the specified platform.

    Args:
        platform: Platform identifier (xhs, douyin, etc.)
        **kwargs: Additional arguments passed to adapter constructor

    Returns:
        Initialized adapter instance

    Raises:
        ValueError: If platform is not supported
    """
    if platform not in ADAPTER_REGISTRY:
        supported = ", ".join(sorted(ADAPTER_REGISTRY.keys()))
        raise ValueError(f"Unsupported platform: {platform}. Supported: {supported}")

    adapter_class = ADAPTER_REGISTRY[platform]()
    return adapter_class(**kwargs)


__all__ = [
    # Base classes
    "BaseSignalSource",
    "SignalEvent",
    "SignalEventType",
    "SignalSeverity",
    "AdapterTool",
    "ToolResult",
    # Factory
    "create_adapter",
    "ADAPTER_REGISTRY",
]
