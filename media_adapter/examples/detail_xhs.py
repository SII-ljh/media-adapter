# -*- coding: utf-8 -*-
"""
Example: Detail Crawl on Xiaohongshu.

This script demonstrates how to crawl specific notes given their URLs (including xsec_token).
"""

import asyncio
import sys
import os

# Ensure the project root is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from media_adapter import config, CrawlerFactory

async def main():
    # 1. Configure for Detail Crawl
    config.PLATFORM = "xhs"
    config.CRAWLER_TYPE = "detail"
    
    # Note: XHS requires xsec_token in the URL for detail crawling.
    # You would typically populate this list with URLs you've gathered or know.
    # Example URL format (replace with valid ones):
    config.XHS_SPECIFIED_NOTE_URL_LIST = [
        "https://www.xiaohongshu.com/explore/64b95d01000000000c034587?xsec_token=AB0EFqJvINCkj6xOCKCQgfNNh8GdnBC_6XecG4QOddo3Q=&xsec_source=pc_cfeed"
    ]
    
    config.SAVE_DATA_OPTION = "json"
    config.HEADLESS = False

    print(f"Starting detail crawler for {len(config.XHS_SPECIFIED_NOTE_URL_LIST)} specified notes.")

    # 2. Create and Start Crawler
    crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
    
    try:
        await crawler.start()
        print("Detail crawling finished.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
         if hasattr(crawler, "close"):
            await crawler.close()

if __name__ == "__main__":
    asyncio.run(main())
