import json
import os
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
import pymongo
from pymongo import MongoClient

# File fallback paths
REPORTS_DIR = Path(__file__).parent.parent / "reports"
PLAN_FILE = REPORTS_DIR / "test_plan.json"
CASES_FILE = REPORTS_DIR / "test_cases.json"
RESULTS_FILE = REPORTS_DIR / "test_results.json"
HISTORY_FILE = REPORTS_DIR / "regression_history.json"
DIAGNOSTICS_FILE = REPORTS_DIR / "diagnostics.json"

# MongoDB connection configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = "qa_agent_db"

_CLIENT: Optional[MongoClient] = None
_DB: Optional[Any] = None
_MONGO_ACTIVE = False

def init_db():
    global _CLIENT, _DB, _MONGO_ACTIVE
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("\n[DB] Initializing storage layer...", flush=True)
    try:
        # 2-second timeout to avoid long hangs on startup
        _CLIENT = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        # Force a server selection check
        _CLIENT.server_info()
        _DB = _CLIENT[DATABASE_NAME]
        _MONGO_ACTIVE = True
        print(f"[DB Status] Connected to MongoDB at {MONGO_URI} successfully!", flush=True)
    except Exception as e:
        _MONGO_ACTIVE = False
        _CLIENT = None
        _DB = None
        print(f"[DB Warning] MongoDB not detected or offline ({str(e)}).", flush=True)
        print("[DB Info] Gracefully falling back to robust local File-Based JSON Storage!\n", flush=True)

# Initialize immediately on import
init_db()


# ── URL Scoping Helpers ────────────────────────────────────────────────────────

def _get_url_key(url: Optional[str]) -> str:
    if not url:
        return "default"
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc or parsed.path
        # Keep alphanumeric, dot, underscore, dash
        clean = "".join(c for c in netloc if c.isalnum() or c in (".", "_", "-"))
        return clean.strip().lower() or "default"
    except Exception:
        return "default"

def _get_filepath(base_filename: str, url: Optional[str] = None) -> Path:
    key = _get_url_key(url)
    if not key or key == "default":
        return REPORTS_DIR / base_filename
    
    p = Path(base_filename)
    stem = p.stem
    ext = p.suffix
    return REPORTS_DIR / f"{stem}_{key}{ext}"


# ── Test Plan ──────────────────────────────────────────────────────────────────

def load_test_plan(url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    key = _get_url_key(url)
    if _MONGO_ACTIVE and _DB is not None:
        try:
            doc = _DB.test_plans.find_one({"target_url": key}, {"_id": 0})
            if doc:
                return doc
        except Exception as e:
            print(f"[DB Error] Failed to read test plan from Mongo: {e}. Falling back to file.", flush=True)
            
    file_path = _get_filepath("test_plan.json", url)
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def save_test_plan(plan: Dict[str, Any], url: Optional[str] = None) -> None:
    key = _get_url_key(url)
    # 1. Always save to JSON file as a local backup
    file_path = _get_filepath("test_plan.json", url)
    try:
        file_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Backup Error] Failed writing test plan file: {e}", flush=True)

    # 2. Save to MongoDB if active
    if _MONGO_ACTIVE and _DB is not None:
        try:
            _DB.test_plans.delete_many({"target_url": key})
            doc = dict(plan)
            doc["target_url"] = key
            _DB.test_plans.insert_one(doc)
            print(f"[DB] Test plan saved to MongoDB for key: {key}", flush=True)
        except Exception as e:
            print(f"[DB Error] Failed writing test plan to Mongo: {e}", flush=True)


# ── Test Cases ─────────────────────────────────────────────────────────────────

def load_test_cases(url: Optional[str] = None) -> List[Dict[str, Any]]:
    key = _get_url_key(url)
    if _MONGO_ACTIVE and _DB is not None:
        try:
            doc = _DB.test_cases.find_one({"target_url": key}, {"_id": 0})
            if doc and "cases" in doc:
                return doc["cases"]
        except Exception as e:
            print(f"[DB Error] Failed reading test cases from Mongo: {e}. Falling back to file.", flush=True)

    file_path = _get_filepath("test_cases.json", url)
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_test_cases(cases: List[Dict[str, Any]], url: Optional[str] = None) -> None:
    key = _get_url_key(url)
    file_path = _get_filepath("test_cases.json", url)
    try:
        file_path.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Backup Error] Failed writing test cases file: {e}", flush=True)

    if _MONGO_ACTIVE and _DB is not None:
        try:
            _DB.test_cases.delete_many({"target_url": key})
            _DB.test_cases.insert_one({"target_url": key, "cases": cases})
            print(f"[DB] {len(cases)} test cases saved to MongoDB for key: {key}", flush=True)
        except Exception as e:
            print(f"[DB Error] Failed writing test cases to Mongo: {e}", flush=True)


