# Xiaohongshu (Little Red Book) Signal Adapter

Signal source adapter for Xiaohongshu platform, implementing the `BaseSignalSource` interface.

## Features

- **Trigger Mode**: Monitor keywords for anomalies (placeholder, to be implemented)
- **Reference Mode**: Provides tools for Agent invocation

## Available Tools

| Tool Name | Description |
|-----------|-------------|
| `xhs_search_notes` | Search notes by keywords |
| `xhs_get_note_detail` | Get detailed information about a specific note |
| `xhs_get_note_comments` | Get comments for a note |
| `xhs_get_creator_info` | Get creator/influencer information |

## Usage

### Basic Usage

```python
import asyncio
from media_adapter.adapters.xhs import XhsSignalAdapter

async def main():
    # Initialize adapter
    adapter = XhsSignalAdapter(headless=True)
    await adapter.initialize()

    # Search notes
    result = await adapter.search_notes(
        keywords="Python教程,编程学习",
        limit=20
    )

    if result.success:
        for note in result.data:
            print(f"Title: {note['title']}")
            print(f"Author: {note['author']}")
            print(f"Likes: {note['liked_count']}")
            print("---")

    # Cleanup
    await adapter.cleanup()

asyncio.run(main())
```

### With LangChain Agent

```python
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from media_adapter.adapters.xhs import XhsSignalAdapter

async def main():
    adapter = XhsSignalAdapter()
    await adapter.initialize()

    # Get LangChain compatible tools
    tools = adapter.get_langchain_tools()

    # Create agent
    llm = ChatOpenAI(temperature=0)
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

    # Run agent
    response = agent.run("Search for popular Python tutorials on Xiaohongshu")
    print(response)

asyncio.run(main())
```

### Trigger Mode (Placeholder)

```python
async def monitor():
    adapter = XhsSignalAdapter()
    await adapter.initialize()

    # Check for anomalies
    events = await adapter.check_trigger(
        keywords=["热门话题", "trending"],
        threshold=100
    )

    for event in events:
        print(f"Event: {event.title}")
        print(f"Severity: {event.severity}")
        print(f"Type: {event.event_type}")
```

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `headless` | bool | True | Run browser in headless mode |

## Tool Schemas

### xhs_search_notes

```python
{
    "keywords": str,      # Required: Search keywords (comma separated)
    "limit": int,         # Optional: Max results (1-100, default: 20)
    "sort_by": str        # Optional: Sort method (general/hot/time)
}
```

### xhs_get_note_detail

```python
{
    "note_id": str        # Required: Note ID or full URL
}
```

### xhs_get_note_comments

```python
{
    "note_id": str,       # Required: Note ID or full URL
    "limit": int          # Optional: Max comments (1-200, default: 50)
}
```

### xhs_get_creator_info

```python
{
    "creator_id": str     # Required: Creator ID or profile URL
}
```

## Return Format

All tools return `ToolResult`:

```python
{
    "success": bool,      # Whether execution was successful
    "data": Any,          # Result data
    "error": str | None,  # Error message if failed
    "metadata": dict      # Additional metadata
}
```
