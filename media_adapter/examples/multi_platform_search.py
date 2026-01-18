# -*- coding: utf-8 -*-
"""
Example: Multi-Platform Search.

This script demonstrates how to crawl multiple platforms sequentially.
"""

import asyncio
import sys
import os

# Ensure the project root is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from media_adapter import config, CrawlerFactory

async def crawl_platform(platform_code: str, keywords: str):
    print(f"\n=== Starting crawl for {platform_code} ===")
    
    # Update global config for this run
    config.PLATFORM = platform_code
    config.KEYWORDS = keywords
    config.CRAWLER_TYPE = "search"
    config.SAVE_DATA_OPTION = "json"
    config.HEADLESS = False # or True
    config.CRAWLER_MAX_NOTES_COUNT = 3 # Keep it short for demo

    # Create crawler
    crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
    
    try:
        await crawler.start()
        print(f"=== Finished crawl for {platform_code} ===")
    except Exception as e:
        print(f"Error crawling {platform_code}: {e}")
    finally:
        if hasattr(crawler, "close"):
            await crawler.close()

async def main():
    # List of platforms to crawl
    # Ensure you have the necessary login requirements (cookies/QR code) as needed for each.
    platforms = [
        ("xhs", "Python programming"),
        # ("dy", "Python programming"), # Uncomment to enable Douyin
        # ("bili", "Python tutorial")   # Uncomment to enable Bilibili
    ]

    for platform, keyword in platforms:
        await crawl_platform(platform, keyword)
        # Optional: rest between platforms
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
