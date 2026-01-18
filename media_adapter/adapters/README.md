# Media Adapter Signal Source Adapters

This module provides signal source adapters for various social media platforms, implementing the `BaseSignalSource` interface.

## Supported Platforms

| Platform | Adapter Class | Tools Count |
|----------|---------------|-------------|
| Xiaohongshu (小红书) | `XhsSignalAdapter` | 4 |
| Douyin (抖音) | `DouyinSignalAdapter` | 4 |
| Kuaishou (快手) | `KuaishouSignalAdapter` | 4 |
| Bilibili (B站) | `BilibiliSignalAdapter` | 4 |
| Weibo (微博) | `WeiboSignalAdapter` | 4 |
| Tieba (贴吧) | `TiebaSignalAdapter` | 4 |
| Zhihu (知乎) | `ZhihuSignalAdapter` | 5 |

## Architecture

```
BaseSignalSource (Abstract Base Class)
├── check_trigger() -> List[SignalEvent]  # Trigger Mode
└── get_tools() -> List[AdapterTool]      # Reference Mode

SignalEvent
├── event_id: str
├── event_type: SignalEventType
├── severity: SignalSeverity
├── platform: str
├── title: str
├── description: str
├── keywords: List[str]
├── data: Dict
└── metadata: Dict

AdapterTool
├── name: str
├── description: str
├── func: Callable
└── args_schema: Optional[BaseModel]
```

## Quick Start

### Using Factory Function

```python
from media_adapter.adapters import create_adapter

# Create adapter for any supported platform
adapter = create_adapter("xhs")  # or "douyin", "bilibili", etc.
await adapter.initialize()

# Search content
result = await adapter.search_notes(keywords="Python教程", limit=10)
print(result.data)

# Cleanup
await adapter.cleanup()
```

### Direct Import

```python
from media_adapter.adapters.xhs import XhsSignalAdapter
from media_adapter.adapters.douyin import DouyinSignalAdapter

# Use specific adapter
xhs = XhsSignalAdapter(headless=True)
await xhs.initialize()
```

## Modes

### Trigger Mode

Monitor for anomalies and generate signal events:

```python
events = await adapter.check_trigger(
    keywords=["热门话题", "trending"],
    threshold=100
)

for event in events:
    print(f"Event: {event.title}")
    print(f"Type: {event.event_type}")
    print(f"Severity: {event.severity}")
```

**Note:** Trigger mode is currently a placeholder. Implement your own monitoring logic.

### Reference Mode

Get tools for Agent invocation:

```python
# Get tools list
tools = adapter.get_tools()
for tool in tools:
    print(f"{tool.name}: {tool.description}")

# Call tool directly
result = await tools[0].func(keywords="Python", limit=20)

# Or get LangChain compatible tools
langchain_tools = adapter.get_langchain_tools()
```

## Tool Reference

### Common Tools (All Platforms)

| Tool Pattern | Description |
|--------------|-------------|
| `{platform}_search_*` | Search content by keywords |
| `{platform}_get_*_detail` | Get detailed information |
| `{platform}_get_*_comments` | Get comments/replies |
| `{platform}_get_*_info` | Get user/creator information |

### Platform-Specific Tools

#### Xiaohongshu (xhs)
- `xhs_search_notes` - Search notes
- `xhs_get_note_detail` - Get note details
- `xhs_get_note_comments` - Get note comments
- `xhs_get_creator_info` - Get creator info

#### Douyin (douyin)
- `douyin_search_videos` - Search videos
- `douyin_get_video_detail` - Get video details
- `douyin_get_video_comments` - Get video comments
- `douyin_get_creator_info` - Get creator info

#### Bilibili (bilibili)
- `bilibili_search_videos` - Search videos
- `bilibili_get_video_detail` - Get video details
- `bilibili_get_video_comments` - Get video comments
- `bilibili_get_up_info` - Get UP主 info

#### Zhihu (zhihu)
- `zhihu_search_content` - Search questions/answers/articles
- `zhihu_get_question_detail` - Get question details
- `zhihu_get_answer_detail` - Get answer details
- `zhihu_get_answer_comments` - Get answer comments
- `zhihu_get_user_info` - Get user info

## LangChain Integration

```python
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from media_adapter.adapters import create_adapter

async def main():
    # Create adapter
    adapter = create_adapter("xhs")
    await adapter.initialize()

    # Get LangChain tools
    tools = adapter.get_langchain_tools()

    # Create agent
    llm = ChatOpenAI(temperature=0)
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

    # Run
    response = agent.run("搜索小红书上关于Python编程的热门笔记")
    print(response)

    await adapter.cleanup()
```

## Return Format

All tools return `ToolResult`:

```python
class ToolResult:
    success: bool        # Execution success
    data: Any           # Result data (list/dict)
    error: Optional[str] # Error message if failed
    metadata: Dict      # Additional info (platform, count, etc.)
```

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `headless` | bool | True | Run browser in headless mode |

## Running Tests

```bash
# Run adapter tests
pytest tests/test_adapters.py -v

# Run with coverage
pytest tests/test_adapters.py --cov=media_adapter.adapters
```

## Adding New Platform

1. Create directory: `adapters/newplatform/`
2. Implement adapter inheriting `BaseSignalSource`
3. Register in `adapters/__init__.py`
4. Add unit tests
5. Update documentation

```python
class NewPlatformSignalAdapter(BaseSignalSource):
    def __init__(self, headless: bool = True):
        super().__init__(
            platform="newplatform",
            name="New Platform Adapter",
            description="..."
        )

    async def initialize(self) -> bool:
        # Setup code
        pass

    async def check_trigger(self, keywords, **kwargs) -> List[SignalEvent]:
        # Trigger logic
        pass

    def get_tools(self) -> List[AdapterTool]:
        # Return available tools
        pass
```
