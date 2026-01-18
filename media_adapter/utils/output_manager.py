# -*- coding: utf-8 -*-
"""
Output Manager for Media Adapter

Manages output paths and saves crawl results to specified directories.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class OutputManager:
    """
    Output manager for saving crawl results.

    Supports:
    - JSON output
    - CSV output (TODO)
    - Automatic directory creation
    - Platform and date-based organization

    Usage:
        manager = OutputManager("./output", platform="xhs")

        # Save search results
        manager.save_json(results, "search_results")

        # Save with custom filename
        manager.save_json(results, "search_python", suffix="notes")
    """

    def __init__(
        self,
        output_dir: str = "./output",
        platform: str = "",
        by_platform: bool = True,
        by_date: bool = True,
    ):
        """
        Initialize output manager.

        Args:
            output_dir: Base output directory
            platform: Platform identifier (xhs, weibo, etc.)
            by_platform: Organize by platform subdirectory
            by_date: Organize by date subdirectory
        """
        self.base_dir = Path(output_dir)
        self.platform = platform
        self.by_platform = by_platform
        self.by_date = by_date

    def _get_output_dir(self) -> Path:
        """Get the full output directory path."""
        output_path = self.base_dir

        if self.by_platform and self.platform:
            output_path = output_path / self.platform

        if self.by_date:
            date_str = datetime.now().strftime("%Y%m%d")
            output_path = output_path / date_str

        return output_path

    def _ensure_dir(self, path: Path):
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)

    def _generate_filename(
        self,
        name: str,
        suffix: str = "",
        extension: str = "json",
        include_timestamp: bool = True
    ) -> str:
        """Generate filename with optional timestamp."""
        parts = [name]

        if suffix:
            parts.append(suffix)

        if include_timestamp:
            timestamp = datetime.now().strftime("%H%M%S")
            parts.append(timestamp)

        return f"{'_'.join(parts)}.{extension}"

    def save_json(
        self,
        data: Union[Dict, List],
        name: str,
        suffix: str = "",
        include_timestamp: bool = True,
        indent: int = 2,
    ) -> str:
        """
        Save data as JSON file.

        Args:
            data: Data to save (dict or list)
            name: Base filename (without extension)
            suffix: Optional suffix for filename
            include_timestamp: Include timestamp in filename
            indent: JSON indentation

        Returns:
            Full path to saved file
        """
        output_dir = self._get_output_dir()
        self._ensure_dir(output_dir)

        filename = self._generate_filename(
            name, suffix, "json", include_timestamp
        )
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)

        return str(filepath)

    def save_text(
        self,
        content: str,
        name: str,
        suffix: str = "",
        extension: str = "txt",
        include_timestamp: bool = True,
    ) -> str:
        """
        Save content as text file.

        Args:
            content: Text content to save
            name: Base filename
            suffix: Optional suffix
            extension: File extension
            include_timestamp: Include timestamp in filename

        Returns:
            Full path to saved file
        """
        output_dir = self._get_output_dir()
        self._ensure_dir(output_dir)

        filename = self._generate_filename(
            name, suffix, extension, include_timestamp
        )
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return str(filepath)

    def get_output_path(self, filename: str) -> str:
        """Get full output path for a filename."""
        output_dir = self._get_output_dir()
        self._ensure_dir(output_dir)
        return str(output_dir / filename)

    def list_files(self, pattern: str = "*") -> List[str]:
        """List files in output directory matching pattern."""
        output_dir = self._get_output_dir()
        if not output_dir.exists():
            return []
        return [str(p) for p in output_dir.glob(pattern)]


def get_output_manager(
    platform: str = "",
    output_dir: Optional[str] = None,
    by_platform: Optional[bool] = None,
    by_date: Optional[bool] = None,
) -> OutputManager:
    """
    Create an output manager with config defaults.

    Args:
        platform: Platform identifier
        output_dir: Override output directory
        by_platform: Override platform organization
        by_date: Override date organization

    Returns:
        OutputManager instance
    """
    from media_adapter import config

    return OutputManager(
        output_dir=output_dir or getattr(config, "OUTPUT_DIR", "./output"),
        platform=platform,
        by_platform=by_platform if by_platform is not None else getattr(config, "OUTPUT_BY_PLATFORM", True),
        by_date=by_date if by_date is not None else getattr(config, "OUTPUT_BY_DATE", True),
    )


def save_crawl_results(
    data: Union[Dict, List],
    platform: str,
    result_type: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    Convenience function to save crawl results.

    Args:
        data: Data to save
        platform: Platform identifier
        result_type: Type of results (search, detail, creator, etc.)
        output_dir: Override output directory

    Returns:
        Path to saved file
    """
    manager = get_output_manager(platform=platform, output_dir=output_dir)
    return manager.save_json(data, result_type)
