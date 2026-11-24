import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from agents.html_processor import clean_html_for_llm, extract_page_structure


def _get_origin(url: str) -> str:
    sep = url.find("://")
    if sep == -1:
        return ""
    remainder = url[sep + 3:]
    slash = remainder.find("/")
    host = remainder if slash == -1 else remainder[:slash]
    return f"{url[:sep]}://{host}"


def _normalize_link(href, origin: str):
    if not href:
        return None
    href = href.strip()
    lower = href.lower()
    if any(lower.startswith(p) for p in ("javascript:", "mailto:", "#", "tel:", "data:")):
        return None
    if href.startswith("//"):
        scheme = origin.split("://")[0]
        return f"{scheme}:{href}"
    if href.startswith("/"):
        return origin + href
    if href.startswith(origin):
        return href
    return None


def _get_screenshots_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _extract_links(page, origin: str) -> list:
    try:
        hrefs = await page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.getAttribute('href'))"
        )
    except Exception:
        return []
    seen: set = set()
    links = []
    for h in hrefs:
        n = _normalize_link(h, origin)
        if n and n not in seen:
            seen.add(n)
            links.append(n)
    return links


async def _get_perf_metrics(page) -> dict:
    try:
        return await page.evaluate("""() => {
            const nav = performance.getEntriesByType('navigation')[0] || {};
            const paint = {};
            for (const e of performance.getEntriesByType('paint')) {
                paint[e.name] = Math.round(e.startTime);
            }
            return {
                dom_content_loaded: Math.round((nav.domContentLoadedEventEnd || 0) - (nav.fetchStart || 0)),
                load_time: Math.round((nav.loadEventEnd || 0) - (nav.fetchStart || 0)),
                first_paint: paint['first-paint'] || 0,
                first_contentful_paint: paint['first-contentful-paint'] || 0,
                transfer_size: Math.round((nav.transferSize || 0) / 1024),
            };
        }""")
    except Exception:
        return {}


async def crawl_website(start_url: str, max_pages: int = 10, progress_cb=None) -> list:
    origin = _get_origin(start_url)
    if not origin:
        raise ValueError("Invalid URL — include scheme (e.g. https://example.com).")

    screenshots_dir = _get_screenshots_dir()
    visited: set = set()
    to_visit = [start_url]
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        )
        page = await context.new_page()

        api_calls: list = []

        async def on_request(req):
            if req.resource_type in ("fetch", "xhr"):
                api_calls.append({"url": req.url[:200], "method": req.method})

        page.on("request", on_request)

        try:
            while to_visit and len(visited) < max_pages:
                url = to_visit.pop(0)
                if url in visited:
                    continue

                if progress_cb:
                    progress_cb("crawl", f"Crawling {url} ({len(visited) + 1}/{min(max_pages, len(visited) + len(to_visit) + 1)})")

                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                except Exception:
                    visited.add(url)
                    continue

                visited.add(url)
                title = await page.title()
                html = await page.content()

                idx = len(results) + 1
                ss_path = screenshots_dir / f"page_{idx}.png"
                await page.screenshot(path=str(ss_path), full_page=True)

                # Mobile screenshot for key pages
                mobile_ss_path = screenshots_dir / f"page_{idx}_mobile.png"
                await page.set_viewport_size({"width": 375, "height": 812})
                await page.screenshot(path=str(mobile_ss_path))
                await page.set_viewport_size({"width": 1280, "height": 800})

                perf = await _get_perf_metrics(page)
                structure = extract_page_structure(html)
                cleaned_html = clean_html_for_llm(html)

                links = await _extract_links(page, origin)
                for link in links:
                    if link not in visited and link not in to_visit:
                        to_visit.append(link)

                page_api_calls = api_calls.copy()
                api_calls.clear()

                results.append({
                    "url": url,
                    "title": title,
                    "html": html,
                    "cleaned_html": cleaned_html,
                    "structure": structure,
                    "screenshot_path": str(ss_path),
                    "mobile_screenshot_path": str(mobile_ss_path),
                    "performance": perf,
                    "api_calls": page_api_calls,
                })

        finally:
            await context.close()
            await browser.close()

    return results


if __name__ == "__main__":
    asyncio.run(crawl_website("https://example.com", max_pages=3))
