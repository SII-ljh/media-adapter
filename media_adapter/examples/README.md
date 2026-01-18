# MediaCrawler Examples

This directory contains example scripts demonstrating how to use the `media_adapter` package to crawl various social media platforms.

## Prerequisites

Ensure you have the dependencies installed:
```bash
pip install -r requirements.txt
```
(Run this from the project root `MediaCrawler/`)

## Running the Examples

You can run these examples directly from this directory, or from the project root.

### 1. Basic Keyword Search (Xiaohongshu)
Searches for keywords on Xiaohongshu and saves results to JSON.
```bash
python src/media_adapter/examples/search_xhs.py
```

### 2. Detail Page Crawl (Xiaohongshu)
Crawls specific note URLs (requires `xsec_token`).
```bash
python src/media_adapter/examples/detail_xhs.py
```

### 3. Multi-Platform Crawl
Iterates through multiple platforms.
```bash
python src/media_adapter/examples/multi_platform_search.py
```

## Configuration

The examples modify `media_adapter.config` global variables to configure behavior:
- `PLATFORM`: Target platform (xhs, dy, bili, etc.)
- `KEYWORDS`: Search terms
- `CRAWLER_TYPE`: "search" or "detail"
- `SAVE_DATA_OPTION`: Output format (json, csv, db, etc.)
- `HEADLESS`: Run browser in background (True) or visible (False)

## Notes
- Some platforms may require login. The crawler handles this by detecting if login is needed and prompting (e.g., QR code).
- `ENABLE_CDP_MODE` in `base_config.py` defaults to True, which tries to use your local Chrome browser to avoid detection.
