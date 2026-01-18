# -*- coding: utf-8 -*-
"""
Deep Test Script for Media Adapter

Tests Xiaohongshu and Weibo platforms with:
1. Keyword search
2. Creator/Blogger profile
3. Post/Note details
4. Cookie-based login (no QR code needed!)

Usage:
    # First, create cookie files in ./cookies/ directory:
    # - cookies/xhs_cookies.txt (for Xiaohongshu)
    # - cookies/weibo_cookies.txt (for Weibo)

    # Test Xiaohongshu
    python -m media_adapter.deep_test --platform xhs

    # Test Weibo
    python -m media_adapter.deep_test --platform weibo

    # Test all platforms
    python -m media_adapter.deep_test --platform all

    # Custom cookies and output directories
    python -m media_adapter.deep_test --platform xhs --cookies ./my_cookies --output ./my_output

    # Run in headless mode
    python -m media_adapter.deep_test --platform xhs --headless
"""

import asyncio
import argparse
import json
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class TestResult:
    """Test result data class"""
    platform: str
    test_type: str
    success: bool
    total_items: int
    duration_seconds: float
    error: Optional[str] = None
    sample_data: Optional[Dict] = None
    saved_path: Optional[str] = None


@dataclass
class PlatformTestReport:
    """Platform test report"""
    platform: str
    timestamp: str
    search_test: Optional[TestResult] = None
    creator_test: Optional[TestResult] = None
    detail_test: Optional[TestResult] = None
    total_items_crawled: int = 0
    total_errors: int = 0
    recommendations: List[str] = field(default_factory=list)


