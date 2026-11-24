import json
import os
from pathlib import Path
from typing import Any, Dict, List
from groq import Groq

MODEL = "llama-3.3-70b-versatile"

def _try_read_dotenv(key: str) -> str:
    root = Path(__file__).resolve().parent.parent
    env = root / ".env"
    if not env.exists():
        return ""
    try:
        text = env.read_text(encoding="utf-8")
    except Exception:
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

def _extract_json_object(raw: str) -> str:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return "{}"
    return raw[start:end + 1]

def generate_diagnostics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    failed = [r for r in results if r.get("status") == "fail"]
    if not failed:
        return {
            "summary": "All tests passed successfully! The application is behaving perfectly under all execution profiles.",
            "recommendations": []
        }

    # Prepare inputs for the diagnostic LLM
    failing_info = []
    for r in failed:
        failing_info.append({
            "test_id": r.get("test_id", "Unknown"),
            "test_name": r.get("test_name", "Unknown"),
            "page_url": r.get("page_url", ""),
            "test_type": r.get("test_type", ""),
            "error": r.get("error", ""),
            "expected_result": r.get("expected_result", ""),
            "steps": [
                {
                    "step": s.get("step", ""),
                    "status": s.get("status", ""),
                    "error": s.get("error", "")
                }
                for s in r.get("step_results", [])
            ]
        })

    prompt = (
        "You are a Senior Principal QA Architect and Full-Stack Bug-Fixing Engineer.\n"
        "Analyze the following failed test execution results of our web application. For each failed test, generate a highly structured, professional, and actionable fix guide.\n\n"
        "Failing Tests Data:\n"
        f"{json.dumps(failing_info, indent=2)}\n\n"
        "Format the output strictly as a single JSON object. Do not include any explanation outside the JSON. The JSON structure MUST be exactly as follows:\n"
        "{\n"
        '  "summary": "A high-level, human-friendly diagnostic summary explaining what seems to be the core systemic problem of the application.",\n'
        '  "recommendations": [\n'
        "    {\n"
        '      "test_id": "TC001",\n'
        '      "test_name": "Test Name",\n'
        '      "root_cause": "Detailed, plain English explanation of precisely why this test failed.",\n'
        '      "fix_action": "Exact instructions for the developer on how to fix this issue (e.g. check selector name, verify routing, ensure state loads).",\n'
        '      "copilot_prompt": "A copy-pasteable, detailed prompt for an AI assistant like Copilot, Claude, or ChatGPT to automatically patch or fix this exact bug in the code. Make sure the prompt is extremely detailed, outlining the file name, target code section, and precise replacement changes."\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Return ONLY the raw JSON object. Do not include markdown code block wrapper."
    )

    try:
        client = _get_client()
        response_raw = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        ).choices[0].message.content or "{}"
        
        extracted = _extract_json_object(response_raw)
        return json.loads(extracted)
    except Exception as e:
        print(f"[Diagnostics Agent] Exception occurred while generating diagnostics: {e}", flush=True)
        # Fallback diagnostics structure
        fallback_recommendations = []
        for r in failed:
            fallback_recommendations.append({
                "test_id": r.get("test_id", "Unknown"),
                "test_name": r.get("test_name", "Unknown"),
                "root_cause": f"Execution failed with error: {r.get('error', 'No explicit error details provided.')}",
                "fix_action": "Inspect the failure logs, double check target page selectors, and ensure backend endpoints are functioning correctly.",
                "copilot_prompt": f"Fix the test case {r.get('test_id')} which failed on url {r.get('page_url')} with the error: {r.get('error')}"
            })
        return {
            "summary": "Automated pipeline analysis completed. Test failures were detected during execution.",
            "recommendations": fallback_recommendations
        }


# ── AI QA Copilot Chat ─────────────────────────────────────────────────────────

def chat_about_results(query: str, results: List[Dict[str, Any]]) -> str:
    if not results:
        return "I don't have any test execution results to analyze yet. Please run the pipeline first!"
        
    cases_summary = []
    for r in results:
        status = r.get("status", "pending").upper()
        steps = [
            f"  - Step: {s.get('step', s.get('action', ''))} -> {s.get('status', '').upper()}" + (f" (Error: {s.get('error')})" if s.get('error') else "")
            for s in r.get("step_results", [])
        ]
        steps_str = "\n".join(steps)
        cases_summary.append(
            f"TEST ID: {r.get('test_id')}\n"
            f"TEST NAME: {r.get('test_name')}\n"
            f"URL: {r.get('page_url', r.get('url', ''))}\n"
            f"STATUS: {status}\n"
            f"TYPE: {r.get('test_type')}\n"
            f"RISK: {r.get('risk_level')}\n"
            + (f"ERROR: {r.get('error')}\n" if r.get('error') else "")
            + f"STEPS:\n{steps_str}\n"
            f"---"
        )
    
    summary_block = "\n".join(cases_summary)
    
    system_prompt = (
        "You are an Advanced AI QA Copilot assisting a full-stack developer.\n"
        "You have complete visibility over the latest end-to-end (E2E) automated test results for this application.\n"
        "Analyze the test cases provided below, answer the developer's questions clearly, offer debugging insights, and provide code remediation recommendations where appropriate.\n\n"
        "### CURRENT E2E AUTOMATED TEST RESULTS:\n"
        f"{summary_block}\n\n"
        "Guidelines:\n"
        "1. Address the passed and failed tests specifically by their name or ID if the developer asks about them.\n"
        "2. Explain why a test failed (inspect the steps and error message).\n"
        "3. Keep answers concise, highly technical, and formatted beautifully using markdown, bold highlights, tables, or code snippets where applicable.\n"
        "4. If all tests passed, praise their implementation and explain what was successfully verified."
    )
    
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.4,
        ).choices[0].message.content or "No response from AI."
        return response
    except Exception as e:
        return f"Error communicating with Groq / Llama-3.3: {str(e)}"

