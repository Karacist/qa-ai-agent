import { useEffect, useMemo, useRef, useState } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";

function srcUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${BACKEND_URL}${clean}`;
}

// ── Constants & Visual Mappings ───────────────────────────────────────────────
const TABS = [
  { id: "overview", label: "Overview", icon: "dashboard" },
  { id: "live", label: "Live", icon: "videocam" },
  { id: "tests", label: "Tests", icon: "rule", countKey: "tests" },
  { id: "remediation", label: "AI Auto-Fix", icon: "magic_button" },
  { id: "load-test", label: "Load Testing", icon: "speed" },
  { id: "plan", label: "Plan", icon: "assignment" },
  { id: "regression", label: "Regression", icon: "compare" },
];

const TYPE_ICONS = {
  functional: "bolt",
  negative: "cancel",
  navigation: "arrow_forward",
  form_validation: "check_box_outline_blank",
  accessibility: "visibility",
  performance: "speed",
  mobile: "smartphone",
};

const RISK_ORDER = ["critical", "high", "medium", "low"];

// ── Helpers ──────────────────────────────────────────────────────────────────
function passRate(pass, total) {
  if (!total) return 0;
  return Math.round((pass / total) * 100);
}

function feedIcon(type, status) {
  if (type === "crawl") return "search";
  if (type === "generate") return "psychology";
  if (type === "test_result") return status === "pass" ? "check_circle" : "cancel";
  if (type === "complete") return "flag";
  if (type === "error") return "warning";
  return "play_arrow";
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

// ── Sub-Components ───────────────────────────────────────────────────────────

function TestCard({ result, onScreenshot }) {
  const [expanded, setExpanded] = useState(false);
  const stepResults = result.step_results || [];
  const stepsPassed = stepResults.filter(s => s.status === "pass").length;
  const stepsTotal = stepResults.length;
  const pct = stepsTotal ? Math.round((stepsPassed / stepsTotal) * 100) : 0;
  const barClass = stepsPassed === stepsTotal ? "pass" : "fail";

  return (
    <div
      className={`test-card ${result.status} reveal ${expanded ? "expanded" : ""}`}
      style={{ cursor: "pointer", transition: "all 0.3s ease" }}
      onClick={() => setExpanded(e => !e)}
    >
      <div className="test-card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <div className={`test-status-icon ${result.status}`}>
            <span className="material-symbols-outlined">
              {result.status === "pass" ? "check_circle" : result.status === "fail" ? "cancel" : "pending"}
            </span>
          </div>
          <div className="test-card-meta">
            <div className="test-card-name" title={result.test_name}>{result.test_name}</div>
            <div className="test-card-id">{result.test_id}</div>
          </div>
        </div>
        <div className="expand-indicator" style={{ color: "var(--outline)", display: "flex", alignItems: "center" }}>
          <span className="material-symbols-outlined">
            {expanded ? "expand_less" : "expand_more"}
          </span>
        </div>
      </div>

      <div className="test-badges">
        {result.test_type && (
          <span className={`badge ${result.test_type}`}>
            <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
              {TYPE_ICONS[result.test_type] || "radio_button_checked"}
            </span>
            {result.test_type.replace("_", " ")}
          </span>
        )}
        {result.risk_level && (
          <span className={`badge ${result.risk_level}`}>{result.risk_level}</span>
        )}
        {result.mobile && (
          <span className="badge mobile">
            <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>smartphone</span>
            mobile
          </span>
        )}
      </div>

      {result.page_url && (
        <div className="test-card-url" title={result.page_url} style={{ paddingBottom: expanded ? "12px" : "16px" }}>
          {result.page_url}
        </div>
      )}

      {expanded && (
        <div
          className="test-card-details"
          onClick={(e) => e.stopPropagation()}
          style={{
            padding: "0 16px 16px",
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            borderTop: "1px solid var(--outline-variant)",
            paddingTop: "16px",
            marginTop: "4px"
          }}
        >
          {/* Detailed Failure Box */}
          {result.status === "fail" && (
            <div
              className="failure-details-box"
              style={{
                background: "rgba(211, 47, 47, 0.05)",
                border: "1px solid rgba(211, 47, 47, 0.2)",
                borderRadius: "8px",
                padding: "12px"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--fail)", fontWeight: "600", fontSize: "13px", marginBottom: "6px" }}>
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>warning</span>
                <span>Why it Failed:</span>
              </div>
              <div
                className="test-error"
                style={{
                  margin: 0,
                  padding: 0,
                  border: "none",
                  background: "none",
                  color: "var(--on-surface)",
                  fontSize: "12px",
                  fontFamily: "var(--font-mono)",
                  maxHeight: "150px",
                  overflowY: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-all"
                }}
              >
                {result.error || "Unknown end-to-end execution timeout or element mismatch."}
              </div>
            </div>
          )}

          {/* Steps Progress */}
          {stepsTotal > 0 && (
            <div className="step-progress" style={{ margin: 0 }}>
              <span>{stepsPassed}/{stepsTotal} steps passed</span>
              <div className="step-bar">
                <div className={`step-bar-fill ${barClass}`} style={{ width: `${pct}%` }} />
              </div>
              <span>{pct}%</span>
            </div>
          )}

          {/* Execution steps */}
          {stepResults.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "var(--outline)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Step Execution Log:
              </div>
              <div className="steps-list" style={{ margin: 0, background: "var(--surface-container-low)" }}>
                {stepResults.map((s, i) => (
                  <div key={i} className={`step-row ${s.status}`} style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "4px", padding: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
                        {s.status === "pass" ? "check_circle" : "cancel"}
                      </span>
                      <span style={{ fontWeight: "500" }}>{s.description || s.action}</span>
                    </div>
                    {s.error && (
                      <div
                        style={{
                          opacity: 0.9,
                          fontSize: "10px",
                          color: "var(--fail)",
                          paddingLeft: "20px",
                          fontFamily: "var(--font-mono)",
                          wordBreak: "break-word"
                        }}
                      >
                        Error: {s.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Screenshot (Minimized by default, clickable to view lightbox) */}
          {result.screenshot && (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ fontSize: "11px", fontWeight: "700", color: "var(--outline)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Execution Screenshot (Click to zoom):
              </div>
              <img
                className="test-screenshot"
                src={srcUrl(result.screenshot)}
                alt="screenshot"
                loading="lazy"
                style={{
                  maxHeight: "180px",
                  width: "100%",
                  objectFit: "contain",
                  borderRadius: "8px",
                  border: "1px solid var(--outline-variant)",
                  background: "var(--surface-container-low)"
                }}
                onClick={() => onScreenshot(srcUrl(result.screenshot))}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatsGrid({ results }) {
  const total = results.length;
  const pass = results.filter(r => r.status === "pass").length;
  const fail = results.filter(r => r.status === "fail").length;
  const rate = passRate(pass, total);

  return (
    <div className="stats-grid reveal">
      <div className="stat-card total">
        <div className="stat-label">Total Tests</div>
        <div className="stat-value">{total}</div>
        <div className="stat-sub">{results.filter(r => r.mobile).length} mobile variants</div>
      </div>
      <div className="stat-card pass">
        <div className="stat-label">Passed</div>
        <div className="stat-value">{pass}</div>
        <div className="stat-sub">{rate}% pass rate</div>
      </div>
      <div className="stat-card fail">
        <div className="stat-label">Failed</div>
        <div className="stat-value">{fail}</div>
        <div className="stat-sub">
          {results.filter(r => r.status === "fail" && r.risk_level === "critical").length} critical
        </div>
      </div>
      <div className="stat-card rate">
        <div className="stat-label">Pass Rate</div>
        <div className="stat-value">{rate}%</div>
        <div className="stat-sub">{total - pass - fail} pending</div>
      </div>
    </div>
  );
}

function BreakdownSection({ results }) {
  const byType = useMemo(() => {
    const m = {};
    for (const r of results) {
      const t = r.test_type || "unknown";
      if (!m[t]) m[t] = { pass: 0, fail: 0 };
      m[t][r.status] = (m[t][r.status] || 0) + 1;
    }
    return m;
  }, [results]);

  const byRisk = useMemo(() => {
    const m = {};
    for (const r of results) {
      const k = r.risk_level || "unknown";
      if (!m[k]) m[k] = { pass: 0, fail: 0 };
      m[k][r.status] = (m[k][r.status] || 0) + 1;
    }
    return m;
  }, [results]);

  const renderRows = (data, keys) =>
    keys.filter(k => data[k]).map(k => {
      const { pass = 0, fail = 0 } = data[k];
      const tot = pass + fail;
      const pct = passRate(pass, tot);
      const barCls = fail === 0 ? "pass" : pass === 0 ? "fail" : "mixed";
      return (
        <div key={k} className="breakdown-row">
          <span className="breakdown-name">{k.replace("_", " ")}</span>
          <div className="breakdown-bar-wrap">
            <div className={`breakdown-bar ${barCls}`} style={{ width: `${pct}%` }} />
          </div>
          <span className="breakdown-nums">{pass}/{tot}</span>
        </div>
      );
    });

  const typeKeys = Object.keys(byType).sort();
  const riskKeys = RISK_ORDER.filter(k => byRisk[k]);

  if (!results.length) return null;

  return (
    <div className="breakdown-grid reveal delay-1">
      <div className="breakdown-card">
        <div className="breakdown-title">By Test Type</div>
        {renderRows(byType, typeKeys)}
      </div>
      <div className="breakdown-card">
        <div className="breakdown-title">By Risk Level</div>
        {renderRows(byRisk, riskKeys)}
      </div>
    </div>
  );
}

function TestPlanView({ plan }) {
  if (!plan) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <span className="material-symbols-outlined" style={{ fontSize: "48px" }}>assignment</span>
        </div>
        <div className="empty-title">No test plan yet</div>
        <div className="empty-desc">Run the pipeline to generate an AI test plan.</div>
      </div>
    );
  }

  return (
    <div className="plan-card reveal">
      <div className="plan-header">
        <div className="plan-title">AI-Generated Test Plan</div>
      </div>

      {plan.app_summary && (
        <div className="plan-summary">{plan.app_summary}</div>
      )}

      {plan.critical_flows?.length > 0 && (
        <div className="plan-section">
          <div className="plan-section-title">Critical User Flows</div>
          <div className="plan-list">
            {plan.critical_flows.map((f, i) => (
              <div key={i} className="plan-list-item">{f}</div>
            ))}
          </div>
        </div>
      )}

      {plan.risk_areas?.length > 0 && (
        <div className="plan-section">
          <div className="plan-section-title">Risk Areas</div>
          <div className="plan-list">
            {plan.risk_areas.map((r, i) => (
              <div key={i} className="plan-list-item">{r}</div>
            ))}
          </div>
        </div>
      )}

      {plan.test_categories?.length > 0 && (
        <div className="plan-section">
          <div className="plan-section-title">Test Coverage</div>
          <div className="plan-tags">
            {plan.test_categories.map((c, i) => (
              <span key={i} className={`badge ${c}`}>
                <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
                  {TYPE_ICONS[c] || "radio_button_checked"}
                </span>
                {c.replace("_", " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      {(plan.auth_required !== undefined || plan.has_forms !== undefined) && (
        <div className="plan-section">
          <div className="plan-section-title">App Characteristics</div>
          <div className="plan-tags">
            {plan.auth_required && (
              <span className="badge high">
                <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>lock</span>
                auth required
              </span>
            )}
            {plan.has_forms && (
              <span className="badge form_validation">
                <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>check_box_outline_blank</span>
                has forms
              </span>
            )}
            {plan.auth_required === false && (
              <span className="badge low">
                <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>public</span>
                public app
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RegressionView({ regression, history }) {
  if (!regression || regression.is_first_run) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <span className="material-symbols-outlined" style={{ fontSize: "48px" }}>compare</span>
        </div>
        <div className="empty-title">No regression data yet</div>
        <div className="empty-desc">Run the pipeline at least twice to see regression comparisons.</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }} className="reveal">
      <div className="regression-grid">
        <div className={`reg-card ${regression.new_failures.length > 0 ? "alert" : "stable"}`}>
          <div className="reg-label">New Failures</div>
          <div className="reg-value">{regression.new_failures.length}</div>
          {regression.new_failures.length > 0 && (
            <div className="reg-ids">
              {regression.new_failures.map(id => <span key={id} className="reg-id-tag">{id}</span>)}
            </div>
          )}
        </div>
        <div className={`reg-card ${regression.fixed.length > 0 ? "good" : "stable"}`}>
          <div className="reg-label">Fixed</div>
          <div className="reg-value">{regression.fixed.length}</div>
          {regression.fixed.length > 0 && (
            <div className="reg-ids">
              {regression.fixed.map(id => <span key={id} className="reg-id-tag">{id}</span>)}
            </div>
          )}
        </div>
        <div className={`reg-card ${regression.stable_failures.length > 0 ? "alert" : "good"}`}>
          <div className="reg-label">Stable Failures</div>
          <div className="reg-value">{regression.stable_failures.length}</div>
        </div>
        <div className="reg-card info">
          <div className="reg-label">Prev Pass Rate</div>
          <div className="reg-value">
            {regression.previous_pass_rate != null ? `${regression.previous_pass_rate}%` : "—"}
          </div>
        </div>
      </div>

      {history.length > 0 && (
        <div className="history-table">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>URL</th>
                <th>Tests</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>Pass Rate</th>
              </tr>
            </thead>
            <tbody>
              {[...history].reverse().slice(0, 15).map((run, i) => (
                <tr key={i}>
                  <td style={{ color: "var(--outline)", fontFamily: "var(--font-mono)" }}>
                    {timeAgo(run.timestamp)}
                  </td>
                  <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {run.url}
                  </td>
                  <td>{run.total}</td>
                  <td style={{ color: "var(--pass)", fontWeight: "600" }}>{run.passed}</td>
                  <td style={{ color: run.failed > 0 ? "var(--fail)" : "var(--outline)", fontWeight: run.failed > 0 ? "600" : "normal" }}>
                    {run.failed}
                  </td>
                  <td>
                    <span style={{
                      fontWeight: "600",
                      color: run.pass_rate >= 80 ? "var(--pass)" : run.pass_rate >= 50 ? "var(--warn)" : "var(--fail)"
                    }}>
                      {run.pass_rate}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Live Browser View ────────────────────────────────────────────────────────

function LiveView({ frame, running, feedEvents = [] }) {
  const imgRef = useRef(null);
  const [scaledCursor, setScaledCursor] = useState(null);
  const [imgLoaded, setImgLoaded] = useState(false);

  let waitingMessage = "Waiting for browser to initialize…";
  if (running && !frame) {
    const latestEvent = feedEvents[feedEvents.length - 1];
    if (latestEvent) {
      const msg = latestEvent.message || "";
      const type = latestEvent.type || "";
      if (type === "crawl") {
        waitingMessage = "Phase 1/3: Crawling site structure…";
      } else if (type === "generate") {
        waitingMessage = "Phase 2/3: Generating test plan with LLM…";
      } else {
        waitingMessage = msg || "Phase 3/3: Initializing Playwright browser…";
      }
    }
  }

  useEffect(() => {
    setImgLoaded(false);
  }, [frame?.img]);

  useEffect(() => {
    if (frame?.cursor_x == null || frame?.cursor_y == null || !imgRef.current || !imgLoaded) {
      setScaledCursor(null);
      return;
    }
    const img = imgRef.current;
    const nW = img.naturalWidth || 1280;
    const nH = img.naturalHeight || 720;
    const dW = img.clientWidth;
    const dH = img.clientHeight;
    if (!dW || !dH) { setScaledCursor(null); return; }
    setScaledCursor({
      x: (frame.cursor_x / nW) * dW,
      y: (frame.cursor_y / nH) * dH,
    });
  }, [frame, imgLoaded]);

  const ACTION_ICONS = {
    goto: "travel_explore", click: "touch_app", fill: "keyboard",
    hover: "mouse", scroll: "swap_vert", press: "keyboard_return",
    check: "check_box", select_option: "list",
    assert_visible: "visibility", assert_text: "fact_check",
    assert_url: "link", assert_title: "title",
  };
  const actionIcon = ACTION_ICONS[frame?.action_type] || "smart_toy";

  if (!running && !frame) {
    return (
      <div className="live-empty-state">
        <span className="material-symbols-outlined" style={{ fontSize: 56 }}>videocam_off</span>
        <div className="live-empty-title">Live view not active</div>
        <div className="live-empty-desc">
          Start a pipeline run to watch Playwright test execution live — with cursor movement, clicks, and form fills.
        </div>
      </div>
    );
  }

  return (
    <div className="live-view-wrap reveal">
      {/* Browser chrome bar */}
      <div className="live-browser-chrome">
        <div className="chrome-dots">
          <span className="chrome-dot chrome-red" />
          <span className="chrome-dot chrome-yellow" />
          <span className="chrome-dot chrome-green" />
        </div>
        <div className="chrome-url-bar">
          <span className="material-symbols-outlined" style={{ fontSize: 13 }}>lock</span>
          <span className="chrome-url-text">{frame?.page_url || "Initializing…"}</span>
        </div>
        <div className="chrome-live-badge">
          <div className="rec-dot" />
          LIVE
        </div>
      </div>

      {/* Viewport */}
      <div className="live-viewport">
        {frame ? (
          <div className="live-img-wrap">
            <img
              ref={imgRef}
              src={`data:image/jpeg;base64,${frame.img}`}
              className="live-screenshot-img"
              alt="live browser"
              onLoad={() => setImgLoaded(true)}
            />
            {scaledCursor && (
              <div
                className="live-cursor-wrap"
                style={{ left: scaledCursor.x, top: scaledCursor.y }}
              >
                <svg width="18" height="22" viewBox="0 0 18 22">
                  <path
                    d="M 1 1 L 1 17 L 5 13 L 8 21 L 11 20 L 8 12 L 13 12 Z"
                    fill="white" stroke="#1a1a2e" strokeWidth="1.5" strokeLinejoin="round"
                  />
                </svg>
                {frame.action_type === "click" && <div className="click-ring" />}
              </div>
            )}
          </div>
        ) : (
          <div className="live-waiting">
            <div className="live-spinner" />
            <span>{waitingMessage}</span>
          </div>
        )}
      </div>

      {/* Action bar */}
      <div className="live-action-bar">
        <div className="live-action-left">
          <span className="live-action-icon material-symbols-outlined">{actionIcon}</span>
          <span className="live-action-text">{frame?.action || "—"}</span>
        </div>
        {frame?.test_name && (
          <div className="live-action-right">
            <span className="live-test-chip">{frame.test_name}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  // run config
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState("10");
  const [browsers, setBrowsers] = useState(["chromium"]);
  const [mobile, setMobile] = useState(true);

  // run state
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);

  // live feed
  const [feedEvents, setFeedEvents] = useState([]);
  const feedRef = useRef(null);

  // data
  const [results, setResults] = useState([]);
  const [testPlan, setTestPlan] = useState(null);
  const [regression, setRegression] = useState(null);
  const [history, setHistory] = useState([]);
  const [diagnostics, setDiagnostics] = useState(null);

  // live view
  const [liveFrame, setLiveFrame] = useState(null);
  const liveAutoSwitched = useRef(false);

  // ui
  const [tab, setTab] = useState("overview");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterType, setFilterType] = useState("all");
  const [filterRisk, setFilterRisk] = useState("all");
  const [lightbox, setLightbox] = useState(null);
  const [dialog, setDialog] = useState(null); // { type, title, message, onConfirm, onCancel, isError }

  const [testedUrls, setTestedUrls] = useState([]);

  // load test state
  const [loadUsers, setLoadUsers] = useState(20);
  const [loadDuration, setLoadDuration] = useState(15);
  const [loadRunning, setLoadRunning] = useState(false);
  const [loadMetrics, setLoadMetrics] = useState(null);
  const [loadHistory, setLoadHistory] = useState([]);
  const [loadReport, setLoadReport] = useState(null);
  const [loadError, setLoadError] = useState(null);

  // load existing data on mount
  useEffect(() => {
    loadTestedUrls();
  }, []);

  async function loadTestedUrls() {
    try {
      const res = await fetch(`${BACKEND_URL}/api/urls`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setTestedUrls(data);
          // Only auto-select default if no URL is currently active
          if (!url && data.length > 0) {
            const defaultUrl = data[0].url;
            setUrl(defaultUrl);
            loadDataForUrl(defaultUrl);
          } else if (url) {
            loadDataForUrl(url);
          } else {
            loadDataForUrl("");
          }
        }
      }
    } catch (_) {
      loadDataForUrl("");
    }
  }

  function loadDataForUrl(targetUrl) {
    fetchResults(targetUrl);
    fetchPlan(targetUrl);
    fetchHistory(targetUrl);
    fetchDiagnostics(targetUrl);
    fetchLoadTest(targetUrl);
  }

  async function fetchLoadTest(targetUrl) {
    try {
      const u = targetUrl !== undefined ? targetUrl : url;
      const fetchUrl = `${BACKEND_URL}/api/load-test/results` + (u ? `?url=${encodeURIComponent(u)}` : "");
      const res = await fetch(fetchUrl);
      if (res.ok) {
        const data = await res.json();
        setLoadReport(data);
        if (data.ticks) {
          setLoadHistory(data.ticks);
        }
      } else {
        setLoadReport(null);
        setLoadHistory([]);
      }
    } catch (_) {
      setLoadReport(null);
      setLoadHistory([]);
    }
  }

  async function startLoadTest() {
    const trimmed = url.trim();
    if (!trimmed) { setLoadError("Please select or enter a URL first."); return; }
    setLoadError(null);
    setLoadRunning(true);
    setLoadMetrics(null);
    setLoadHistory([]);
    setLoadReport(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/load-test/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: trimmed,
          users: loadUsers,
          duration: loadDuration
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Failed to start load test");
      connectLoadTestSSE(body.run_id);
    } catch (err) {
      setLoadError(err.message);
      setLoadRunning(false);
    }
  }

  function connectLoadTestSSE(id) {
    if (esRef.current) esRef.current.close();
    const es = new EventSource(`${BACKEND_URL}/api/events?run_id=${id}`);
    esRef.current = es;

    es.onmessage = (e) => {
      let evt;
      try { evt = JSON.parse(e.data); } catch { return; }

      if (evt.type === "heartbeat") return;

      if (evt.type === "load_test_pulse" && evt.data) {
        const pulse = evt.data;
        setLoadMetrics(pulse);
        setLoadHistory(prev => [...prev, pulse]);
        return;
      }

      if (evt.type === "complete") {
        setLoadReport(evt.report || null);
        setLoadRunning(false);
        es.close();
        loadTestedUrls();
      }

      if (evt.type === "error") {
        setLoadError(evt.message || "Load test failed");
        setLoadRunning(false);
        es.close();
      }
    };

    es.onerror = () => {
      if (loadRunning) setLoadError("Lost connection to server.");
      setLoadRunning(false);
      es.close();
    };
  }

  async function fetchResults(targetUrl) {
    try {
      const u = targetUrl !== undefined ? targetUrl : url;
      const casesUrl = `${BACKEND_URL}/reports/test_cases.json` + (u ? `?url=${encodeURIComponent(u)}` : "");
      const resUrl = `${BACKEND_URL}/reports/test_results.json` + (u ? `?url=${encodeURIComponent(u)}` : "");
      
      const [cases, res] = await Promise.all([
        fetch(casesUrl).then(r => r.ok ? r.json() : []).catch(() => []),
        fetch(resUrl).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      if (res && Array.isArray(res)) {
        setResults(res);
      } else if (Array.isArray(cases) && cases.length) {
        setResults(cases.map(tc => ({ ...tc, status: "pending" })));
      } else {
        setResults([]);
      }
    } catch (_) {
      setResults([]);
    }
  }

  async function fetchPlan(targetUrl) {
    try {
      const u = targetUrl !== undefined ? targetUrl : url;
      const fetchUrl = `${BACKEND_URL}/api/plan` + (u ? `?url=${encodeURIComponent(u)}` : "");
      const p = await fetch(fetchUrl).then(r => r.ok ? r.json() : null).catch(() => null);
      setTestPlan(p);
    } catch (_) {
      setTestPlan(null);
    }
  }

  async function fetchHistory(targetUrl) {
    try {
      const u = targetUrl !== undefined ? targetUrl : url;
      const fetchUrl = `${BACKEND_URL}/api/history` + (u ? `?url=${encodeURIComponent(u)}` : "");
      const h = await fetch(fetchUrl).then(r => r.ok ? r.json() : []).catch(() => []);
      setHistory(Array.isArray(h) ? h : []);
    } catch (_) {
      setHistory([]);
    }
  }

  async function fetchDiagnostics(targetUrl) {
    try {
      const u = targetUrl !== undefined ? targetUrl : url;
      const fetchUrl = `${BACKEND_URL}/api/diagnostics` + (u ? `?url=${encodeURIComponent(u)}` : "");
      const d = await fetch(fetchUrl).then(r => r.ok ? r.json() : null).catch(() => null);
      setDiagnostics(d);
    } catch (_) {
      setDiagnostics(null);
    }
  }

  // SSE connection
  const esRef = useRef(null);

  function connectSSE(id) {
    if (esRef.current) esRef.current.close();
    const es = new EventSource(`${BACKEND_URL}/api/events?run_id=${id}`);
    esRef.current = es;

    es.onmessage = (e) => {
      let evt;
      try { evt = JSON.parse(e.data); } catch { return; }

      if (evt.type === "heartbeat") return;

      if (evt.type === "frame") {
        setLiveFrame({
          img: evt.img, action: evt.action, action_type: evt.action_type,
          cursor_x: evt.cursor_x, cursor_y: evt.cursor_y,
          test_id: evt.test_id, test_name: evt.test_name, page_url: evt.page_url,
        });
        if (!liveAutoSwitched.current) {
          liveAutoSwitched.current = true;
          setTab("live");
        }
        return;
      }

      setFeedEvents(prev => [...prev.slice(-150), evt]);

      if (evt.type === "test_result") {
        setResults(prev => {
          const idx = prev.findIndex(r => r.test_id === evt.test_id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = evt;
            return next;
          }
          return [...prev, evt];
        });
      }

      if (evt.type === "complete") {
        setResults(evt.results || []);
        setRegression(evt.regression || null);
        setRunning(false);
        es.close();
        fetchPlan();
        fetchHistory();
        fetchDiagnostics();
        loadTestedUrls();

        // Auto-switch to AI Auto-Fix tab if there are failed tests
        const hasFailures = (evt.results || []).some(r => r.status === "fail");
        if (hasFailures) {
          setTab("remediation");
        } else {
          setTab("tests");
        }
      }

      if (evt.type === "error") {
        setRunError(evt.message || "Run failed");
        setRunning(false);
        es.close();
      }
    };

    es.onerror = () => {
      if (running) setRunError("Lost connection to server.");
      setRunning(false);
      es.close();
    };
  }

  // scroll feed to bottom
  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [feedEvents]);

  // start run
  async function startRun() {
    const trimmed = url.trim();
    if (!trimmed) { setRunError("Please enter a URL."); return; }
    setRunError(null);
    setRunning(true);
    setFeedEvents([]);
    setResults([]);
    setTestPlan(null);
    setRegression(null);
    setLiveFrame(null);
    liveAutoSwitched.current = false;
    setTab("overview");

    try {
      const res = await fetch(`${BACKEND_URL}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: trimmed,
          max_pages: Math.max(1, Math.min(parseInt(maxPages) || 10, 50)),
          browsers,
          mobile,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Failed to start run");
      connectSSE(body.run_id);
    } catch (err) {
      setRunError(err.message);
      setRunning(false);
    }
  }

  // derived data
  const filteredResults = useMemo(() => {
    return results.filter(r => {
      if (filterStatus !== "all" && r.status !== filterStatus) return false;
      if (filterType !== "all" && r.test_type !== filterType) return false;
      if (filterRisk !== "all" && r.risk_level !== filterRisk) return false;
      return true;
    });
  }, [results, filterStatus, filterType, filterRisk]);

  const types = useMemo(() => [...new Set(results.map(r => r.test_type).filter(Boolean))], [results]);
  const risks = useMemo(() => RISK_ORDER.filter(r => results.some(t => t.risk_level === r)), [results]);

  const runStatus = running ? "running" : runError ? "error" : results.length > 0 ? "done" : "idle";
  const statusLabel = { idle: "Idle", running: "Running…", done: "Complete", error: "Error" }[runStatus];

  function toggleBrowser(b) {
    setBrowsers(prev =>
      prev.includes(b) ? (prev.length > 1 ? prev.filter(x => x !== b) : prev) : [...prev, b]
    );
  }

  return (
    <div className="app">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-brand">
          <div className="brand-icon">
            <span className="material-symbols-outlined">precision_manufacturing</span>
          </div>
          <div>
            <div className="brand-name">QA Agent</div>
          </div>
        </div>

        <div className="topbar-divider" />

        <nav className="topbar-tabs">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn ${tab === t.id ? "active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>{t.icon}</span>
              {t.label}
              {t.id === "live" && running && <div className="live-tab-rec" />}
              {t.countKey === "tests" && results.length > 0 && (
                <span className="tab-count">{results.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="topbar-right">
          <div className={`status-badge ${runStatus}`}>
            <div className="status-dot" />
            {statusLabel}
          </div>
          <button className="topbar-settings-btn">
            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>settings</span>
          </button>
          <div className="user-avatar">
            <img alt="User Avatar" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBS7wmZ8fbc5SzCPT4f7agoMljYsmXzpIlzVIkh6zsEKHgGp8r6MfK9QjKUQG4z860S702IY9rwfA1-CSQn3erHZJNgYMjCdnTjS5eQJzM4NtbB_L5gYy4KAXXxPJO6s5by1dnT-GbFmIPg9c-eva6Wyz5iFKKiM_AB_RiHeUk3rlS19V950f7Rh_Ocz4CMpmMMAHphEGy5xAotCvQNafS-90330dHJvtDSeWOqKl3MnVUaeF5W3c3rRBgGVht5IB7x5oJhvtd_563-" />
          </div>
        </div>
      </header>

      {/* ── Sidebar ── */}
      <aside className="sidebar">
        {/* Run Panel */}
        <div className="run-panel">
          <div className="panel-title">Run Pipeline</div>

          <div className="input-group">
            <label className="input-label" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Target URL</span>
              {testedUrls.length > 0 && (
                <select
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "var(--primary)",
                    fontSize: "11px",
                    fontWeight: "600",
                    cursor: "pointer",
                    outline: "none",
                    padding: "0"
                  }}
                  onChange={(e) => {
                    const selected = e.target.value;
                    if (selected) {
                      setUrl(selected);
                      loadDataForUrl(selected);
                    }
                  }}
                  value=""
                >
                  <option value="" disabled>History...</option>
                  {testedUrls.map(u => (
                    <option key={u.key} value={u.url}>{u.url}</option>
                  ))}
                </select>
              )}
            </label>
            <input
              className="inp"
              type="text"
              placeholder="https://your-app.com"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !running && startRun()}
            />
          </div>

          <div className="inp-row">
            <div className="input-group">
              <label className="input-label">Max Pages</label>
              <input
                className="inp"
                type="number"
                min="1"
                max="50"
                value={maxPages}
                onChange={e => setMaxPages(e.target.value)}
              />
            </div>
            <div className="input-group" style={{ justifyContent: "flex-end", paddingBottom: "8px" }}>
              <label className="checkbox-row">
                <input type="checkbox" checked={mobile} onChange={e => setMobile(e.target.checked)} />
                Mobile tests
              </label>
            </div>
          </div>



          <div className="run-buttons" style={{ display: "flex", gap: "8px" }}>
            <button className="btn-run hover-pulse" onClick={startRun} disabled={running} style={{ flex: 1 }}>
              <span className="material-symbols-outlined">play_arrow</span>
              {running ? "Running…" : "Run Pipeline"}
            </button>
            {running && (
              <button
                className="btn-stop hover-pulse"
                onClick={async () => {
                  try {
                    const res = await fetch(`${BACKEND_URL}/api/stop`, { method: "POST" });
                    const data = await res.json();
                    if (data.success) {
                      // Instantly report status in UI to feel highly responsive
                      setFeedEvents(prev => [...prev, { type: "error", message: "Stopping pipeline execution..." }]);
                    }
                  } catch (e) {
                    setDialog({
                      type: "alert",
                      title: "Error",
                      message: "Error stopping pipeline: " + e.message,
                      isError: true
                    });
                  }
                }}
                style={{
                  background: "linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%)",
                  border: "none",
                  color: "white",
                  borderRadius: "8px",
                  padding: "0 16px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "13px",
                  transition: "all 0.3s ease",
                  boxShadow: "0 4px 15px rgba(255, 75, 43, 0.3)"
                }}
              >
                <span className="material-symbols-outlined" style={{ marginRight: "4px" }}>stop</span>
                Stop
              </button>
            )}
          </div>

  {
    runError && (
      <div className="run-error" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span>⚠ {runError}</span>
        {runError.includes("already in progress") && (
          <button
            className="btn-reset-lock"
            onClick={async () => {
              try {
                const res = await fetch(`${BACKEND_URL}/api/reset`, { method: "POST" });
                const data = await res.json();
                if (data.success) {
                  setRunError(null);
                } else {
                  setDialog({
                    type: "alert",
                    title: "Error",
                    message: "Failed to release lock: " + data.error,
                    isError: true
                  });
                }
              } catch (e) {
                setDialog({
                  type: "alert",
                  title: "Error",
                  message: "Error releasing lock: " + e.message,
                  isError: true
                });
              }
            }}
            style={{
              marginLeft: "8px",
              background: "rgba(255, 255, 255, 0.2)",
              border: "none",
              color: "white",
              borderRadius: "4px",
              padding: "4px 8px",
              fontSize: "10px",
              fontWeight: "600",
              cursor: "pointer",
              textTransform: "uppercase",
              whiteSpace: "nowrap"
            }}
          >
            Reset Lock
          </button>
        )}
      </div>
    )
  }
        </div >

    <div className="sidebar-divider" />

  {/* Live Feed */ }
  <div className="live-feed">
    <div className="panel-title">Live Feed</div>
    {feedEvents.length === 0 ? (
      <div className="feed-empty">
        {running ? "Waiting for events…" : "Start a run to see live progress."}
      </div>
    ) : (
      <div className="feed-list" ref={feedRef}>
        {feedEvents.map((ev, i) => (
          <div
            key={i}
            className={`feed-item ${ev.type} ${ev.status || ""}`}
          >
            <span className="feed-icon">
              <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                {feedIcon(ev.type, ev.status)}
              </span>
            </span>
            <span className="feed-msg">{ev.message}</span>
          </div>
        ))}
      </div>
    )}
  </div>
      </aside >

    {/* ── Main Content Area ── */ }
    < main className = "main-content" >

      {/* Overview Tab */ }
  {
    tab === "overview" && (
      <>
        {results.length === 0 && !running ? (
          <div className="empty-hero-wrap">
            {/* Glowing Empty State Toy Robot */}
            <div className="toy-glow-container reveal">
              <div className="toy-glow-bg"></div>
              <div className="toy-card animate-float">
                <span className="material-symbols-outlined">smart_toy</span>
              </div>
              <div className="toy-bolt-badge">
                <span className="material-symbols-outlined">bolt</span>
              </div>
            </div>

            <div className="reveal delay-1">
              <h2 className="empty-title">Ready to run</h2>
              <p className="empty-desc">
                Enter a URL in the sidebar and click Run Pipeline to start automated QA testing across multiple devices and browsers.
              </p>
            </div>

            {/* Staggered features list */}
            <div className="empty-features reveal delay-2">
              <div className="feature-indicator">
                <div className="feature-icon-box">
                  <span className="material-symbols-outlined">speed</span>
                </div>
                <span className="feature-label">Fast Analysis</span>
              </div>
              <div className="feature-indicator">
                <div className="feature-icon-box">
                  <span className="material-symbols-outlined">description</span>
                </div>
                <span className="feature-label">Detailed Reports</span>
              </div>
              <div className="feature-indicator">
                <div className="feature-icon-box">
                  <span className="material-symbols-outlined">security</span>
                </div>
                <span className="feature-label">Secure Testing</span>
              </div>
            </div>

            {/* Tip cards */}
            <div className="empty-tips-grid reveal delay-3">
              <div className="tip-card">
                <div className="tip-header">
                  <span className="material-symbols-outlined">history</span>
                  <span className="tip-title">Recent Runs</span>
                </div>
                <p className="tip-text">No previous automation runs detected for this account.</p>
              </div>
              <div className="tip-card">
                <div className="tip-header">
                  <span className="material-symbols-outlined">tips_and_updates</span>
                  <span className="tip-title">Pro Tip</span>
                </div>
                <p className="tip-text">Use regression mode to compare visual diffs between deployments.</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            <StatsGrid results={results} />
            <BreakdownSection results={results} />
          </>
        )}
      </>
    )
  }

  {/* Live View Tab */ }
  {
    tab === "live" && (
      <LiveView frame={liveFrame} running={running} feedEvents={feedEvents} />
    )
  }

  {/* Tests Tab */ }
  {
    tab === "tests" && (
      <>
        <div className="section-header reveal" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="section-title" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span>Test Results</span>
            {results.length > 0 && (
              <button
                className="btn-clear-inline hover-pulse"
                disabled={running}
                onClick={(e) => {
                  e.stopPropagation();
                  setDialog({
                    type: "confirm",
                    title: "Confirm Deletion",
                    message: "Are you sure you want to delete all test cases, plans, and results for this URL? This action is permanent and cannot be undone.",
                    onConfirm: async () => {
                      try {
                        const res = await fetch(`${BACKEND_URL}/api/clear`);
                        const data = await res.json();
                        if (data.success) {
                          setResults([]);
                          setTestPlan(null);
                          setRegression(null);
                          setDiagnostics(null);
                          setHistory([]);
                          setFeedEvents([]);
                          setLiveFrame(null);
                          loadTestedUrls();
                          setDialog({
                            type: "alert",
                            title: "Success",
                            message: data.message || "All cases and history cleared successfully."
                          });
                        } else {
                          setDialog({
                            type: "alert",
                            title: "Error",
                            message: "Failed to clear data: " + data.error,
                            isError: true
                          });
                        }
                      } catch (e) {
                        setDialog({
                          type: "alert",
                          title: "Error",
                          message: "Error clearing data: " + e.message,
                          isError: true
                        });
                      }
                    }
                  });
                }}
                style={{
                  background: "rgba(211, 47, 47, 0.08)",
                  border: "1px solid rgba(211, 47, 47, 0.2)",
                  color: "var(--fail)",
                  borderRadius: "6px",
                  padding: "4px 10px",
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  cursor: running ? "not-allowed" : "pointer",
                  fontWeight: "600",
                  fontSize: "11px",
                  transition: "all 0.2s ease"
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>delete_sweep</span>
                Delete All Cases
              </button>
            )}
          </div>
          <div className="filter-bar">
            {["all", "pass", "fail"].map(s => (
              <button
                key={s}
                className={`filter-chip ${s}-chip ${filterStatus === s ? "active" : ""}`}
                onClick={() => setFilterStatus(s)}
              >
                {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
                {s !== "all" && (
                  <> ({results.filter(r => r.status === s).length})</>
                )}
              </button>
            ))}

            {types.length > 0 && (
              <>
                <div className="filter-sep" />
                <select className="filter-sel" value={filterType} onChange={e => setFilterType(e.target.value)}>
                  <option value="all">All Types</option>
                  {types.map(t => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                </select>
              </>
            )}

            {risks.length > 0 && (
              <select className="filter-sel" value={filterRisk} onChange={e => setFilterRisk(e.target.value)}>
                <option value="all">All Risks</option>
                {risks.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            )}
          </div>
        </div>

        {filteredResults.length === 0 ? (
          <div className="no-results reveal">No tests match the current filter.</div>
        ) : (
          <div className="test-grid">
            {filteredResults.map(r => (
              <TestCard key={r.test_id} result={r} onScreenshot={setLightbox} />
            ))}
          </div>
        )}
      </>
    )
  }

  {/* Plan Tab */ }
  { tab === "plan" && <TestPlanView plan={testPlan} /> }

  {/* AI Auto-Fix Tab */}
  { tab === "remediation" && <AIAutoFixView diagnostics={diagnostics} activeUrl={url} /> }

  {/* Regression Tab */}
  { tab === "regression" && <RegressionView regression={regression} history={history} /> }

  {/* Load Testing Tab */}
  { tab === "load-test" && (
    <LoadTestView
      url={url}
      loadUsers={loadUsers}
      setLoadUsers={setLoadUsers}
      loadDuration={loadDuration}
      setLoadDuration={setLoadDuration}
      loadRunning={loadRunning}
      startLoadTest={startLoadTest}
      loadMetrics={loadMetrics}
      loadHistory={loadHistory}
      loadReport={loadReport}
      loadError={loadError}
    />
  )}
      </main >

    {/* Screenshot Lightbox */}
    {
      lightbox && (
        <div className="lightbox" onClick={() => setLightbox(null)}>
          <img src={lightbox} alt="screenshot" />
        </div>
      )
    }

    {/* Custom dialog/modal */}
    {dialog && (
      <div 
        className="custom-dialog-overlay reveal" 
        onClick={(e) => {
          e.stopPropagation();
          setDialog(null);
        }}
      >
        <div 
          className="custom-dialog-card reveal zoom" 
          onClick={(e) => e.stopPropagation()}
        >
          <div className="custom-dialog-header">
            <span className={`material-symbols-outlined custom-dialog-icon ${dialog.type === "confirm" ? "warn" : dialog.isError ? "fail" : "success"}`}>
              {dialog.type === "confirm" ? "warning" : dialog.isError ? "error" : "check_circle"}
            </span>
            <h4 className="custom-dialog-title">{dialog.title}</h4>
          </div>
          <div className="custom-dialog-body">
            <p>{dialog.message}</p>
          </div>
          <div className="custom-dialog-actions">
            {dialog.type === "confirm" ? (
              <>
                <button 
                  className="btn-dialog-cancel" 
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    dialog.onCancel?.();
                    setDialog(null);
                  }}
                >
                  Cancel
                </button>
                <button 
                  className="btn-dialog-confirm danger" 
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    dialog.onConfirm?.();
                    setDialog(null);
                  }}
                >
                  Confirm Delete
                </button>
              </>
            ) : (
              <button 
                className="btn-dialog-confirm" 
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  dialog.onConfirm?.();
                  setDialog(null);
                }}
              >
                OK
              </button>
            )}
          </div>
        </div>
      </div>
    )}
  </div>
  );
}

