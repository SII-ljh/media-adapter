# -*- coding: utf-8 -*-
"""
Cookie Manager for Media Adapter

Manages cookies from txt files for multiple platforms and accounts.

Cookie file format (txt):
- Each line is a cookie string for one account
- Empty lines and lines starting with # are ignored
- Format: key1=value1; key2=value2; ...

Example cookies/xhs_cookies.txt:
# Account 1 - Main
a1=xxx; web_session=xxx; ...

# Account 2 - Backup
a1=yyy; web_session=yyy; ...
"""

import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CookieManager:
    """
    Cookie manager that reads cookies from txt files.

    Supports multiple accounts per platform with random or sequential selection.

    Usage:
        manager = CookieManager("./cookies")

        # Get a cookie for xhs (random selection if multiple)
        cookie_str = manager.get_cookie("xhs")

        # Get specific account
        cookie_str = manager.get_cookie("xhs", account_index=0)

        # Get all cookies for a platform
        cookies = manager.get_all_cookies("xhs")
    """

    def __init__(self, cookies_dir: str = "./cookies"):
        """
        Initialize cookie manager.

        Args:
            cookies_dir: Directory containing cookie txt files
        """
        self.cookies_dir = Path(cookies_dir)
        self._cache: Dict[str, List[str]] = {}

        # Platform to filename mapping
        self.platform_files = {
            "xhs": "xhs_cookies.txt",
            "xiaohongshu": "xhs_cookies.txt",
            "weibo": "weibo_cookies.txt",
            "wb": "weibo_cookies.txt",
            "douyin": "douyin_cookies.txt",
            "dy": "douyin_cookies.txt",
            "bilibili": "bilibili_cookies.txt",
            "bili": "bilibili_cookies.txt",
            "kuaishou": "kuaishou_cookies.txt",
            "ks": "kuaishou_cookies.txt",
            "tieba": "tieba_cookies.txt",
            "zhihu": "zhihu_cookies.txt",
        }

    def _load_cookies_from_file(self, filepath: Path) -> List[str]:
        """Load cookies from a txt file."""
        cookies = []
        if not filepath.exists():
            return cookies

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Validate it looks like a cookie string
                if "=" in line:
                    cookies.append(line)

        return cookies

    def _get_cookie_file(self, platform: str) -> Path:
        """Get cookie file path for a platform."""
        filename = self.platform_files.get(platform.lower(), f"{platform}_cookies.txt")
        return self.cookies_dir / filename

    def get_cookie(
        self,
        platform: str,
        account_index: Optional[int] = None,
        random_select: bool = True
    ) -> str:
        """
        Get a cookie string for the specified platform.

        Args:
            platform: Platform identifier (xhs, weibo, douyin, etc.)
            account_index: Specific account index to use (0-based)
            random_select: If True and account_index is None, randomly select

        Returns:
            Cookie string, or empty string if no cookies available
        """
        cookies = self.get_all_cookies(platform)

        if not cookies:
            return ""

        if account_index is not None:
            if 0 <= account_index < len(cookies):
                return cookies[account_index]
            return ""

        if random_select:
            return random.choice(cookies)

        return cookies[0]

    def get_all_cookies(self, platform: str) -> List[str]:
        """
        Get all cookies for a platform.

        Args:
            platform: Platform identifier

        Returns:
            List of cookie strings
        """
        platform = platform.lower()

        # Use cache if available
        if platform in self._cache:
            return self._cache[platform]

        cookie_file = self._get_cookie_file(platform)
        cookies = self._load_cookies_from_file(cookie_file)

        # Cache the result
        self._cache[platform] = cookies

        return cookies

    def get_account_count(self, platform: str) -> int:
        """Get number of accounts available for a platform."""
        return len(self.get_all_cookies(platform))

    def clear_cache(self):
        """Clear the cookie cache to reload from files."""
        self._cache.clear()

    def ensure_cookies_dir(self):
        """Create cookies directory if it doesn't exist."""
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def save_cookie(
        self,
        platform: str,
        cookie_str: str,
        account_index: int = 0
    ) -> bool:
        """
        Save/update a cookie string to the txt file.

        This implements cookie persistence - after successful login,
        the latest cookies are written back to the file for future use.

        Args:
            platform: Platform identifier (xhs, weibo, douyin, etc.)
            cookie_str: New cookie string to save
            account_index: Which account slot to update (0-based, default 0)

        Returns:
            True if save successful, False otherwise
        """
        if not cookie_str or not cookie_str.strip():
            return False

        try:
            self.ensure_cookies_dir()
            cookie_file = self._get_cookie_file(platform)

            # Read existing file content
            lines = []
            cookie_lines_indices = []  # Track which lines are actual cookies

            if cookie_file.exists():
                with open(cookie_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        lines.append(line.rstrip('\n'))
                        # Track cookie lines (non-empty, non-comment, has =)
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#") and "=" in stripped:
                            cookie_lines_indices.append(i)

            # Determine where to put the new cookie
            if account_index < len(cookie_lines_indices):
                # Update existing cookie at the specified index
                target_line = cookie_lines_indices[account_index]
                lines[target_line] = cookie_str.strip()
            else:
                # Add new cookie at the end
                if lines and lines[-1]:  # Add blank line if file doesn't end with one
                    lines.append("")
                lines.append(f"# Account {len(cookie_lines_indices) + 1} - Auto-saved after login")
                lines.append(cookie_str.strip())

            # Write back to file
            with open(cookie_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
                if lines:
                    f.write("\n")

            # Clear cache so next read gets fresh data
            if platform.lower() in self._cache:
                del self._cache[platform.lower()]

            print(f"[CookieManager] Saved cookie for {platform} (account {account_index})")
            return True

        except Exception as e:
            print(f"[CookieManager] Failed to save cookie for {platform}: {e}")
            return False

    def create_template(self, platform: str):
        """Create a template cookie file for a platform."""
        self.ensure_cookies_dir()
        cookie_file = self._get_cookie_file(platform)

        if cookie_file.exists():
            return

        template = f"""# {platform.upper()} Cookies
# Each line is a cookie string for one account
# Empty lines and lines starting with # are ignored
# Format: key1=value1; key2=value2; ...

# Account 1 - paste your cookie string below
# Example: a1=xxx; web_session=yyy; ...

"""
        with open(cookie_file, "w", encoding="utf-8") as f:
            f.write(template)


def parse_cookie_string(cookie_str: str) -> Dict[str, str]:
    """
    Parse cookie string to dictionary.

    Args:
        cookie_str: Cookie string (key1=value1; key2=value2; ...)

    Returns:
        Dictionary of cookie name-value pairs
    """
    if not cookie_str:
        return {}

    cookie_dict = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            cookie_dict[key.strip()] = value.strip()

    return cookie_dict


def format_cookies_for_playwright(
    cookie_str: str,
    domain: str,
    path: str = "/"
) -> List[Dict]:
    """
    Format cookie string for Playwright browser context.

    Args:
        cookie_str: Cookie string
        domain: Cookie domain (e.g., ".xiaohongshu.com")
        path: Cookie path

    Returns:
        List of cookie dicts for Playwright
    """
    cookie_dict = parse_cookie_string(cookie_str)
    cookies = []

    for name, value in cookie_dict.items():
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
        })

    return cookies


# Global cookie manager instance
_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager(cookies_dir: str = "./cookies") -> CookieManager:
    """
    Get or create the global cookie manager instance.

    Args:
        cookies_dir: Directory containing cookie files

    Returns:
        CookieManager instance
    """
    global _cookie_manager

    if _cookie_manager is None or str(_cookie_manager.cookies_dir) != cookies_dir:
        _cookie_manager = CookieManager(cookies_dir)

    return _cookie_manager