class DeepTester:
    """Deep tester for media platforms"""

    # Platform-specific field mappings
    FIELD_MAPPINGS = {
        "xhs": {
            "id": "note_id",
            "title": "title",
            "content": "desc",
            "author": "author",
            "author_id": "author_id",
            "likes": "liked_count",
            "comments": "comment_count",
            "shares": "collected_count",
        },
        "weibo": {
            "id": "weibo_id",
            "title": "title",
            "content": "content",
            "author": "author",
            "author_id": "author_id",
            "likes": "liked_count",
            "comments": "comments_count",
            "shares": "reposts_count",
        },
        "douyin": {
            "id": "video_id",
            "title": "title",
            "content": "title",  # Douyin uses title as content
            "author": "author",
            "author_id": "author_id",
            "likes": "digg_count",
            "comments": "comment_count",
            "shares": "share_count",
            "plays": "play_count",
        },
    }

    def __init__(
        self,
        platform: str,
        headless: bool = False,
        cookies_dir: str = "./cookies",
        output_dir: str = "./output",
    ):
        self.platform = platform
        self.headless = headless
        self.cookies_dir = cookies_dir
        self.output_dir = output_dir
        self.adapter = None
        self.report = PlatformTestReport(
            platform=platform,
            timestamp=datetime.now().isoformat()
        )

    async def initialize(self):
        """Initialize adapter"""
        print(f"\n{'='*60}")
        print(f"Initializing {self.platform.upper()} Adapter")
        print(f"Cookies dir: {self.cookies_dir}")
        print(f"Output dir: {self.output_dir}")
        print(f"{'='*60}")

        from media_adapter.adapters import create_adapter

        self.adapter = create_adapter(
            self.platform,
            headless=self.headless,
            cookies_dir=self.cookies_dir,
            output_dir=self.output_dir,
        )
        await self.adapter.initialize()
        print(f"[{self.platform}] Adapter initialized")

    async def test_search(self, keywords: List[str], limit: int = 100) -> TestResult:
        """Test keyword search"""
        print(f"\n--- Testing Search ---")
        print(f"Keywords: {keywords}")
        print(f"Limit: {limit}")

        start_time = time.time()
        all_results = []
        errors = []
        saved_path = None

        try:
            for keyword in keywords:
                print(f"  Searching: {keyword}")

                result = await self.adapter.search_notes(
                    keywords=keyword,
                    limit=limit // len(keywords),
                    save_results=True,  # Save results to file
                )

                if result.success:
                    print(f"    Found {len(result.data)} items")
                    all_results.extend(result.data)
                    if result.metadata.get("saved_path"):
                        saved_path = result.metadata["saved_path"]
                        print(f"    Saved to: {saved_path}")
                else:
                    errors.append(f"Search '{keyword}': {result.error}")
                    print(f"    Error: {result.error}")

                await asyncio.sleep(2)

        except Exception as e:
            errors.append(str(e))
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()

        duration = time.time() - start_time

        result = TestResult(
            platform=self.platform,
            test_type="search",
            success=len(all_results) > 0,
            total_items=len(all_results),
            duration_seconds=duration,
            error="; ".join(errors) if errors else None,
            sample_data=all_results[0] if all_results else None,
            saved_path=saved_path,
        )

        self.report.search_test = result
        self.report.total_items_crawled += len(all_results)

        print(f"\n  Search Result: {len(all_results)} items in {duration:.1f}s")

        return result

    async def test_creator(self, creator_id: str) -> TestResult:
        """Test creator/blogger profile fetch"""
        print(f"\n--- Testing Creator Profile ---")
        print(f"Creator ID: {creator_id}")

        start_time = time.time()

        try:
            result = await self.adapter.get_creator_info(creator_id)
            duration = time.time() - start_time

            if result.success:
                nickname = result.data.get('nickname', result.data.get('screen_name', 'N/A'))
                print(f"  Creator found: {nickname}")
                return TestResult(
                    platform=self.platform,
                    test_type="creator",
                    success=True,
                    total_items=1,
                    duration_seconds=duration,
                    sample_data=result.data,
                )
            else:
                print(f"  Error: {result.error}")
                return TestResult(
                    platform=self.platform,
                    test_type="creator",
                    success=False,
                    total_items=0,
                    duration_seconds=duration,
                    error=result.error,
                )

        except Exception as e:
            duration = time.time() - start_time
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()
            return TestResult(
                platform=self.platform,
                test_type="creator",
                success=False,
                total_items=0,
                duration_seconds=duration,
                error=str(e),
            )

    async def test_detail(self, item_id: str, xsec_token: str = "") -> TestResult:
        """Test post/note detail fetch"""
        print(f"\n--- Testing Post Detail ---")
        print(f"Item ID: {item_id}")

        start_time = time.time()

        try:
            if self.platform == "xhs":
                result = await self.adapter.get_note_detail(item_id, xsec_token=xsec_token)
            elif self.platform == "weibo":
                result = await self.adapter.get_weibo_detail(item_id)
            elif self.platform == "douyin":
                result = await self.adapter.get_video_detail(item_id)
            else:
                raise ValueError(f"Unknown platform: {self.platform}")

            duration = time.time() - start_time

            if result.success:
                print(f"  Detail fetched successfully")
                return TestResult(
                    platform=self.platform,
                    test_type="detail",
                    success=True,
                    total_items=1,
                    duration_seconds=duration,
                    sample_data=result.data,
                )
            else:
                print(f"  Error: {result.error}")
                return TestResult(
                    platform=self.platform,
                    test_type="detail",
                    success=False,
                    total_items=0,
                    duration_seconds=duration,
                    error=result.error,
                )

        except Exception as e:
            duration = time.time() - start_time
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()
            return TestResult(
                platform=self.platform,
                test_type="detail",
                success=False,
                total_items=0,
                duration_seconds=duration,
                error=str(e),
            )

    def generate_report(self) -> Dict:
        """Generate comprehensive test report"""
        total_success = sum([
            1 for t in [self.report.search_test, self.report.creator_test, self.report.detail_test]
            if t and t.success
        ])

        recommendations = []
        if not self.report.search_test or not self.report.search_test.success:
            recommendations.append("Check if cookies are valid and not expired")

        self.report.recommendations = recommendations

        report = {
            "platform": self.platform,
            "timestamp": self.report.timestamp,
            "summary": {
                "total_tests": 3,
                "passed_tests": total_success,
                "total_items_crawled": self.report.total_items_crawled,
            },
            "field_mapping": self.FIELD_MAPPINGS.get(self.platform, {}),
            "tests": {},
            "recommendations": recommendations,
        }

        if self.report.search_test:
            report["tests"]["search"] = asdict(self.report.search_test)
        if self.report.creator_test:
            report["tests"]["creator"] = asdict(self.report.creator_test)
        if self.report.detail_test:
            report["tests"]["detail"] = asdict(self.report.detail_test)

        return report

    async def cleanup(self):
        """Cleanup adapter resources"""
        if self.adapter:
            await self.adapter.cleanup()


# Test configurations for each platform
TEST_CONFIGS = {
    "xhs": {
        "search_keywords": ["Python教程", "编程学习"],
        "creator_id": "5a23a47fe8ac2b0dd877ecbb",
        "detail_id": "",  # Will be filled from search results
    },
    "weibo": {
        "search_keywords": ["Python编程", "人工智能"],
        "creator_id": "1642634100",
        "detail_id": "",  # Will be filled from search results
    },
    "douyin": {
        "search_keywords": ["Python教程", "编程"],
        "creator_id": "",  # Will be filled from search results
        "detail_id": "",  # Will be filled from search results
    },
}


def ensure_cookies_dir(cookies_dir: str):
    """Ensure cookies directory exists with template files."""
    from media_adapter.utils.cookie_manager import CookieManager

    manager = CookieManager(cookies_dir)
    manager.ensure_cookies_dir()

    # Create template files if they don't exist
    for platform in ["xhs", "weibo", "douyin"]:
        manager.create_template(platform)

    print(f"Cookies directory: {cookies_dir}")
    print("Please ensure you have valid cookies in the following files:")
    print(f"  - {cookies_dir}/xhs_cookies.txt (for Xiaohongshu)")
    print(f"  - {cookies_dir}/weibo_cookies.txt (for Weibo)")
    print(f"  - {cookies_dir}/douyin_cookies.txt (for Douyin)")


