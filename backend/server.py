import asyncio
import json
import mimetypes
import queue
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import backend.db_manager as db_manager

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from agents.crawler_agent import crawl_website
from agents.diagnostics_agent import generate_diagnostics, chat_about_results
from agents.executor_agent import execute_tests_async
from agents.regression_manager import compare_with_previous, save_run
from agents.test_generator_agent import generate_test_cases

REPORTS_DIR = REPO_ROOT / "reports"
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"

# Active run queues: run_id -> Queue
_RUN_QUEUES: Dict[str, queue.Queue] = {}
_RUN_QUEUES_LOCK = threading.Lock()
# Only one pipeline at a time
_RUN_LOCK = threading.Lock()
_SHOULD_ABORT = False

class AbortPipelineException(BaseException):
    pass


# ── helpers ────────────────────────────────────────────────────────────────────

def _json_resp(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _cors(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _cors(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")


def _read_json(handler: BaseHTTPRequestHandler) -> Optional[Dict[str, Any]]:
    length = handler.headers.get("Content-Length")
    if not length:
        return None
    try:
        raw = handler.rfile.read(int(length))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _serve_file(handler: BaseHTTPRequestHandler, file_path: Path) -> None:
    if not file_path.exists() or not file_path.is_file():
        _json_resp(handler, 404, {"error": "Not found"})
        return
    ctype, _ = mimetypes.guess_type(str(file_path))
    data = file_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", ctype or "application/octet-stream")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


# ── pipeline ───────────────────────────────────────────────────────────────────

async def _run_pipeline(
    url: str,
    max_pages: int,
    browsers: List[str],
    run_mobile: bool,
    progress_cb: Callable,
) -> Dict[str, Any]:
    pages = await crawl_website(url, max_pages=max_pages, progress_cb=progress_cb)

    test_cases = await asyncio.to_thread(
        generate_test_cases, pages, progress_cb
    )

    results = await execute_tests_async(
        browsers=browsers, run_mobile=run_mobile,
        progress_cb=progress_cb, frame_cb=progress_cb,
        url=url,
    )

    passed = sum(1 for r in results if r.get("status") == "pass")
    failed = len(results) - passed

    # Generate and persist AI diagnostics/remediation guides
    progress_cb("generate", "Analyzing test failures and generating AI Auto-Fix guides...")
    diagnostics = await asyncio.to_thread(generate_diagnostics, results)
    db_manager.save_diagnostics(diagnostics, url)

    run_record = save_run(results, url)
    regression = compare_with_previous(results, url)

    report: Dict[str, Any] = {
        "input_url": url,
        "max_pages": max_pages,
        "browsers": browsers,
        "pages_crawled": len(pages),
        "test_cases_generated": len(test_cases),
        "tests_run": len(results),
        "tests_passed": passed,
        "tests_failed": failed,
        "pass_rate": run_record.get("pass_rate", 0),
        "by_type": run_record.get("by_type", {}),
        "by_risk": run_record.get("by_risk", {}),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "final_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {"report": report, "results": results, "regression": regression}


def _run_pipeline_thread(run_id: str, url: str, max_pages: int, browsers: List[str], run_mobile: bool) -> None:
    q = _RUN_QUEUES.get(run_id)
    if q is None:
        return

    def progress_cb(phase: str, message: str, data: Dict[str, Any] = None) -> None:
        global _SHOULD_ABORT
        if _SHOULD_ABORT:
            raise AbortPipelineException("Pipeline stopped by user.")

        event: Dict[str, Any] = {"type": phase, "message": message}
        if data:
            event.update(data)
        q.put(event)
        
        # Print progress to backend console terminal live
        icons = {
            "crawl": "[crawl]",
            "generate": "[generate]",
            "execute": "[execute]",
            "test_result": "[test]",
            "complete": "[complete]",
            "error": "[error]"
        }
        prefix = icons.get(phase, "[?]")
        if phase == "test_result" and data:
            status = data.get("status", "")
            prefix = "[pass]" if status == "pass" else "[fail]" if status == "fail" else "[pending]"
        print(f"{prefix} {message}", flush=True)

    acquired = _RUN_LOCK.acquire(blocking=False)
    if not acquired:
        q.put({"type": "error", "message": "Another run is already in progress."})
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _run_pipeline(url, max_pages, browsers, run_mobile, progress_cb)
        )
        q.put({"type": "complete", **result})
    except AbortPipelineException:
        q.put({"type": "error", "message": "Pipeline stopped by user."})
    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        loop.close()
        _RUN_LOCK.release()
        # Clean up queue after 10 minutes
        threading.Timer(600, lambda: _RUN_QUEUES.pop(run_id, None)).start()


def _run_load_test_thread(run_id: str, url: str, num_users: int, duration_seconds: int) -> None:
    q = _RUN_QUEUES.get(run_id)
    if q is None:
        return

    def progress_cb(pulse: Dict[str, Any]) -> None:
        event = {"type": "load_test_pulse", "data": pulse}
        q.put(event)

    from agents.load_tester import run_load_test

    try:
        report = run_load_test(
            target_url=url,
            num_users=num_users,
            duration_seconds=duration_seconds,
            progress_cb=progress_cb
        )
        # Save to DB
        db_manager.save_load_test(report, url)
        # Put complete
        q.put({"type": "complete", "report": report})
    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        # Clean up queue after 10 minutes
        threading.Timer(600, lambda: _RUN_QUEUES.pop(run_id, None)).start()


# ── request handler ────────────────────────────────────────────────────────────

class QAHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access log
        pass

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        _cors(self)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/status":
            _json_resp(self, 200, {"ok": True})
            return

        if path == "/api/reset":
            if _RUN_LOCK.locked():
                try:
                    _RUN_LOCK.release()
                    _json_resp(self, 200, {"success": True, "message": "Pipeline lock released successfully."})
                except Exception as e:
                    _json_resp(self, 500, {"success": False, "error": f"Failed to release lock: {str(e)}"})
            else:
                _json_resp(self, 200, {"success": True, "message": "Pipeline lock is already unlocked."})
            return

        if path == "/api/stop":
            global _SHOULD_ABORT
            _SHOULD_ABORT = True
            _json_resp(self, 200, {"success": True, "message": "Pipeline stop request received."})
            return

        if path == "/api/urls":
            urls = db_manager.get_tested_urls()
            _json_resp(self, 200, urls)
            return

        if path == "/api/history":
            url_param = qs.get("url", [""])[0]
            history = db_manager.load_run_history(url_param)
            _json_resp(self, 200, history)
            return

        if path == "/api/plan":
            url_param = qs.get("url", [""])[0]
            plan = db_manager.load_test_plan(url_param)
            if plan:
                _json_resp(self, 200, plan)
            else:
                _json_resp(self, 404, {"error": "No test plan yet"})
            return

        if path == "/api/diagnostics":
            url_param = qs.get("url", [""])[0]
            diagnostics = db_manager.load_diagnostics(url_param)
            _json_resp(self, 200, diagnostics)
            return

        if path == "/api/clear":
            try:
                db_manager.clear_all_data()
                _json_resp(self, 200, {"success": True, "message": "All test cases, plans, results and history cleared successfully."})
            except Exception as e:
                _json_resp(self, 500, {"success": False, "error": f"Failed to clear data: {str(e)}"})
            return

        if path == "/api/load-test/results":
            url_param = qs.get("url", [""])[0]
            report = db_manager.load_load_test(url_param)
            if report:
                _json_resp(self, 200, report)
            else:
                _json_resp(self, 404, {"error": "No load test yet"})
            return

        # SSE event stream
        if path == "/api/events":
            run_id = qs.get("run_id", [""])[0]
            with _RUN_QUEUES_LOCK:
                q = _RUN_QUEUES.get(run_id)
            if q is None:
                _json_resp(self, 404, {"error": "Run not found"})
                return
            self._stream_events(q)
            return

        # Static file serving
        if path.startswith("/reports/"):
            rel = path[len("/reports/"):]
            if rel == "test_cases.json":
                url_param = qs.get("url", [""])[0]
                cases = db_manager.load_test_cases(url_param)
                _json_resp(self, 200, cases)
                return
            if rel == "test_results.json":
                url_param = qs.get("url", [""])[0]
                results = db_manager.load_test_results(url_param)
                _json_resp(self, 200, results)
                return

            fp = (REPORTS_DIR / rel).resolve()
            if not str(fp).startswith(str(REPORTS_DIR.resolve())):
                _json_resp(self, 403, {"error": "Forbidden"})
                return
            _serve_file(self, fp)
            return

        if path.startswith("/screenshots/"):
            rel = path[len("/screenshots/"):]
            fp = (SCREENSHOTS_DIR / rel).resolve()
            if not str(fp).startswith(str(SCREENSHOTS_DIR.resolve())):
                _json_resp(self, 403, {"error": "Forbidden"})
                return
            _serve_file(self, fp)
            return

        _json_resp(self, 404, {"error": "Not found"})

    def do_POST(self):  # noqa: N802
        global _SHOULD_ABORT
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/reset":
            if _RUN_LOCK.locked():
                try:
                    _RUN_LOCK.release()
                    _json_resp(self, 200, {"success": True, "message": "Pipeline lock released successfully."})
                except Exception as e:
                    _json_resp(self, 500, {"success": False, "error": f"Failed to release lock: {str(e)}"})
            else:
                _json_resp(self, 200, {"success": True, "message": "Pipeline lock is already unlocked."})
            return

        if path == "/api/stop":
            _SHOULD_ABORT = True
            _json_resp(self, 200, {"success": True, "message": "Pipeline stop request received."})
            return

        if path == "/api/chat":
            payload = _read_json(self)
            if not payload:
                _json_resp(self, 400, {"error": "Expected JSON body"})
                return
            query = payload.get("query", "").strip()
            url_param = payload.get("url", "").strip()
            
            if not query:
                _json_resp(self, 400, {"error": "Missing 'query'"})
                return
                
            results = db_manager.load_test_results(url_param)
            if not results:
                results = db_manager.load_test_results()
                
            try:
                response_text = chat_about_results(query, results)
                _json_resp(self, 200, {"response": response_text})
            except Exception as e:
                _json_resp(self, 500, {"error": f"Failed communicating with AI: {str(e)}"})
            return

        if path == "/api/load-test/run":
            payload = _read_json(self)
            if not payload:
                _json_resp(self, 400, {"error": "Expected JSON body"})
                return
                
            url = str(payload.get("url", "")).strip()
            if not url:
                _json_resp(self, 400, {"error": "Missing 'url'"})
                return
                
            try:
                users = max(1, min(int(payload.get("users", 20)), 200))
            except Exception:
                users = 20
                
            try:
                duration = max(5, min(int(payload.get("duration", 15)), 120))
            except Exception:
                duration = 15

            run_id = str(uuid.uuid4())
            q: queue.Queue = queue.Queue()
            with _RUN_QUEUES_LOCK:
                _RUN_QUEUES[run_id] = q

            t = threading.Thread(
                target=_run_load_test_thread,
                args=(run_id, url, users, duration),
                daemon=True,
            )
            t.start()

            _json_resp(self, 202, {"run_id": run_id})
            return

        if path != "/api/run":
            _json_resp(self, 404, {"error": "Not found"})
            return

        _SHOULD_ABORT = False

        payload = _read_json(self)
        if not payload:
            _json_resp(self, 400, {"error": "Expected JSON body"})
            return

        url = str(payload.get("url", "")).strip()
        if not url:
            _json_resp(self, 400, {"error": "Missing 'url'"})
            return

        try:
            max_pages = max(1, min(int(payload.get("max_pages", 10)), 50))
        except Exception:
            max_pages = 10

        browsers = payload.get("browsers", ["chromium"])
        if not isinstance(browsers, list) or not browsers:
            browsers = ["chromium"]
        browsers = [b for b in browsers if b in ("chromium", "firefox", "webkit")]
        if not browsers:
            browsers = ["chromium"]

        run_mobile = bool(payload.get("mobile", True))

        run_id = str(uuid.uuid4())
        q: queue.Queue = queue.Queue()
        with _RUN_QUEUES_LOCK:
            _RUN_QUEUES[run_id] = q

        t = threading.Thread(
            target=_run_pipeline_thread,
            args=(run_id, url, max_pages, browsers, run_mobile),
            daemon=True,
        )
        t.start()

        _json_resp(self, 202, {"run_id": run_id})

    def _stream_events(self, q: queue.Queue) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        _cors(self)
        self.end_headers()

        try:
            while True:
                try:
                    event = q.get(timeout=25)
                except queue.Empty:
                    self.wfile.write(b"data: {\"type\":\"heartbeat\"}\n\n")
                    self.wfile.flush()
                    continue

                data = json.dumps(event, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()

                if event.get("type") in ("complete", "error"):
                    break
        except Exception:
            pass


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), QAHandler)
    print(f"QA Agent backend running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
