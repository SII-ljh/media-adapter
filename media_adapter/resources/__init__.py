# -*- coding: utf-8 -*-
"""Resource loader for JavaScript files and other static assets."""

import os
from pathlib import Path
from functools import lru_cache


def _get_resources_dir() -> Path:
    """Get the resources directory path."""
    return Path(__file__).parent


@lru_cache(maxsize=None)
def get_resource_path(filename: str) -> str:
    """
    Get the absolute path to a resource file.

    Args:
        filename: Name of the resource file (e.g., 'stealth.min.js')

    Returns:
        Absolute path to the resource file as string
    """
    resource_path = _get_resources_dir() / filename
    if not resource_path.exists():
        raise FileNotFoundError(f"Resource file not found: {filename}")
    return str(resource_path)


def get_stealth_js_path() -> str:
    """Get path to stealth.min.js for Playwright injection."""
    return get_resource_path("stealth.min.js")


def get_douyin_js_path() -> str:
    """Get path to douyin.js for signing."""
    return get_resource_path("douyin.js")


def get_zhihu_js_path() -> str:
    """Get path to zhihu.js for signing."""
    return get_resource_path("zhihu.js")


def read_js_content(filename: str) -> str:
    """
    Read JavaScript file content.

    Args:
        filename: Name of the JS file

    Returns:
        Content of the JavaScript file
    """
    resource_path = get_resource_path(filename)
    with open(resource_path, "r", encoding="utf-8-sig") as f:
        return f.read()


# Convenience functions
def get_stealth_js_content() -> str:
    """Read stealth.min.js content."""
    return read_js_content("stealth.min.js")


def get_douyin_js_content() -> str:
    """Read douyin.js content."""
    return read_js_content("douyin.js")


def get_zhihu_js_content() -> str:
    """Read zhihu.js content."""
    return read_js_content("zhihu.js")
