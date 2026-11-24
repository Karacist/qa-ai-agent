import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import threading
import random
from typing import Dict, Any, List, Optional, Callable

def run_load_test(
    target_url: str,
    num_users: int = 10,
    duration_seconds: int = 15,
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Runs a high-performance concurrent load test using a ThreadPoolExecutor.
    Simulates concurrent virtual users hitting the target URL and streams live stats.
    """
    print(f"\n[Load Tester] Starting stress test on {target_url}...", flush=True)
    print(f"[Load Tester] Concurrency: {num_users} VU | Duration: {duration_seconds}s", flush=True)

    # Clean URL
    parsed_target = urllib.parse.urlparse(target_url)
    if not parsed_target.scheme:
        target_url = "http://" + target_url

    # Shared thread-safe metrics accumulator
    metrics_lock = threading.Lock()
    stats = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "status_codes": {},
        "latencies": [],
        "current_second_requests": 0,
        "current_second_latencies": [],
        "recent_hits": []  # List of dicts representing recent request logs
    }

    stop_event = threading.Event()
    start_time = time.time()

    # User Agent list to simulate realistic traffic
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 QA-Agent-Stress/1.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15 QA-Agent-Stress/1.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0 QA-Agent-Stress/1.0"
    ]

    def worker_loop(worker_id: int):
        while not stop_event.is_set():
            # Respect duration
            if time.time() - start_time >= duration_seconds:
                break

            req_url = target_url
            # Add a cache-busting query param or hit random subpaths occasionally to simulate crawling
            # but keep it simple to ensure hitting the server
            if random.random() < 0.3:
                req_url = f"{target_url}{'' if target_url.endswith('/') else '/'}?qa_stress_vu={worker_id}&cb={random.randint(1000, 9999)}"

            req_start = time.time()
            status_code = 0
            err_msg = ""
            
            try:
                req = urllib.request.Request(
                    req_url,
                    headers={
                        "User-Agent": random.choice(USER_AGENTS),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    status_code = response.getcode()
            except urllib.error.HTTPError as e:
                status_code = e.code
                err_msg = str(e.reason)
            except Exception as e:
                status_code = 599  # Custom code for network failure / timeout
                err_msg = str(e)

            req_end = time.time()
            latency_ms = int((req_end - req_start) * 1000)

            # Record metrics securely
            with metrics_lock:
                stats["total_requests"] += 1
                stats["current_second_requests"] += 1
                stats["current_second_latencies"].append(latency_ms)
                stats["latencies"].append(latency_ms)
                
                is_success = 200 <= status_code < 400
                if is_success:
                    stats["successful_requests"] += 1
                else:
                    stats["failed_requests"] += 1

                stats["status_codes"][status_code] = stats["status_codes"].get(status_code, 0) + 1

                # Keep only last 12 recent hits for frontend display
                log_entry = {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "user": f"VU #{worker_id}",
                    "url": urllib.parse.urlparse(req_url).path or "/",
                    "status": status_code,
                    "success": is_success,
                    "latency": latency_ms,
                    "error": err_msg[:40] if err_msg else None
                }
                stats["recent_hits"].insert(0, log_entry)
                if len(stats["recent_hits"]) > 12:
                    stats["recent_hits"].pop()

            # Think-time sleep between 100ms and 500ms to simulate a realistic virtual user activity
            time.sleep(random.uniform(0.1, 0.5))

    # Spawn thread pool
    executor = ThreadPoolExecutor(max_workers=num_users)
    futures = [executor.submit(worker_loop, i + 1) for i in range(num_users)]

    # Main thread streams stats every second
    ticks = []
    last_tick_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        time.sleep(1.0)
        elapsed = time.time() - start_time
        if elapsed >= duration_seconds:
            break

        # Calculate current pulse metrics
        with metrics_lock:
            cur_reqs = stats["current_second_requests"]
            cur_lats = stats["current_second_latencies"]
            
            # Reset current second accumulators
            stats["current_second_requests"] = 0
            stats["current_second_latencies"] = []
            
            avg_lat = int(sum(cur_lats) / len(cur_lats)) if cur_lats else 0
            success_rate = (stats["successful_requests"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 100
            
            pulse = {
                "elapsed": round(elapsed, 1),
                "progress_percent": min(100, int((elapsed / duration_seconds) * 100)),
                "rps": cur_reqs,
                "latency_ms": avg_lat,
                "total_requests": stats["total_requests"],
                "success_rate": round(success_rate, 1),
                "recent_hits": list(stats["recent_hits"])
            }
            ticks.append(pulse)

        if progress_cb:
            try:
                progress_cb(pulse)
            except Exception as e:
                print(f"[Load Tester Warning] Failed to stream progress: {e}", flush=True)

    # Stop all worker threads safely
    stop_event.set()
    executor.shutdown(wait=True)

    # Compile final metrics report
    total_elapsed = time.time() - start_time
    total_reqs = stats["total_requests"]
    successes = stats["successful_requests"]
    failures = stats["failed_requests"]
    all_latencies = stats["latencies"]
    
    avg_latency = int(sum(all_latencies) / len(all_latencies)) if all_latencies else 0
    max_latency = max(all_latencies) if all_latencies else 0
    min_latency = min(all_latencies) if all_latencies else 0
    
    # Calculate Latency Percentiles (P95, P99)
    sorted_lats = sorted(all_latencies)
    p95 = sorted_lats[int(len(sorted_lats) * 0.95)] if sorted_lats else 0
    p99 = sorted_lats[int(len(sorted_lats) * 0.99)] if sorted_lats else 0

    success_rate = (successes / total_reqs * 100) if total_reqs > 0 else 100
    avg_rps = round(total_reqs / total_elapsed, 1) if total_elapsed > 0 else 0

    # Determine Capacity Score & AI Recommendation based on performance
    score = 100
    # Penalize based on average latency
    if avg_latency > 2000:
        score -= 30
    elif avg_latency > 1000:
        score -= 15
    elif avg_latency > 500:
        score -= 5
        
    # Penalize based on success rate
    score -= int((100 - success_rate) * 1.5)
    score = max(0, min(100, score))

    # Grade
    if score >= 90:
        grade = "A+ (Excellent)"
        advice = "The server handles traffic outstandingly with sub-second response times and zero bottlenecks. Recommended actions: None needed."
    elif score >= 75:
        grade = "B (Good)"
        advice = "The server remains stable but shows moderate latency spikes. Recommended actions: Optimize DB index queries and enable static content compression (Gzip/Brotli)."
    elif score >= 50:
        grade = "C (Fair)"
        advice = "Significant latency degradation and minor connection dropouts. Recommended actions: Implement server caching layers (Redis), scale resources (RAM/CPU), and rate limit repetitive crawls."
    else:
        grade = "D (Poor/Unstable)"
        advice = "The server is buckling under stress. Extreme latencies and high HTTP error rates detected. Recommended actions: Implement severe rate-limiting, optimize SQL/NoSQL structures, and load balance incoming requests across multiple containers."

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_url": target_url,
        "concurrency": num_users,
        "duration": duration_seconds,
        "total_requests": total_reqs,
        "successful_requests": successes,
        "failed_requests": failures,
        "success_rate": round(success_rate, 1),
        "avg_rps": avg_rps,
        "avg_latency_ms": avg_latency,
        "min_latency_ms": min_latency,
        "max_latency_ms": max_latency,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "status_code_distribution": stats["status_codes"],
        "performance_score": score,
        "performance_grade": grade,
        "ai_recommendation": advice,
        "ticks": ticks  # Retained for graphing history
    }

    print(f"[Load Tester Done] Concurrency completed. Total Req: {total_reqs} | Avg Latency: {avg_latency}ms | Score: {score}", flush=True)
    return report
