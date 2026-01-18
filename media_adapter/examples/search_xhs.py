# -*- coding: utf-8 -*-
"""
Example: Basic Keyword Search on Xiaohongshu.

This script demonstrates how to configure and run the crawler to search for specific keywords on Xiaohongshu.
"""

import asyncio
import sys
import os

# Ensure the project root is in PYTHONPATH so we can import media_adapter
# Assuming this file is in src/media_adapter/examples/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from media_adapter import config, CrawlerFactory

async def main():
    # 1. Configure the Crawler
    # Set the target platform to Xiaohongshu ("xhs")
    config.PLATFORM = "xhs"
    
    # Set the crawler type to "search" (keyword search)
    config.CRAWLER_TYPE = "search"
    
    # Set the keywords to search for, separated by commas
    config.KEYWORDS = "Python爬虫,AI编程"
    
    # Configure data saving. Here we use "json" for simplicity.
    config.SAVE_DATA_OPTION = "json"
    
    # Optional: Configure headless mode (False to see the browser)
    config.HEADLESS = False  # Set to True for headless mode
    
    # Optional: Set maximum number of notes to crawl
    config.CRAWLER_MAX_NOTES_COUNT = 5

    print(f"Starting crawler for platform: {config.PLATFORM} with keywords: {config.KEYWORDS}")

    # 2. Create the Crawler instance
    crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
    
    # 3. Start the Crawler
    try:
        await crawler.start()
        print("Crawling finished successfully.")
    except Exception as e:
        print(f"An error occurred during crawling: {e}")
    finally:
        # Ensure resources are cleaned up if necessary (though crawler.start() usually handles its own lifecycle)
        # Some crawler implementations might need explicit close, but specific implementation details vary.
        if hasattr(crawler, "close"):
            await crawler.close()

if __name__ == "__main__":
    asyncio.run(main())
