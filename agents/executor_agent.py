import asyncio
import base64
import json
from pathlib import Path

from playwright.async_api import async_playwright, Page
import backend.db_manager as db_manager


def _get_reports_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _to_web_path(path: Path) -> str:
    root = Path(__file__).resolve().parent.parent
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path).replace("\\", "/")


def _load_test_cases(url: str = None) -> list:
    data = db_manager.load_test_cases(url)
    if not data:
        raise FileNotFoundError("No generated test cases found in database or fallback storage.")
    return data


def _fallback_selectors(selector: str) -> list:
    """Generate alternative selectors for self-healing."""
    alts = [selector]
    lo = selector.lower()
    if "submit" in lo or "login" in lo or "signin" in lo:
        alts += ["button[type='submit']", "input[type='submit']", "button:has-text('Login')",
                 "button:has-text('Sign in')", "button:has-text('Submit')"]
    if "email" in lo:
        alts += ["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"]
    if "password" in lo:
        alts += ["input[type='password']", "input[name='password']"]
    if "button" in lo:
        alts += ["button:visible", "[role='button']:visible"]
    if "input" in lo:
        alts += ["input:visible", "input[type='text']:visible"]
    return alts


async def _try_action(action_fn, selectors: list) -> bool:
    for sel in selectors:
        try:
            await action_fn(sel)
            return True
        except Exception:
            continue
    return False


async def _execute_action(page: Page, action: dict, timeout: int = 8000) -> None:
    a = action.get("action", "")

    if a == "goto":
        await page.goto(str(action["url"]), wait_until="networkidle", timeout=30000)

    elif a == "click":
        sel = str(action.get("selector", ""))
        fallbacks = _fallback_selectors(sel)
        ok = await _try_action(lambda s: page.click(s, timeout=timeout), fallbacks)
        if not ok:
            raise Exception(f"Could not click any selector: {sel}")

    elif a == "fill":
        sel = str(action.get("selector", ""))
        value = str(action.get("value", ""))
        try:
            await page.fill(sel, value, timeout=timeout)
        except Exception:
            alts = _fallback_selectors(sel)
            ok = await _try_action(lambda s: page.fill(s, value, timeout=timeout), alts[1:])
            if not ok:
                raise Exception(f"Could not fill selector: {sel}")

    elif a == "select_option":
        await page.select_option(str(action["selector"]), str(action.get("value", "")), timeout=timeout)

    elif a == "check":
        await page.check(str(action["selector"]), timeout=timeout)

    elif a == "hover":
        await page.hover(str(action["selector"]), timeout=timeout)

    elif a == "press":
        await page.keyboard.press(str(action.get("key", "Enter")))

    elif a == "scroll":
        delta = 500 if action.get("direction", "down") == "down" else -500
        await page.evaluate(f"window.scrollBy(0, {delta})")

    elif a == "wait_for_selector":
        await page.wait_for_selector(str(action["selector"]), timeout=timeout)

    elif a == "wait_for_url":
        await page.wait_for_url(f"**{action['url_contains']}**", timeout=timeout)

    elif a == "assert_visible":
        sel = str(action.get("selector", ""))
        loc = page.locator(sel)
        count = await loc.count()
        if count == 0:
            raise AssertionError(f"No elements found for: {sel}")
        if not await loc.first.is_visible():
            raise AssertionError(f"Element not visible: {sel}")

    elif a == "assert_hidden":
        sel = str(action.get("selector", ""))
        loc = page.locator(sel)
        if await loc.count() > 0 and await loc.first.is_visible():
            raise AssertionError(f"Element should be hidden but is visible: {sel}")

    elif a == "assert_text":
        sel = str(action.get("selector", ""))
        expected = str(action.get("contains", ""))
        try:
            text = await page.locator(sel).first.inner_text(timeout=timeout)
        except Exception:
            text = await page.locator(sel).first.text_content(timeout=timeout) or ""
        if expected.lower() not in text.lower():
            raise AssertionError(f"Expected '{expected}' in '{text[:120]}'")

    elif a == "assert_url":
        expected = str(action.get("contains", ""))
        if expected not in page.url:
            raise AssertionError(f"URL '{page.url}' does not contain '{expected}'")

    elif a == "assert_title":
        expected = str(action.get("contains", ""))
        title = await page.title()
        if expected.lower() not in title.lower():
            raise AssertionError(f"Title '{title}' does not contain '{expected}'")

    elif a == "assert_count":
        sel = str(action.get("selector", ""))
        min_count = int(action.get("min", 1))
        count = await page.locator(sel).count()
        if count < min_count:
            raise AssertionError(f"Expected >= {min_count} for '{sel}', got {count}")


