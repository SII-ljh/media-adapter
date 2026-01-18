# -*- coding: utf-8 -*-
"""Path utilities for runtime data directories."""

import os
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def get_data_dir() -> Path:
    """
    Get the data directory for storing crawled content.

    Priority:
    1. MEDIA_ADAPTER_DATA_DIR environment variable
    2. Current working directory / data

    Returns:
        Path to data directory
    """
    env_path = os.environ.get("MEDIA_ADAPTER_DATA_DIR")
    if env_path:
        data_dir = Path(env_path)
    else:
        data_dir = Path.cwd() / "data"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@lru_cache(maxsize=1)
def get_browser_data_dir() -> Path:
    """
    Get the browser data directory for storing browser profiles.

    Priority:
    1. MEDIA_ADAPTER_BROWSER_DATA_DIR environment variable
    2. Current working directory / browser_data

    Returns:
        Path to browser data directory
    """
    env_path = os.environ.get("MEDIA_ADAPTER_BROWSER_DATA_DIR")
    if env_path:
        browser_dir = Path(env_path)
    else:
        browser_dir = Path.cwd() / "browser_data"

    browser_dir.mkdir(parents=True, exist_ok=True)
    return browser_dir


def get_platform_data_dir(platform: str) -> Path:
    """Get data directory for a specific platform."""
    platform_dir = get_data_dir() / platform
    platform_dir.mkdir(parents=True, exist_ok=True)
    return platform_dir


def get_platform_browser_dir(platform: str) -> Path:
    """Get browser data directory for a specific platform."""
    user_data_dir = get_browser_data_dir() / f"{platform}_user_data_dir"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return user_data_dir
