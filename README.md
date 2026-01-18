# Media Adapter

A multi-platform social media data crawler with LLM integration capabilities.

## Supported Platforms

| Platform | Code | Description |
|----------|------|-------------|
| Xiaohongshu | `xhs` | Little Red Book |
| Douyin | `dy` | Chinese TikTok |
| Kuaishou | `ks` | Kuaishou Video |
| Bilibili | `bili` | Bilibili Video |
| Weibo | `wb` | Sina Weibo |
| Tieba | `tieba` | Baidu Tieba |
| Zhihu | `zhihu` | Zhihu Q&A |

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/media-adapter.git
cd media-adapter

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .

# Install Playwright browsers
playwright install chromium
```

### Optional Dependencies

```bash
# Development tools
pip install -e ".[dev]"

# LangChain integration
pip install -e ".[langchain]"

# FastAPI support
pip install -e ".[api]"

# All dependencies
pip install -e ".[all]"
```

## Quick Start

### CLI Usage

```bash
# Search Xiaohongshu
media-adapter --platform xhs --keywords "python,编程"

# Search Douyin
media-adapter --platform dy --keywords "美食"

# Use cookie login
media-adapter --platform xhs --lt cookie --cookies "your_cookie_string"

# Save to different formats
media-adapter --platform xhs --keywords "travel" --save_data_option csv
media-adapter --platform xhs --keywords "travel" --save_data_option sqlite

# Run in headless mode
media-adapter --platform xhs --keywords "tech" --headless true

# Initialize database
media-adapter --init_db sqlite
```

### Python API

```python
import asyncio
from media_adapter import XiaoHongShuCrawler, config

# Configure
config.PLATFORM = "xhs"
config.CRAWLER_TYPE = "search"
config.KEYWORDS = "python,编程"
config.HEADLESS = True

# Run crawler
async def main():
    crawler = XiaoHongShuCrawler()
    await crawler.start()

asyncio.run(main())
```

### LLM Integration (Adapter)

```python
import asyncio
from media_adapter.adapters import create_adapter

async def main():
    # Create adapter
    adapter = create_adapter("xhs")
    await adapter.initialize()

    # Get available tools
    tools = adapter.get_tools()
    for tool in tools:
        print(f"Tool: {tool.name}")

    # Use with LangChain
    langchain_tools = adapter.get_langchain_tools()

asyncio.run(main())
```

## Configuration

Main configuration in `media_adapter/config/base_config.py`:

| Option | Default | Description |
|--------|---------|-------------|
| `PLATFORM` | `"xhs"` | Target platform |
| `CRAWLER_TYPE` | `"search"` | search / detail / creator |
| `HEADLESS` | `False` | Run browser headlessly |
| `SAVE_DATA_OPTION` | `"json"` | json / csv / sqlite / excel / db |
| `LOGIN_TYPE` | `"qrcode"` | qrcode / phone / cookie |

## Output

Default output directory: `./output/{platform}/{date}/{crawler_type}/`

Supported formats:
- JSON (default)
- CSV
- Excel
- SQLite
- MySQL
- PostgreSQL
- MongoDB

## Project Structure

```
media_adapter/
├── adapters/          # LLM integration adapters
├── platforms/         # Platform-specific crawlers
│   ├── xhs/          # Xiaohongshu
│   ├── douyin/       # Douyin
│   ├── kuaishou/     # Kuaishou
│   ├── bilibili/     # Bilibili
│   ├── weibo/        # Weibo
│   ├── tieba/        # Baidu Tieba
│   └── zhihu/        # Zhihu
├── config/           # Configuration files
├── core/             # Abstract base classes
├── database/         # Database models
├── storage/          # Output backends
├── utils/            # Utility functions
├── cli/              # CLI argument parsing
└── api/              # FastAPI REST interface
```

## Testing

```bash
# Run deep test
media-adapter-test --platform xhs

# Test all platforms
media-adapter-test --platform all

# Headless mode
media-adapter-test --platform xhs --headless
```

## License

This project is licensed under the NON-COMMERCIAL LEARNING LICENSE 1.1.

**Important**: This code is for learning and research purposes only. Users must:
1. Not use for commercial purposes
2. Comply with target platform's terms of service and robots.txt
3. Not perform large-scale crawling
4. Control request frequency reasonably
5. Not use for illegal purposes

## Disclaimer

This tool is intended for educational and research purposes. The developers are not responsible for any misuse or damage caused by this software. Always respect the terms of service of the platforms you interact with.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

Based on [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) by NanmiCoder.