async def _run_accessibility_check(page: Page) -> dict:
    try:
        await page.add_script_tag(
            url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.7.2/axe.min.js"
        )
        await page.wait_for_timeout(800)
        results = await page.evaluate("""
            () => new Promise((resolve) => {
                if (typeof axe === 'undefined') { resolve({violations: []}); return; }
                axe.run().then(r => resolve({
                    violations: r.violations.slice(0, 15).map(v => ({
                        id: v.id,
                        impact: v.impact,
                        description: v.description,
                        nodes: v.nodes.length,
                    }))
                })).catch(() => resolve({violations: []}));
            })
        """)
        violations = results.get("violations", [])
        return {"violations_count": len(violations), "violations": violations}
    except Exception as e:
        return {"violations_count": 0, "violations": [], "error": str(e)}


async def _run_single_test(
    context,
    test_case: dict,
    index: int,
    screenshots_dir: Path,
    browser_name: str = "chromium",
    mobile: bool = False,
    progress_cb=None,
    frame_cb=None,
) -> dict:
    test_id = str(test_case.get("test_id", f"TC{index:03d}"))
    test_name = str(test_case.get("test_name", f"Test {test_id}"))
    page_url = str(test_case.get("page_url", ""))
    playwright_steps = test_case.get("playwright_steps", [])
    test_type = test_case.get("test_type", "functional")

    suffix = ("_mobile" if mobile else "") + (f"_{browser_name}" if browser_name != "chromium" else "")
    run_id = test_id + suffix
    screenshot_path = screenshots_dir / f"test_{run_id}.png"

    if progress_cb:
        label = f"[{'📱' if mobile else '🖥'}] {test_id}: {test_name}"
        progress_cb("execute", f"Running {label}", {"test_id": run_id})

    page = await context.new_page()
    if mobile:
        await page.set_viewport_size({"width": 375, "height": 812})

    status = "pass"
    error_message = None
    step_results = []
    accessibility = {}

    async def _emit_frame(action_desc: str, action_type: str = "", cursor_x=None, cursor_y=None):
        if not frame_cb:
            return
        try:
            img_bytes = await page.screenshot(type="jpeg", quality=55)
            frame_cb("frame", action_desc, {
                "img": base64.b64encode(img_bytes).decode(),
                "action": action_desc,
                "action_type": action_type,
                "cursor_x": cursor_x,
                "cursor_y": cursor_y,
                "test_id": run_id,
                "test_name": test_name,
                "page_url": page.url,
            })
        except Exception:
            pass

    try:
        if page_url:
            # Emit a frame immediately so the UI changes state to active navigation
            await _emit_frame(f"Connecting to {page_url}...", "goto")
            try:
                await page.goto(page_url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)  # Wait 2s for layout/images to paint (avoids blank white screen)
                await _emit_frame(f"Navigated to {page_url}", "goto")
            except Exception as goto_err:
                # Emit a frame showing the failure state before re-throwing
                await _emit_frame(f"Navigation failed: {str(goto_err)}", "error")
                raise goto_err

        last_x = 640
        last_y = 360

        for step in playwright_steps:
            step_action = step.get("action", "")
            step_desc = step.get("description", step_action)

            cursor_x = cursor_y = None
            if frame_cb and step_action in ("click", "fill", "hover", "check"):
                sel = str(step.get("selector", ""))
                if sel:
                    try:
                        box = await page.locator(sel).first.bounding_box(timeout=1500)
                        if box:
                            cursor_x = int(box["x"] + box["width"] / 2)
                            cursor_y = int(box["y"] + box["height"] / 2)
                    except Exception:
                        pass

            if cursor_x is not None and cursor_y is not None:
                if last_x is not None and last_y is not None:
                    # Emit starting point frame
                    await _emit_frame(f"Moving cursor towards: {step_desc}", "hover", last_x, last_y)
                    await page.wait_for_timeout(350)
                # Emit end point frame (CSS transition glides cursor smoothly)
                await _emit_frame(f"Targeting: {step_desc}", "hover", cursor_x, cursor_y)
                await page.wait_for_timeout(800)
                last_x = cursor_x
                last_y = cursor_y
            else:
                await _emit_frame(step_desc, step_action, last_x, last_y)

            try:
                await _execute_action(page, step)
                step_results.append({"action": step_action, "status": "pass", "description": step_desc})
                
                if step_action == "click" and cursor_x is not None:
                    # Emit click event triggers pulsing click-ring in frontend
                    await _emit_frame(f"Clicking: {step_desc}", "click", cursor_x, cursor_y)
                    await page.wait_for_timeout(600)

                await page.wait_for_timeout(1000)
                await _emit_frame(f"Completed: {step_desc}", step_action, cursor_x, cursor_y)
            except Exception as step_err:
                err_str = str(step_err)
                step_results.append({"action": step_action, "status": "fail", "description": step_desc, "error": err_str})
                # Assertion failures and navigation/fill failures are fatal
                if step_action.startswith("assert_") or step_action in ("goto", "fill", "click"):
                    status = "fail"
                    error_message = f"'{step_desc}': {err_str}"
                    break

        # Accessibility audit for accessibility test types
        if test_type == "accessibility":
            accessibility = await _run_accessibility_check(page)
            if accessibility.get("violations_count", 0) > 3:
                status = "fail"
                error_message = f"{accessibility['violations_count']} accessibility violations found"

    except Exception as err:
        status = "fail"
        error_message = str(err)

    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        pass

    await page.close()

    result = {
        "test_id": run_id,
        "test_name": test_name + (" (Mobile)" if mobile else ""),
        "page_url": page_url,
        "test_type": test_type,
        "risk_level": test_case.get("risk_level", "medium"),
        "browser": browser_name,
        "mobile": mobile,
        "status": status,
        "error": error_message,
        "step_results": step_results,
        "steps_total": len(playwright_steps),
        "steps_passed": sum(1 for s in step_results if s["status"] == "pass"),
        "accessibility": accessibility,
        "screenshot": _to_web_path(screenshot_path),
        "expected_result": str(test_case.get("expected_result", "")),
    }

    if progress_cb:
        progress_cb(
            "test_result",
            f"{'✓' if status == 'pass' else '✗'} {test_id}: {status.upper()}",
            result,
        )

    return result