# ── Test Results ───────────────────────────────────────────────────────────────

def load_test_results(url: Optional[str] = None) -> List[Dict[str, Any]]:
    key = _get_url_key(url)
    if _MONGO_ACTIVE and _DB is not None:
        try:
            doc = _DB.test_results.find_one({"target_url": key}, {"_id": 0})
            if doc and "results" in doc:
                return doc["results"]
        except Exception as e:
            print(f"[DB Error] Failed reading test results from Mongo: {e}. Falling back to file.", flush=True)

    file_path = _get_filepath("test_results.json", url)
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_test_results(results: List[Dict[str, Any]], url: Optional[str] = None) -> None:
    key = _get_url_key(url)
    file_path = _get_filepath("test_results.json", url)
    try:
        file_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Backup Error] Failed writing test results file: {e}", flush=True)

    if _MONGO_ACTIVE and _DB is not None:
        try:
            _DB.test_results.delete_many({"target_url": key})
            _DB.test_results.insert_one({"target_url": key, "results": results})
            print(f"[DB] {len(results)} test results saved to MongoDB for key: {key}", flush=True)
        except Exception as e:
            print(f"[DB Error] Failed writing test results to Mongo: {e}", flush=True)


# ── Regression History ─────────────────────────────────────────────────────────

def load_run_history(url: Optional[str] = None) -> List[Dict[str, Any]]:
    key = _get_url_key(url)
    if _MONGO_ACTIVE and _DB is not None:
        try:
            doc = _DB.run_history.find_one({"target_url": key}, {"_id": 0})
            if doc and "history" in doc:
                return doc["history"]
        except Exception as e:
            print(f"[DB Error] Failed reading run history from Mongo: {e}. Falling back to file.", flush=True)

    file_path = _get_filepath("regression_history.json", url)
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_run_history(history: List[Dict[str, Any]], url: Optional[str] = None) -> None:
    key = _get_url_key(url)
    file_path = _get_filepath("regression_history.json", url)
    try:
        file_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Backup Error] Failed writing history file: {e}", flush=True)

    if _MONGO_ACTIVE and _DB is not None:
        try:
            _DB.run_history.delete_many({"target_url": key})
            _DB.run_history.insert_one({"target_url": key, "history": history})
            print(f"[DB] Regression run history saved to MongoDB for key: {key}", flush=True)
        except Exception as e:
            print(f"[DB Error] Failed writing history to Mongo: {e}", flush=True)


# ── AI Auto-Fix Diagnostics ───────────────────────────────────────────────────

def load_diagnostics(url: Optional[str] = None) -> Dict[str, Any]:
    key = _get_url_key(url)
    if _MONGO_ACTIVE and _DB is not None:
        try:
            doc = _DB.diagnostics.find_one({"target_url": key}, {"_id": 0})
            if doc:
                return doc
        except Exception as e:
            print(f"[DB Error] Failed reading diagnostics from Mongo: {e}. Falling back to file.", flush=True)

    file_path = _get_filepath("diagnostics.json", url)
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {"summary": "All systems healthy!", "recommendations": []}
    return {"summary": "All systems healthy!", "recommendations": []}

def save_diagnostics(diagnostics: Dict[str, Any], url: Optional[str] = None) -> None:
    key = _get_url_key(url)
    file_path = _get_filepath("diagnostics.json", url)
    try:
        file_path.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Backup Error] Failed writing diagnostics file: {e}", flush=True)

    if _MONGO_ACTIVE and _DB is not None:
        try:
            _DB.diagnostics.delete_many({"target_url": key})
            doc = dict(diagnostics)
            doc["target_url"] = key
            _DB.diagnostics.insert_one(doc)
            print(f"[DB] AI diagnostics saved to MongoDB for key: {key}", flush=True)
        except Exception as e:
            print(f"[DB Error] Failed writing diagnostics to Mongo: {e}", flush=True)


# ── Tested URLs Discovery ──────────────────────────────────────────────────────

