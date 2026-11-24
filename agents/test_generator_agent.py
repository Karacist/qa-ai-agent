import json
import os
from pathlib import Path
from typing import Any, Dict, List

from groq import Groq
import backend.db_manager as db_manager

MODEL = "llama-3.3-70b-versatile"

STEP_ACTIONS_SPEC = """
Each playwright_step must use EXACTLY one of these action types:
  {"action":"goto","url":"https://..."}
  {"action":"click","selector":"CSS","description":"what"}
  {"action":"fill","selector":"CSS","value":"text"}
  {"action":"select_option","selector":"CSS","value":"option"}
  {"action":"check","selector":"CSS"}
  {"action":"hover","selector":"CSS"}
  {"action":"press","key":"Enter"}
  {"action":"scroll","direction":"down"}
  {"action":"wait_for_selector","selector":"CSS"}
  {"action":"wait_for_url","url_contains":"substr"}
  {"action":"assert_visible","selector":"CSS","description":"what"}
  {"action":"assert_hidden","selector":"CSS"}
  {"action":"assert_text","selector":"CSS","contains":"text"}
  {"action":"assert_url","contains":"substr"}
  {"action":"assert_title","contains":"text"}
  {"action":"assert_count","selector":"CSS","min":1}

CRITICAL SELECTOR RULES:
1. Navigation links are almost ALWAYS <a> tags on this site. Use a selector like: a:has-text("Contact Us"), a:has-text("About Us"), a:has-text("About University"), a:has-text("Academics").
2. DO NOT use button:has-text(...) for navigation links unless the page structure explicitly lists it as a button.
3. NEVER attempt to click or fill hidden input fields (such as input[name='__EVENTTARGET'], input[name='__VIEWSTATE']). Only interact with visible elements.
4. If checking search, verify if there is an input like input[type="text"] or input[name="search"], and check the exact links.
"""


def _try_read_dotenv(key: str) -> str:
    root = Path(__file__).resolve().parent.parent
    env = root / ".env"
    if not env.exists():
        return ""
    for enc in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            text = env.read_text(encoding=enc, errors="ignore")
            break
        except Exception:
            text = ""
    else:
        return ""
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if line.startswith("export "):
            line = line[7:].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() != key:
            continue
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        return v.strip()
    return ""


def _get_client() -> Groq:
    key = os.environ.get("GROQ_API_KEY", "").strip() or _try_read_dotenv("GROQ_API_KEY")
    if not key:
        raise ValueError("Missing GROQ_API_KEY. Set it in .env or as an environment variable.")
    return Groq(api_key=key)


def _extract_json_array(raw: str) -> str:
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON array found in model response.")
    return raw[start:end + 1]


def _extract_json_object(raw: str) -> str:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return "{}"
    return raw[start:end + 1]


def _save(obj: Any, filename: str, url: Optional[str] = None) -> None:
    if filename == "test_plan.json":
        db_manager.save_test_plan(obj, url)
    elif filename == "test_cases.json":
        db_manager.save_test_cases(obj, url)
    else:
        d = Path(__file__).resolve().parent.parent / "reports"
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_plan_prompt(pages: List[Dict]) -> str:
    sitemap = []
    for pg in pages:
        s = pg.get("structure", {})
        sitemap.append({
            "url": pg["url"],
            "title": pg["title"],
            "forms": len(s.get("forms", [])),
            "buttons": [b["text"] for b in s.get("buttons", [])[:8]],
            "headings": [h["text"] for h in s.get("headings", [])[:5]],
            "inputs": len(s.get("inputs", [])),
            "api_calls": [c["url"] for c in pg.get("api_calls", [])[:5]],
            "perf_load_ms": pg.get("performance", {}).get("load_time", 0),
        })
    return (
        "You are a senior QA engineer. Analyze this web application sitemap and create a structured test plan.\n\n"
        f"Sitemap:\n{json.dumps(sitemap, indent=2)}\n\n"
        "Return a JSON object with exactly these keys:\n"
        '  "app_summary": "one sentence describing the app",\n'
        '  "critical_flows": ["list of 3-5 most important user journeys to test"],\n'
        '  "risk_areas": ["list of high-risk features: auth, payments, forms, data integrity etc"],\n'
        '  "test_categories": ["functional","negative","navigation","form_validation","accessibility","performance","mobile"],\n'
        '  "auth_required": true/false,\n'
        '  "has_forms": true/false\n'
        "\nReturn ONLY valid JSON, no markdown, no commentary."
    )