function AIAutoFixView({ diagnostics, activeUrl }) {
  const [copiedMaster, setCopiedMaster] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  
  // Chat state
  const [chatMessages, setChatMessages] = useState([
    {
      role: "assistant",
      content: "Hello! I am your AI E2E QA Copilot. I have analyzed your test cases and execution history. Ask me anything about the passed or failed test cases, their specific root causes, or how to resolve them!"
    }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, chatLoading]);

  const copyMaster = () => {
    if (!diagnostics || !diagnostics.recommendations) return;
    navigator.clipboard.writeText(masterPrompt);
    setCopiedMaster(true);
    setTimeout(() => setCopiedMaster(false), 2000);
  };

  const copyIndex = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleSendChat = async () => {
    const query = chatInput.trim();
    if (!query) return;

    // Add user message instantly
    setChatMessages(prev => [...prev, { role: "user", content: query }]);
    setChatInput("");
    setChatLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, url: activeUrl })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages(prev => [...prev, { role: "assistant", content: data.response || "No response received." }]);
      } else {
        const errData = await res.json();
        setChatMessages(prev => [...prev, { role: "assistant", content: `Error: ${errData.error || "Failed to query AI."}` }]);
      }
    } catch (e) {
      setChatMessages(prev => [...prev, { role: "assistant", content: `Network error: ${e.message}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Compile the unified master bug-fixing prompt (safely handling null cases)
  const masterPrompt = diagnostics && diagnostics.recommendations ? `I have a web application with some failing E2E tests. Here are the diagnostics and fix plans generated by our QA Agent. Please review them and automatically modify our codebase to fix these bugs.

SUMMARY OF ISSUES:
${diagnostics.summary}

RECOMMENDATIONS & FIX GUIDES:
${diagnostics.recommendations.map((r, i) => `
---
[${i + 1}] TEST FAILURE: ${r.test_id} - ${r.test_name}
ROOT CAUSE: ${r.root_cause}
PROPOSED FIX ACTION: ${r.fix_action}
SUGGESTED COPILOT REMEDIATION INSTRUCTIONS:
${r.copilot_prompt}
`).join("\n")}

Please locate the affected files and apply the proposed changes immediately to resolve all the failing tests.` : "";

  function formatMarkdown(text) {
    if (!text) return "";
    
    // 1. Escape HTML to prevent XSS
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
      
    // 2. Format code blocks ```...```
    html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
      return `<pre class="chat-code-block"><code>${code.trim()}</code></pre>`;
    });
    
    // 3. Format inline code `...`
    html = html.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');
    
    // 4. Format bold **...**
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    
    // 5. Format bullet lists
    html = html.replace(/^\s*-\s+(.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
    
    // 6. Handle line breaks
    html = html.split("\n").join("<br />");
    
    return <div dangerouslySetInnerHTML={{ __html: html }} />;
  }

  const hasDiagnostics = diagnostics && diagnostics.recommendations && diagnostics.recommendations.length > 0;

  return (
    <div className="diagnostics-container reveal" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div className="section-header">
        <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="material-symbols-outlined" style={{ color: "var(--primary)", fontSize: "28px" }}>magic_button</span>
          AI Auto-Fix & Diagnostics
        </div>
      </div>

      {/* Side-by-side or stacked grid: Left is Diagnostics, Right is Chat */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "24px",
        alignItems: "start",
        width: "100%"
      }}>
        {/* Left Side: Auto-Fix Recommendations */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {!hasDiagnostics ? (
            <div className="empty-state reveal" style={{ 
              background: "var(--surface-container-low)", 
              border: "1px solid var(--outline-variant)",
              borderRadius: "var(--radius-lg)",
              padding: "48px 24px",
              textAlign: "center"
            }}>
              <div className="empty-icon" style={{ color: "var(--pass)", marginBottom: 16 }}>
                <span className="material-symbols-outlined" style={{ fontSize: "56px" }}>check_circle</span>
              </div>
              <h3 style={{ fontSize: "16px", fontWeight: "600", color: "var(--on-surface)", marginBottom: 8 }}>
                All journeys are 100% healthy!
              </h3>
              <p style={{ fontSize: "13px", color: "var(--on-surface-variant)" }}>
                No test failures detected. You do not need to make any fixes. Great job!
              </p>
            </div>
          ) : (
            <>
              <div className="diagnostics-summary-card">
                <div className="summary-header">
                  <span className="material-symbols-outlined">psychology</span>
                  <h4>System-wide Diagnostic Summary</h4>
                </div>
                <p className="summary-text">{diagnostics.summary}</p>
              </div>

              <div className="master-prompt-card">
                <div className="master-prompt-header">
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="material-symbols-outlined" style={{ color: "var(--primary)" }}>terminal</span>
                    <h4>Unified Master Fix Prompt</h4>
                  </div>
                  <button className={`filter-chip active ${copiedMaster ? "success" : ""}`} onClick={copyMaster} style={{ padding: "6px 14px", fontSize: "12px", display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                      {copiedMaster ? "check" : "content_copy"}
                    </span>
                    {copiedMaster ? "Copied!" : "Copy Master Prompt"}
                  </button>
                </div>
                <div className="master-prompt-desc">
                  Copy this compiled master prompt to your favorite AI Assistant to immediately fix all bugs in one single paste!
                </div>
                <pre className="master-prompt-code">{masterPrompt}</pre>
              </div>

              <h3 style={{ fontSize: "14px", fontWeight: "600", color: "var(--on-surface)", marginTop: 8 }}>
                Failed Journey Diagnostics ({diagnostics.recommendations.length})
              </h3>

              <div className="diagnostics-grid" style={{ display: "flex", flexDirection: "column", gap: 16, maxHeight: "350px", overflowY: "auto", paddingRight: 4 }}>
                {diagnostics.recommendations.map((rec, i) => (
                  <div key={rec.test_id} className="diagnostics-item-card" style={{ padding: 16 }}>
                    <div className="diagnostics-item-header" style={{ marginBottom: 12 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span className="diag-bad-chip">{rec.test_id}</span>
                        <h4 style={{ fontSize: "14px", fontWeight: "600", color: "var(--on-surface)" }}>{rec.test_name}</h4>
                      </div>
                      <button 
                        className={`filter-chip ${copiedIndex === i ? "active" : ""}`}
                        onClick={() => copyIndex(rec.copilot_prompt, i)}
                        style={{ padding: "4px 10px", fontSize: "11px", display: "flex", alignItems: "center", gap: 4 }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                          {copiedIndex === i ? "check" : "content_copy"}
                        </span>
                        {copiedIndex === i ? "Copied!" : "Copy Fix Prompt"}
                      </button>
                    </div>

                    <div className="diagnostics-item-body" style={{ gap: 12 }}>
                      <div className="diag-field">
                        <div className="diag-field-title" style={{ fontSize: "12px" }}>
                          <span className="material-symbols-outlined" style={{ color: "var(--fail)", fontSize: "16px" }}>error_outline</span>
                          Root Cause Analysis
                        </div>
                        <div className="diag-field-text" style={{ fontSize: "12.5px" }}>{rec.root_cause}</div>
                      </div>

                      <div className="diag-field">
                        <div className="diag-field-title" style={{ fontSize: "12px" }}>
                          <span className="material-symbols-outlined" style={{ color: "var(--primary)", fontSize: "16px" }}>construction</span>
                          Developer Fix Action
                        </div>
                        <div className="diag-field-text" style={{ fontSize: "12.5px" }}>{rec.fix_action}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Right Side: Copilot Chat */}
        <div className="chat-container">
          <div className="chat-header">
            <div className="chat-header-info">
              <div className="chat-header-avatar">
                <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>forum</span>
              </div>
              <div>
                <div className="chat-header-title">AI QA Copilot</div>
                <div className="chat-header-subtitle">
                  {activeUrl ? `Scoped to ${activeUrl.replace("https://", "").replace("http://", "")}` : "Global context"}
                </div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 8, height: 8, background: "var(--pass)", borderRadius: "50%" }}></div>
              <span style={{ fontSize: "11px", fontWeight: "600", color: "var(--pass)" }}>Online</span>
            </div>
          </div>

          <div className="chat-messages">
            {chatMessages.map((msg, idx) => (
              <div key={idx} className={`chat-message-row ${msg.role}`}>
                <div className="chat-bubble">
                  {formatMarkdown(msg.content)}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="chat-message-row assistant">
                <div className="chat-bubble" style={{ display: "flex", alignItems: "center" }}>
                  <div className="typing-dots">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="chat-input-bar">
            <input
              className="chat-input-field"
              type="text"
              placeholder="Ask about failed tests, root causes, or how to fix them..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !chatLoading) {
                  handleSendChat();
                }
              }}
              disabled={chatLoading}
            />
            <button
              className="chat-send-btn"
              onClick={handleSendChat}
              disabled={chatLoading || !chatInput.trim()}
            >
              <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>send</span>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadTestView({
  url,
  loadUsers,
  setLoadUsers,
  loadDuration,
  setLoadDuration,
  loadRunning,
  startLoadTest,
  loadMetrics,
  loadHistory,
  loadReport,
  loadError
}) {
  // Let's compute SVG dimensions and path string
  const svgWidth = 600;
  const svgHeight = 220;
  const padding = 30;
  
  const points = useMemo(() => {
    if (!loadHistory || loadHistory.length < 2) return [];
    
    // Scale history points to fit inside SVG
    const maxVal = Math.max(...loadHistory.map(h => h.latency_ms), 100);
    const minVal = 0;
    
    return loadHistory.map((h, idx) => {
      const x = padding + (idx / (loadHistory.length - 1)) * (svgWidth - padding * 2);
      const y = svgHeight - padding - ((h.latency_ms - minVal) / (maxVal - minVal)) * (svgHeight - padding * 2);
      return { x, y, latency: h.latency_ms, rps: h.rps };
    });
  }, [loadHistory]);

  const pathD = useMemo(() => {
    if (points.length < 2) return "";
    return points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  }, [points]);

  const areaD = useMemo(() => {
    if (points.length < 2) return "";
    const startX = points[0].x;
    const endX = points[points.length - 1].x;
    return `${pathD} L ${endX} ${svgHeight - padding} L ${startX} ${svgHeight - padding} Z`;
  }, [points, pathD]);

  const successRate = loadMetrics ? loadMetrics.success_rate : (loadReport ? loadReport.success_rate : null);
  const totalReqs = loadMetrics ? loadMetrics.total_requests : (loadReport ? loadReport.total_requests : null);
  const rps = loadMetrics ? loadMetrics.rps : (loadReport ? loadReport.avg_rps : null);
  const latency = loadMetrics ? loadMetrics.latency_ms : (loadReport ? loadReport.avg_latency_ms : null);
  const progress = loadMetrics ? loadMetrics.progress_percent : (loadRunning ? 5 : 0);

  return (
    <div className="diagnostics-container reveal" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div className="section-header">
        <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="material-symbols-outlined" style={{ color: "var(--primary)", fontSize: "28px" }}>speed</span>
          Concurrently Scaled Load Testing
        </div>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 2fr",
        gap: "24px",
        alignItems: "start",
        width: "100%"
      }}>
        {/* Left Side: Parameters Slider Panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="diagnostics-item-card" style={{ padding: 20 }}>
            <h4 style={{ fontSize: "14px", fontWeight: "600", color: "var(--on-surface)", marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <span className="material-symbols-outlined" style={{ fontSize: "18px", color: "var(--primary)" }}>tune</span>
              Stress Parameters
            </h4>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "var(--on-surface-variant)", marginBottom: 6 }}>
                  <span>Virtual Users (VU)</span>
                  <strong style={{ color: "var(--primary)" }}>{loadUsers} Users</strong>
                </div>
                <input
                  type="range"
                  min="10"
                  max="150"
                  step="5"
                  value={loadUsers}
                  onChange={(e) => setLoadUsers(parseInt(e.target.value))}
                  disabled={loadRunning}
                  style={{ width: "100%", accentColor: "var(--primary)" }}
                />
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "var(--on-surface-variant)", marginBottom: 6 }}>
                  <span>Duration</span>
                  <strong style={{ color: "var(--primary)" }}>{loadDuration} seconds</strong>
                </div>
                <input
                  type="range"
                  min="10"
                  max="60"
                  step="5"
                  value={loadDuration}
                  onChange={(e) => setLoadDuration(parseInt(e.target.value))}
                  disabled={loadRunning}
                  style={{ width: "100%", accentColor: "var(--primary)" }}
                />
              </div>

              {loadError && (
                <div style={{ color: "var(--fail)", fontSize: "12px", background: "rgba(211,47,47,0.08)", padding: "10px 12px", borderRadius: "var(--radius-sm)", border: "1px solid rgba(211,47,47,0.15)" }}>
                  {loadError}
                </div>
              )}

              <button
                className="chat-send-btn"
                onClick={startLoadTest}
                disabled={loadRunning || !url}
                style={{ width: "100%", display: "flex", justifyContent: "center", gap: 8, padding: 12 }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>bolt</span>
                {loadRunning ? "Stress Run Active..." : "Initiate Load Test"}
              </button>
            </div>
          </div>

          {loadReport && !loadRunning && (
            <div className="diagnostics-item-card" style={{ padding: 20, background: "rgba(53,37,205,0.02)", border: "1px dashed var(--outline-variant)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "600", color: "var(--on-surface)", marginBottom: 12 }}>
                Server Capacity Report
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12.5px" }}>
                  <span style={{ color: "var(--on-surface-variant)" }}>Grade</span>
                  <strong style={{ color: loadReport.performance_score >= 80 ? "var(--pass)" : "var(--warn)" }}>
                    {loadReport.performance_grade}
                  </strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12.5px" }}>
                  <span style={{ color: "var(--on-surface-variant)" }}>Capacity Score</span>
                  <strong>{loadReport.performance_score} / 100</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12.5px" }}>
                  <span style={{ color: "var(--on-surface-variant)" }}>Average RPS</span>
                  <strong>{loadReport.avg_rps} req/s</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12.5px" }}>
                  <span style={{ color: "var(--on-surface-variant)" }}>P95 Latency</span>
                  <strong>{loadReport.p95_latency_ms} ms</strong>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Side: Live Metrics Workspace */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* If completely empty */}
          {!loadRunning && !loadReport ? (
            <div className="empty-state reveal" style={{ 
              background: "var(--surface-container-low)", 
              border: "1px solid var(--outline-variant)",
              borderRadius: "var(--radius-lg)",
              padding: "64px 24px",
              textAlign: "center"
            }}>
              <div className="empty-icon" style={{ color: "var(--primary)", marginBottom: 16 }}>
                <span className="material-symbols-outlined" style={{ fontSize: "64px" }}>network_ping</span>
              </div>
              <h3 style={{ fontSize: "16px", fontWeight: "600", color: "var(--on-surface)", marginBottom: 8 }}>
                No Load Test Records Detected
              </h3>
              <p style={{ fontSize: "13px", color: "var(--on-surface-variant)", maxWidth: 360, margin: "0 auto" }}>
                Select a target domain, specify concurrent virtual users, and launch your stress run to analyze live server capacity metrics!
              </p>
            </div>
          ) : (
            <>
              {/* Gauges Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                {/* Latency card */}
                <div className="diagnostics-item-card" style={{ padding: 16, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 120 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: "28px", color: latency > 1000 ? "var(--fail)" : latency > 500 ? "var(--warn)" : "var(--pass)", marginBottom: 6 }}>
                    timer
                  </span>
                  <div style={{ fontSize: "20px", fontWeight: "700", color: "var(--on-surface)" }}>
                    {latency != null ? `${latency} ms` : "—"}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--on-surface-variant)", marginTop: 2 }}>Avg Latency</div>
                </div>

                {/* RPS card */}
                <div className="diagnostics-item-card" style={{ padding: 16, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 120 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: "28px", color: "var(--primary)", marginBottom: 6 }}>
                    bolt
                  </span>
                  <div style={{ fontSize: "20px", fontWeight: "700", color: "var(--on-surface)" }}>
                    {rps != null ? `${rps} RPS` : "—"}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--on-surface-variant)", marginTop: 2 }}>Throughput / Speed</div>
                </div>

                {/* Success rate card */}
                <div className="diagnostics-item-card" style={{ padding: 16, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 120 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: "28px", color: successRate >= 95 ? "var(--pass)" : successRate >= 80 ? "var(--warn)" : "var(--fail)", marginBottom: 6 }}>
                    check_circle
                  </span>
                  <div style={{ fontSize: "20px", fontWeight: "700", color: "var(--on-surface)" }}>
                    {successRate != null ? `${successRate}%` : "—"}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--on-surface-variant)", marginTop: 2 }}>
                    Success Rate {totalReqs ? `(${totalReqs} hits)` : ""}
                  </div>
                </div>
              </div>

              {/* Progress bar */}
              {loadRunning && (
                <div style={{ width: "100%" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: 6, color: "var(--on-surface-variant)" }}>
                    <span>Active Run Progress</span>
                    <strong>{progress}%</strong>
                  </div>
                  <div style={{ height: 6, background: "var(--outline-variant)", borderRadius: 3, overflow: "hidden" }}>
                    <div style={{ width: `${progress}%`, height: "100%", background: "var(--primary)", transition: "width 0.5s ease" }} />
                  </div>
                </div>
              )}

              {/* Live SVG Performance Chart */}
              {loadHistory.length >= 2 && (
                <div className="diagnostics-item-card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
                  <h4 style={{ fontSize: "12px", fontWeight: "600", color: "var(--on-surface)", display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: "16px", color: "var(--primary)" }}>show_chart</span>
                    Latency Over Time (Response Scale)
                  </h4>
                  <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: "100%", height: "auto" }}>
                    <defs>
                      <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>
                    {/* Grid Lines */}
                    <line x1={padding} y1={padding} x2={svgWidth - padding} y2={padding} stroke="rgba(0,0,0,0.04)" strokeDasharray="3" />
                    <line x1={padding} y1={svgHeight / 2} x2={svgWidth - padding} y2={svgHeight / 2} stroke="rgba(0,0,0,0.04)" strokeDasharray="3" />
                    <line x1={padding} y1={svgHeight - padding} x2={svgWidth - padding} y2={svgHeight - padding} stroke="rgba(0,0,0,0.1)" />

                    {/* Gradient Area */}
                    {areaD && <path d={areaD} fill="url(#chartGrad)" />}

                    {/* Line path */}
                    {pathD && <path d={pathD} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" />}

                    {/* Circles on dots */}
                    {points.map((p, idx) => (
                      <circle key={idx} cx={p.x} cy={p.y} r="3.5" fill="white" stroke="var(--primary)" strokeWidth="2" />
                    ))}
                  </svg>
                </div>
              )}

              {/* Server health grade & AI advice (Report Summary) */}
              {loadReport && !loadRunning && (
                <div className="diagnostics-summary-card" style={{ border: "1px solid var(--outline-variant)" }}>
                  <div className="summary-header">
                    <span className="material-symbols-outlined" style={{ color: "var(--primary)" }}>psychology</span>
                    <h4>AI Stress Remediation Strategy</h4>
                  </div>
                  <p className="summary-text" style={{ fontSize: "13px", lineHeight: "1.6", color: "var(--on-surface)" }}>
                    <strong>Report: </strong>{loadReport.ai_recommendation}
                  </p>
                </div>
              )}

              {/* Live request hits terminal feed */}
              {((loadMetrics && loadMetrics.recent_hits) || (loadReport && loadReport.ticks)) && (
                <div className="diagnostics-item-card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
                  <h4 style={{ fontSize: "12px", fontWeight: "600", color: "var(--on-surface)", display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: "16px", color: "var(--primary)" }}>terminal</span>
                    Stress Simulation Console (Live Hits Feed)
                  </h4>
                  <div style={{ 
                    background: "rgba(19, 27, 46, 0.98)", 
                    borderRadius: "var(--radius-md)", 
                    padding: 12, 
                    fontFamily: "var(--font-mono)", 
                    fontSize: "12px", 
                    maxHeight: 180, 
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                    gap: 6
                  }}>
                    {(loadMetrics?.recent_hits || loadHistory[loadHistory.length - 1]?.recent_hits || []).map((hit, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", color: hit.success ? "#a9b2c3" : "#f43f5e" }}>
                        <span>
                          [{hit.timestamp}] {hit.user} hits <strong style={{ color: "#38bdf8" }}>{hit.url}</strong>
                        </span>
                        <span>
                          {hit.status} {hit.success ? "OK" : "ERR"} ({hit.latency}ms)
                        </span>
                      </div>
                    ))}
                    {loadRunning && (
                      <div style={{ color: "var(--primary)", animation: "pulse 1.5s infinite" }}>
                        ▋ Simulated Virtual Users generating concurrent streams...
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