def get_tested_urls() -> List[Dict[str, str]]:
    urls_map = {} # safe_key -> full_url
    
    # 1. Check MongoDB
    if _MONGO_ACTIVE and _DB is not None:
        try:
            for col in [_DB.test_plans, _DB.test_cases, _DB.test_results, _DB.load_tests]:
                for doc in col.find({}, {"target_url": 1, "input_url": 1, "url": 1, "page_url": 1}):
                    key = doc.get("target_url")
                    if not key or key == "default":
                        continue
                    full_url = doc.get("input_url") or doc.get("url") or doc.get("page_url")
                    # If load_tests collection format is a bit nested, try finding it inside doc.get("result", {})
                    if not full_url and "result" in doc and isinstance(doc["result"], dict):
                        full_url = doc["result"].get("target_url")
                    
                    if full_url and key not in urls_map:
                        urls_map[key] = full_url
        except Exception:
            pass

    # 2. Check local files
    try:
        # Scan plan files
        for f in REPORTS_DIR.glob("test_plan_*.json"):
            key = f.stem[len("test_plan_"):]
            if key and key != "default":
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    full_url = data.get("input_url") or data.get("url")
                    if full_url:
                        urls_map[key] = full_url
                except Exception:
                    pass
                    
        # Scan result files
        for f in REPORTS_DIR.glob("test_results_*.json"):
            key = f.stem[len("test_results_"):]
            if key and key != "default":
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(data, list) and len(data) > 0:
                        full_url = data[0].get("page_url") or data[0].get("url")
                        if full_url:
                            # Extract host
                            parsed = urllib.parse.urlparse(full_url)
                            base = f"{parsed.scheme}://{parsed.netloc}"
                            urls_map[key] = base
                except Exception:
                    pass

        # Scan load test files
        for f in REPORTS_DIR.glob("load_test_*.json"):
            key = f.stem[len("load_test_"):]
            if key and key != "default":
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    full_url = data.get("target_url") or data.get("url")
                    if full_url:
                        urls_map[key] = full_url
                except Exception:
                    pass
    except Exception:
        pass

    out = []
    for k, v in urls_map.items():
        out.append({"key": k, "url": v})
    return out


# ── Load Testing Scoped Data ───────────────────────────────────────────────────

def save_load_test(result: Dict[str, Any], url: Optional[str] = None) -> None:
    key = _get_url_key(url)
    # 1. Always save to JSON file as a local backup
    file_path = _get_filepath("load_test.json", url)
    try:
        file_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[DB Error] Failed to write load test backup file: {e}", flush=True)

    # 2. Save/Update in MongoDB if active
    if _MONGO_ACTIVE and _DB is not None:
        try:
            _DB.load_tests.update_one(
                {"target_url": key},
                {"$set": {"target_url": key, "result": result}},
                upsert=True
            )
        except Exception as e:
            print(f"[DB Error] Failed to save load test in Mongo: {e}", flush=True)

def load_load_test(url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    key = _get_url_key(url)
    if _MONGO_ACTIVE and _DB is not None:
        try:
            doc = _DB.load_tests.find_one({"target_url": key}, {"_id": 0})
            if doc and "result" in doc:
                return doc["result"]
        except Exception as e:
            print(f"[DB Error] Failed to read load test from Mongo: {e}. Falling back to file.", flush=True)
            
    file_path = _get_filepath("load_test.json", url)
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ── Clear All Data ─────────────────────────────────────────────────────────────

def clear_all_data() -> None:
    # 1. Delete all local JSON files including scoped ones
    try:
        for f in REPORTS_DIR.glob("*.json"):
            if any(prefix in f.name for prefix in ["test_plan", "test_cases", "test_results", "regression_history", "diagnostics", "load_test"]):
                try:
                    f.unlink()
                    print(f"[Backup] Deleted file {f.name}", flush=True)
                except Exception as e:
                    print(f"[DB Error] Failed to delete file {f.name}: {e}", flush=True)
    except Exception as e:
        print(f"[Clear Error] Failed to scan reports dir: {e}", flush=True)
                
    # 2. Clear MongoDB collections
    if _MONGO_ACTIVE and _DB is not None:
        try:
            _DB.test_plans.delete_many({})
            _DB.test_cases.delete_many({})
            _DB.test_results.delete_many({})
            _DB.run_history.delete_many({})
            _DB.diagnostics.delete_many({})
            _DB.load_tests.delete_many({})
            print("[DB] All data collections cleared successfully from MongoDB.", flush=True)
        except Exception as e:
            print(f"[DB Error] Failed to clear MongoDB collections: {e}", flush=True)