async def run_platform_test(
    platform: str,
    headless: bool = False,
    cookies_dir: str = "./cookies",
    output_dir: str = "./output",
) -> Dict:
    """Run complete test suite for a platform"""

    print(f"\n{'#'*60}")
    print(f"# DEEP TEST: {platform.upper()}")
    print(f"{'#'*60}")

    tester = DeepTester(
        platform,
        headless=headless,
        cookies_dir=cookies_dir,
        output_dir=output_dir,
    )
    config_data = TEST_CONFIGS.get(platform, {})

    try:
        await tester.initialize()

        # Test 1: Search
        search_result = await tester.test_search(
            keywords=config_data.get("search_keywords", ["test"]),
            limit=100
        )

        # Get item ID and creator_id from search results
        detail_id = config_data.get("detail_id")
        xsec_token = ""
        creator_id = config_data.get("creator_id", "")

        if search_result.sample_data:
            # Get note/post/video ID for detail test
            detail_id = (
                search_result.sample_data.get("note_id") or
                search_result.sample_data.get("weibo_id") or
                search_result.sample_data.get("video_id") or
                detail_id
            )
            xsec_token = search_result.sample_data.get("xsec_token", "")

            # Get author_id for creator test
            search_creator_id = search_result.sample_data.get("author_id", "")
            if search_creator_id:
                creator_id = search_creator_id
                print(f"  Using author_id from search result: {creator_id}")

        # Test 2: Creator profile
        if creator_id:
            creator_result = await tester.test_creator(creator_id=creator_id)
            tester.report.creator_test = creator_result

        # Test 3: Post detail
        if detail_id:
            detail_result = await tester.test_detail(detail_id, xsec_token=xsec_token)
            tester.report.detail_test = detail_result

        # Generate report
        report = tester.generate_report()

        # Print summary
        print(f"\n{'='*60}")
        print(f"TEST REPORT: {platform.upper()}")
        print(f"{'='*60}")
        print(f"Total items crawled: {report['summary']['total_items_crawled']}")
        print(f"Tests passed: {report['summary']['passed_tests']}/{report['summary']['total_tests']}")

        print(f"\nField Mapping for {platform.upper()}:")
        for std_field, platform_field in report['field_mapping'].items():
            print(f"  {std_field:15} -> {platform_field}")

        if report['recommendations']:
            print(f"\nRecommendations:")
            for rec in report['recommendations']:
                print(f"  - {rec}")

        return report

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return {"platform": platform, "error": str(e)}

    finally:
        await tester.cleanup()


async def main():
    parser = argparse.ArgumentParser(
        description="Deep test media adapters with cookie-based authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test Xiaohongshu
  python -m media_adapter.deep_test --platform xhs

  # Test Weibo
  python -m media_adapter.deep_test --platform weibo

  # Test Douyin
  python -m media_adapter.deep_test --platform douyin

  # Test all platforms
  python -m media_adapter.deep_test --platform all

  # Use custom directories
  python -m media_adapter.deep_test --platform xhs --cookies ./my_cookies --output ./my_output

Before running:
  1. Create cookies directory: mkdir -p cookies
  2. Add your cookies to: cookies/xhs_cookies.txt, cookies/weibo_cookies.txt, or cookies/douyin_cookies.txt
  3. Cookie format: key1=value1; key2=value2; ...
  4. If no cookies, run without --headless to use QR code login
"""
    )
    parser.add_argument(
        "--platform",
        choices=["xhs", "weibo", "douyin", "all"],
        default="xhs",
        help="Platform to test (default: xhs)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--cookies",
        default="./cookies",
        help="Directory containing cookie files (default: ./cookies)"
    )
    parser.add_argument(
        "--output",
        default="./output",
        help="Directory to save output files (default: ./output)"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize cookies directory with template files"
    )

    args = parser.parse_args()

    # Initialize cookies directory if requested
    if args.init:
        ensure_cookies_dir(args.cookies)
        return

    # Ensure cookies directory exists
    Path(args.cookies).mkdir(parents=True, exist_ok=True)
    Path(args.output).mkdir(parents=True, exist_ok=True)

    all_reports = {}

    if args.platform == "all":
        platforms = ["xhs", "weibo", "douyin"]
    else:
        platforms = [args.platform]

    for platform in platforms:
        report = await run_platform_test(
            platform,
            headless=args.headless,
            cookies_dir=args.cookies,
            output_dir=args.output,
        )
        all_reports[platform] = report

    # Save reports to output directory
    report_file = Path(args.output) / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(all_reports, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nReports saved to: {report_file}")

    # Print final summary
    print(f"\n{'#'*60}")
    print("# FINAL SUMMARY")
    print(f"{'#'*60}")

    for platform, report in all_reports.items():
        if "error" in report:
            print(f"\n{platform.upper()}: FAILED - {report['error']}")
        else:
            summary = report.get("summary", {})
            print(f"\n{platform.upper()}:")
            print(f"  Items crawled: {summary.get('total_items_crawled', 0)}")
            print(f"  Tests passed: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)}")


def run():
    """Entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