async def execute_tests_async(
    browsers: list = None,
    run_mobile: bool = True,
    progress_cb=None,
    frame_cb=None,
    url: str = None,
) -> list:
    if browsers is None:
        browsers = ["chromium"]

    test_cases = _load_test_cases(url)
    reports_dir = _get_reports_dir()
    screenshots_dir = reports_dir / "test_screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    all_results = []

    browser_map = {"chromium": "chromium", "firefox": "firefox", "webkit": "webkit"}

    async with async_playwright() as p:
        for browser_name in browsers:
            launcher = getattr(p, browser_map.get(browser_name, "chromium"))
            browser = await launcher.launch(headless=True)
            context = await browser.new_context()

            try:
                for i, tc in enumerate(test_cases, start=1):
                    result = await _run_single_test(
                        context, tc, i, screenshots_dir,
                        browser_name=browser_name, mobile=False,
                        progress_cb=progress_cb, frame_cb=frame_cb,
                    )
                    all_results.append(result)

                    # Run mobile variant for critical/high risk tests
                    if run_mobile and tc.get("risk_level") in ("critical", "high"):
                        mobile_result = await _run_single_test(
                            context, tc, i, screenshots_dir,
                            browser_name=browser_name, mobile=True,
                            progress_cb=progress_cb, frame_cb=frame_cb,
                        )
                        all_results.append(mobile_result)
            finally:
                await context.close()
                await browser.close()

    db_manager.save_test_results(all_results, url)

    passed = sum(1 for r in all_results if r["status"] == "pass")
    failed = len(all_results) - passed
    print(f"\nExecution complete: {len(all_results)} tests, {passed} passed, {failed} failed")
    return all_results


def execute_tests(browsers=None, run_mobile=True, progress_cb=None, frame_cb=None, url=None) -> list:
    return asyncio.run(execute_tests_async(
        browsers=browsers, run_mobile=run_mobile, progress_cb=progress_cb, frame_cb=frame_cb, url=url,
    ))
