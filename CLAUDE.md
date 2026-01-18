# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Install as package (recommended - works from any directory)
pip install -e .

# Or install dependencies only
pip install -r media_adapter/requirements.txt

# CLI commands (available after package install)
media-adapter --platform xhs --keywords "python"
media-adapter-test --platform xhs

# Run as module
python -m media_adapter --platform xhs --keywords "python"
python -m media_adapter.examples.deep_test --platform xhs

# Initialize database
media-adapter --init-db sqlite
media-adapter --init-db mysql
media-adapter --init-db postgres
```

## Architecture Overview

This is a multi-platform social media crawler with LLM integration capabilities. It crawls content from 7 Chinese social media platforms: Xiaohongshu (xhs), Douyin (dy), Kuaishou (ks), Bilibili (bili), Weibo (wb), Baidu Tieba (tieba), and Zhihu.

### Core Patterns

- **Factory Pattern**: `CrawlerFactory` in `app.py` creates platform-specific crawlers
- **Abstract Base Classes**: `AbstractCrawler`, `AbstractLogin`, `AbstractStore` in `core/base_crawler.py`
- **Adapter Pattern**: `BaseSignalSource` in `adapters/base.py` provides LLM tool integration
- **Context Variables**: `context.py` uses async context vars for state sharing across coroutines

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `adapters/` | LLM integration adapters implementing `BaseSignalSource` |
| `platforms/` | Platform-specific crawlers (core logic, client, login) |
| `config/` | Configuration (`base_config.py` for globals, `*_config.py` per platform) |
| `core/` | Abstract interfaces for crawlers, login, and storage |
| `database/` | SQLAlchemy models and DB session management |
| `storage/` | Output backends (JSON, CSV, Excel, MongoDB, SQL) |
| `api/` | FastAPI REST interface with WebUI |
| `utils/` | Browser automation, cookies, async file I/O |
| `cache/` | Caching layer (local, Redis) |
| `proxy/` | Proxy pool management (kuaidaili, wandouhttp) |
| `cli/` | Typer-based CLI argument parsing |

### Execution Flow

```
CLI (cli/arg.py) → app.py::main() → CrawlerFactory.create_crawler(platform)
    → Platform Crawler → Browser Launch (CDP/Playwright)
    → Login (QRCode/Phone/Cookie) → Search/Crawl → Store → Cleanup
```

### Adapter System (LLM Integration)

Adapters in `adapters/` implement two modes:
- **Trigger Mode**: `check_trigger()` monitors for anomalies, returns `SignalEvent` list
- **Reference Mode**: `get_tools()` returns callable tools for LLM agents

Each adapter provides tools like `search_notes`, `get_note_detail`, `get_comments`, `get_creator_info`.

LangChain integration:
```python
from media_adapter.adapters import create_adapter
adapter = create_adapter("xhs")
await adapter.initialize()
tools = adapter.get_langchain_tools()
```

### Browser Automation

- **CDP Mode (Default)**: Uses Chrome DevTools Protocol with real browser
- Key classes: `browser_launcher.py`, `cdp_browser.py`, `browser_session.py`, `cookie_manager.py`
- Supports proxy rotation, cookie persistence, slider verification bypass

### Configuration

Primary config in `config/base_config.py`:
```python
PLATFORM = "xhs"  # xhs, dy, ks, bili, wb, tieba, zhihu
CRAWLER_TYPE = "search"  # search, detail, creator
ENABLE_CDP_MODE = True
HEADLESS = False
SAVE_DATA_OPTION = "json"  # json, csv, db, sqlite, excel, postgres, mongodb
LOGIN_TYPE = "qrcode"  # qrcode, phone, cookie
```

### Output

Default output path: `./output/{platform}/{date}/{crawler_type}/`

Supported formats: JSON (default), CSV, Excel, SQLite, MySQL, PostgreSQL, MongoDB
