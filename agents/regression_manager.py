import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import backend.db_manager as db_manager

HISTORY_PATH = Path(__file__).resolve().parent.parent / "reports" / "regression_history.json"
MAX_HISTORY = 30


def load_history(url: str = None) -> List[Dict[str, Any]]:
    return db_manager.load_run_history(url)


def save_run(results: List[Dict[str, Any]], url: str) -> Dict[str, Any]:
    history = load_history(url)
    run: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "total": len(results),
        "passed": sum(1 for r in results if r.get("status") == "pass"),
        "failed": sum(1 for r in results if r.get("status") == "fail"),
        "pass_rate": round(
            sum(1 for r in results if r.get("status") == "pass") / len(results) * 100
            if results else 0,
            1,
        ),
        "statuses": {r["test_id"]: r["status"] for r in results if "test_id" in r},
        "by_type": _count_by(results, "test_type"),
        "by_risk": _count_by(results, "risk_level"),
    }
    history.append(run)
    history = history[-MAX_HISTORY:]
    db_manager.save_run_history(history, url)
    return run


def compare_with_previous(current_results: List[Dict[str, Any]], url: str = None) -> Dict[str, Any]:
    history = load_history(url)
    base: Dict[str, Any] = {
        "new_failures": [],
        "fixed": [],
        "stable_failures": [],
        "stable_passes": [],
        "is_first_run": True,
        "previous_pass_rate": None,
    }
    if len(history) < 2:
        return base

    prev = history[-2]
    prev_statuses: Dict[str, str] = prev.get("statuses", {})
    curr_statuses = {r["test_id"]: r["status"] for r in current_results if "test_id" in r}

    return {
        "new_failures": [t for t, s in curr_statuses.items() if s == "fail" and prev_statuses.get(t) == "pass"],
        "fixed": [t for t, s in curr_statuses.items() if s == "pass" and prev_statuses.get(t) == "fail"],
        "stable_failures": [t for t, s in curr_statuses.items() if s == "fail" and prev_statuses.get(t) == "fail"],
        "stable_passes": [t for t, s in curr_statuses.items() if s == "pass" and prev_statuses.get(t) == "pass"],
        "is_first_run": False,
        "previous_pass_rate": prev.get("pass_rate"),
    }


def _count_by(results: List[Dict], key: str) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for r in results:
        val = str(r.get(key, "unknown"))
        status = str(r.get("status", "unknown"))
        if val not in out:
            out[val] = {"pass": 0, "fail": 0}
        out[val][status] = out[val].get(status, 0) + 1
    return out
