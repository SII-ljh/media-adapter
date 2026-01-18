# -*- coding: utf-8 -*-
"""
Base Signal Source Interface

Defines the abstract interface for all media platform adapters.
Each adapter must implement both Trigger mode and Reference Tools mode.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from pydantic import BaseModel, Field


class SignalEventType(str, Enum):
    """Signal event types for trigger mode."""
    KEYWORD_SPIKE = "keyword_spike"           # Keyword mention spike
    SENTIMENT_SHIFT = "sentiment_shift"       # Sentiment change detected
    TRENDING_TOPIC = "trending_topic"         # New trending topic
    INFLUENCER_POST = "influencer_post"       # Key influencer posted
    VIRAL_CONTENT = "viral_content"           # Content going viral
    ANOMALY_DETECTED = "anomaly_detected"     # General anomaly
    NEW_CONTENT = "new_content"               # New content matching criteria


class SignalSeverity(str, Enum):
    """Severity levels for signal events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalEvent(BaseModel):
    """
    Represents a signal event detected by the trigger mode.

    Attributes:
        event_id: Unique identifier for this event
        event_type: Type of the signal event
        severity: Severity level of the event
        platform: Source platform (xhs, douyin, etc.)
        timestamp: When the event was detected
        title: Brief title/summary of the event
        description: Detailed description
        data: Raw data associated with the event
        metadata: Additional metadata
    """
    event_id: str = Field(..., description="Unique event identifier")
    event_type: SignalEventType = Field(..., description="Type of signal event")
    severity: SignalSeverity = Field(default=SignalSeverity.MEDIUM, description="Event severity")
    platform: str = Field(..., description="Source platform")
    timestamp: datetime = Field(default_factory=datetime.now, description="Detection timestamp")
    title: str = Field(..., description="Event title")
    description: str = Field(default="", description="Event description")
    keywords: List[str] = Field(default_factory=list, description="Related keywords")
    data: Dict[str, Any] = Field(default_factory=dict, description="Raw event data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        use_enum_values = True


class ToolResult(BaseModel):
    """
    Structured result from a reference tool.

    Attributes:
        success: Whether the tool execution was successful
        data: The structured data returned
        error: Error message if failed
        metadata: Additional metadata about the result
    """
    success: bool = Field(default=True, description="Execution success status")
    data: Any = Field(default=None, description="Result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")


@dataclass
class AdapterTool:
    """
    Represents a tool that can be called by an Agent.

    Attributes:
        name: Tool name (used for invocation)
        description: Description of what the tool does
        func: The callable function
        args_schema: Pydantic model for argument validation
    """
    name: str
    description: str
    func: Callable
    args_schema: Optional[type] = None

    def to_langchain_tool(self):
        """Convert to LangChain Tool format."""
        try:
            from langchain.tools import StructuredTool
            return StructuredTool.from_function(
                func=self.func,
                name=self.name,
                description=self.description,
                args_schema=self.args_schema,
            )
        except ImportError:
            # Return a simple dict representation if langchain not available
            return {
                "name": self.name,
                "description": self.description,
                "func": self.func,
            }


class BaseSignalSource(ABC):
    """
    Abstract base class for all media platform signal source adapters.

    Each adapter must implement:
    1. Trigger Mode: check_trigger() - Detects anomalies and generates SignalEvents
    2. Reference Mode: get_tools() - Provides tools for Agent to call

    Attributes:
        platform: Platform identifier (xhs, douyin, etc.)
        name: Human-readable name
        description: Description of the adapter
    """

    def __init__(self, platform: str, name: str, description: str = ""):
        self.platform = platform
        self.name = name
        self.description = description
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the adapter (e.g., login, setup browser).

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def check_trigger(
        self,
        keywords: List[str],
        **kwargs
    ) -> List[SignalEvent]:
        """
        Trigger Mode: Check for anomalies and generate signal events.

        Args:
            keywords: Keywords to monitor
            **kwargs: Additional platform-specific parameters

        Returns:
            List of SignalEvent objects if anomalies detected, empty list otherwise
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[AdapterTool]:
        """
        Reference Mode: Get list of tools available for Agent invocation.

        Returns:
            List of AdapterTool objects
        """
        pass

    def get_langchain_tools(self) -> List:
        """
        Get tools in LangChain compatible format.

        Returns:
            List of LangChain Tool objects
        """
        return [tool.to_langchain_tool() for tool in self.get_tools()]

    async def cleanup(self) -> None:
        """
        Cleanup resources (e.g., close browser, connections).
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(platform={self.platform}, name={self.name})>"
