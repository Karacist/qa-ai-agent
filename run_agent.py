import asyncio
import sys

from agents.crawler_agent import crawl_website
from agents.executor_agent import execute_tests
from agents.regression_manager import compare_with_previous, save_run
from agents.test_generator_agent import generate_test_cases

# Ensure stdout handles unicode on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def progress(phase: str, message: str, _data=None) -> None:
    icons = {"crawl": "[crawl]", "generate": "[gen]", "execute": "[run]", "test_result": "  "}
    print(f"{icons.get(phase, '[?]')} {message}")


def main() -> None:
    url = input("Enter a starting URL to crawl: ").strip()
    if not url:
        print("No URL provided. Exiting.")
        return

    max_pages = input("Max pages [10]: ").strip()
    max_pages = int(max_pages) if max_pages.isdigit() else 10

    print("\n-- Phase 1: Crawl --")
    pages = asyncio.run(crawl_website(url, max_pages=max_pages, progress_cb=progress))
    print(f"   Crawled {len(pages)} page(s)")

    if not pages:
        print("No pages crawled. Exiting.")
        return

    print("\n-- Phase 2: Generate Tests --")
    test_cases = generate_test_cases(pages, progress_cb=progress)
    print(f"   Generated {len(test_cases)} test case(s)")

    print("\n-- Phase 3: Execute Tests --")
    results = execute_tests(browsers=["chromium"], run_mobile=True, progress_cb=progress, url=url)

    print("\n-- Phase 4: Regression Check --")
    save_run(results, url)
    regression = compare_with_previous(results, url)

    passed = sum(1 for r in results if r.get("status") == "pass")
    failed = len(results) - passed

    print(f"\n{'─' * 48}")
    print(f"  Total: {len(results)}  |  Passed: {passed}  |  Failed: {failed}")
    if not regression.get("is_first_run"):
        if regression["new_failures"]:
            print(f"  NEW FAILURES: {regression['new_failures']}")
        if regression["fixed"]:
            print(f"  FIXED: {regression['fixed']}")
    print(f"  Reports saved to: reports/")
    print(f"{'─' * 48}")


if __name__ == "__main__":
    main()