def _build_tests_prompt(pages: List[Dict], test_plan: dict) -> str:
    summaries = []
    for pg in pages:
        s = pg.get("structure", {})
        summaries.append({
            "url": pg["url"],
            "title": pg["title"],
            "forms": s.get("forms", []),
            "buttons": [b["text"] for b in s.get("buttons", [])[:12]],
            "headings": [h["text"] for h in s.get("headings", [])[:6]],
            "links": [l["text"] for l in s.get("links", [])[:10]],
            "inputs": s.get("inputs", [])[:8],
            "select_elements": s.get("select_elements", []),
            "images_without_alt": s.get("images_without_alt", 0),
            "performance": pg.get("performance", {}),
            "api_calls": [c["url"] for c in pg.get("api_calls", [])[:5]],
        })

    return (
        "You are a senior QA engineer. Generate comprehensive end-to-end test cases for this web app.\n\n"
        f"Test Plan:\n{json.dumps(test_plan, indent=2)}\n\n"
        f"Pages & Structure:\n{json.dumps(summaries, indent=2)}\n\n"
        "Generate 10-15 test cases covering ALL of these categories:\n"
        "1. FUNCTIONAL: Happy path for each major feature\n"
        "2. NEGATIVE: Invalid inputs, empty required fields, wrong credentials\n"
        "3. NAVIGATION: All major navigation links work, correct page loads\n"
        "4. FORM_VALIDATION: Required fields, email format, min/max length\n"
        "5. ACCESSIBILITY: Images have alt text, forms have labels, heading hierarchy\n"
        "6. PERFORMANCE: Page loads under 3 seconds (assert load_time from metrics)\n"
        "7. MOBILE: Key flows work at 375px viewport\n\n"
        + STEP_ACTIONS_SPEC + "\n\n"
        "Return ONLY a JSON array. Each element must have:\n"
        "  test_id (TC001...), test_name, page_url, test_type (functional|negative|navigation|"
        "form_validation|accessibility|performance|mobile), risk_level (critical|high|medium|low), "
        "playwright_steps (array using spec above), steps (human-readable strings), expected_result\n\n"
        "Use real selectors from the page structure above. Return valid parseable JSON only."
    )


def generate_test_cases(pages: List[Dict[str, Any]], progress_cb=None) -> List[Dict[str, Any]]:
    client = _get_client()

    if progress_cb:
        progress_cb("generate", "Analyzing app and generating test plan...")

    plan_raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": _build_plan_prompt(pages)}],
        temperature=0.1,
    ).choices[0].message.content or "{}"

    target_url = pages[0]["url"] if pages else None

    try:
        test_plan = json.loads(_extract_json_object(plan_raw))
    except Exception:
        test_plan = {}
    _save(test_plan, "test_plan.json", target_url)

    if progress_cb:
        progress_cb("generate", f"Test plan ready — generating {10}-15 test cases...")

    tests_raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": _build_tests_prompt(pages, test_plan)}],
        temperature=0.2,
    ).choices[0].message.content or "[]"

    try:
        test_cases = json.loads(_extract_json_array(tests_raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse test cases JSON: {exc}") from exc

    if isinstance(test_cases, dict):
        test_cases = [test_cases]

    for i, tc in enumerate(test_cases, start=1):
        if not isinstance(tc, dict):
            continue
        tc.setdefault("test_id", f"TC{i:03d}")
        tc.setdefault("risk_level", "medium")
        tc.setdefault("test_type", "functional")
        tc.setdefault("playwright_steps", [])
        tc.setdefault("steps", [])
        tc.setdefault("page_url", pages[0]["url"] if pages else "")

    test_cases = [tc for tc in test_cases if isinstance(tc, dict)]
    _save(test_cases, "test_cases.json", target_url)
    return test_cases
