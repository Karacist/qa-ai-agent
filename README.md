# 🤖 QA AI Agent

An end-to-end, AI-powered web QA platform. Point it at any URL and it will crawl the site, generate executable test cases using an LLM, run those tests in a real browser, detect regressions, perform load testing, and explain every failure — all without writing a single line of test code.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![Playwright](https://img.shields.io/badge/Playwright-headless-green?logo=playwright)
![Groq](https://img.shields.io/badge/LLM-Llama%203.3%2070B%20via%20Groq-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🕷 **Intelligent Crawler** | Headless Playwright BFS crawler — captures DOM, screenshots, Web Perf API metrics, and XHR calls per page |
| 🧠 **AI Test Generation** | Two-stage Llama 3.3-70B pipeline that creates a test plan and 10–15 executable Playwright test cases from the live DOM |
| ▶️ **Multi-Browser Execution** | Runs tests against Chromium, Firefox, and WebKit; auto-repeats critical/high-risk tests at 375 px mobile viewport |
| 📺 **Live Browser View** | Real-time JPEG frame stream with animated cursor tracking and click-ring effects in the React dashboard |
| 🔍 **AI Diagnostics & Auto-Fix** | Each failed test gets an LLM-generated root-cause analysis, fix instructions, and a copy-pasteable prompt for Copilot/Claude/ChatGPT |
| 📉 **Regression Tracking** | Maintains per-URL run history (up to 30 runs); highlights new failures and fixed tests after every run |
| ⚡ **Load Testing** | Concurrent `ThreadPoolExecutor` stress tester — configurable virtual users (1–200) and duration (5–120 s), with P95/P99 latency, RPS streaming, and a performance grade (A+ to D) |
| 💬 **AI Chat Copilot** | Floating chat widget that answers questions about the current test results using the LLM |
| 🗄 **Flexible Storage** | Auto-detects MongoDB; falls back to local JSON files if MongoDB is unavailable — no config needed |
| 📤 **CSV Export** | Export any test results to CSV directly from the dashboard |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                   React Dashboard                    │
│  (Vite · JSX · SSE event stream · live frame view)  │
└──────────────────────┬──────────────────────────────┘
                       │  HTTP + Server-Sent Events
                       ▼
┌─────────────────────────────────────────────────────┐
│          Python HTTP Backend  (port 8000)            │
│          stdlib ThreadingHTTPServer — no framework   │
└──┬──────────┬────────┬──────────┬───────────────────┘
   │          │        │          │
   ▼          ▼        ▼          ▼
Crawler   Generator  Executor  Load Tester
(Playwright) (Groq LLM) (Playwright) (urllib threads)
   │          │        │
   └──────────┴────────┘
              │
              ▼
        DB Manager
   (MongoDB ↔ JSON fallback)
```

### Pipeline Phases

1. **Crawl** — `agents/crawler_agent.py`  
   BFS-crawls the target site with Playwright Chromium, capturing HTML, screenshots, perf metrics, and API calls.

2. **Generate** — `agents/test_generator_agent.py`  
   Sends a sitemap summary to Llama 3.3-70B → receives a structured test plan.  
   Sends the full page DOM + test plan → receives 10–15 executable test cases with Playwright steps.

3. **Execute** — `agents/executor_agent.py`  
   Runs every test case in Playwright (Chromium/Firefox/WebKit), streams live JPEG frames to the frontend, and runs mobile variants for critical/high-risk tests.

4. **Diagnose & Regress** — `agents/diagnostics_agent.py` + `agents/regression_manager.py`  
   LLM analyses failures and generates fix guides; regression manager diffs this run against the previous one.

---

## 📂 Project Structure

```
qa-ai-agent/
├── agents/
│   ├── crawler_agent.py        # Playwright BFS crawler
│   ├── html_processor.py       # Regex HTML cleaner + structure extractor
│   ├── test_generator_agent.py # Groq LLM test plan + test case generator
│   ├── executor_agent.py       # Playwright test runner with live streaming
│   ├── diagnostics_agent.py    # Groq LLM failure analysis + AI chat copilot
│   ├── load_tester.py          # Concurrent load tester (urllib + ThreadPoolExecutor)
│   └── regression_manager.py  # Run history + regression diffing
├── backend/
│   ├── server.py               # ThreadingHTTPServer — REST API + SSE endpoints
│   └── db_manager.py          # MongoDB / JSON file dual-mode storage
├── graph/
│   └── workflow.py             # LangGraph pipeline (crawl → generate → report)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── Dashboard.jsx   # Full React SPA (~1900 lines)
│   │   ├── utils/
│   │   │   ├── csvExport.js
│   │   │   └── reportLoader.js
│   │   ├── App.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── reports/                    # Auto-generated (gitignored)
├── screenshots/                # Auto-generated (gitignored)
├── run_agent.py                # CLI entry point (no server needed)
├── requirements.txt
├── .env.example                # Copy to .env and add your keys
└── README.md
```

---

## 🚀 Setup & Installation

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the React dashboard)
- A free **[Groq API key](https://console.groq.com)** (Llama 3.3-70B, generous free tier)
- *(Optional)* **MongoDB** running locally on the default port — the app works fine without it

---

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/qa-ai-agent.git
cd qa-ai-agent
```

---

### 2. Set up the Python environment

```bash
# Create and activate a virtual environment
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

---

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Install Playwright browsers

```bash
playwright install chromium firefox webkit
```

> You only need `chromium` for the default pipeline. `firefox` and `webkit` are only used if you explicitly select them in the UI.

---

### 5. Configure your API key

```bash
# Copy the example file
cp .env.example .env   # macOS/Linux
copy .env.example .env  # Windows
```

Edit `.env` and replace the placeholder with your actual Groq key:

```
GROQ_API_KEY=gsk_your_actual_key_here
```

Get a free key at **[console.groq.com](https://console.groq.com)**.

---

### 6. Install frontend dependencies

```bash
cd frontend
npm install
```

---

## ▶️ Running the App

You need two terminals — one for the backend, one for the frontend.

### Terminal 1 — Start the Python backend

```bash
# From the repo root (with venv active)
python backend/server.py
```

You should see:
```
[DB] Initializing storage layer...
QA Agent backend running at http://127.0.0.1:8000
```

### Terminal 2 — Start the React frontend

```bash
cd frontend
npm run dev
```

Then open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

### CLI mode (no frontend needed)

You can also run the full pipeline from the terminal without starting either server:

```bash
python run_agent.py
```

It will prompt you for a URL and max pages, then print live progress and a results summary.

---

## 🧪 Usage Walkthrough

1. Open the dashboard at `http://localhost:5173`.
2. Enter a website URL in the **input field** (e.g., `https://example.com`).
3. Choose the number of pages to crawl (1–50), browsers, and whether to include mobile variants.
4. Click **Run Pipeline**.
5. Watch the **Live View** tab as the agent browses and tests the site in real time.
6. When complete, explore:
   - **Overview** — pass/fail metrics, breakdowns by type and risk
   - **Tests** — per-test results with screenshots and step details
   - **Test Plan** — LLM-generated app summary and risk areas
   - **Regression** — comparison with previous runs
   - **AI Auto-Fix** — root-cause analysis and Copilot prompts for each failure
   - **Load Test** — run a stress test and view the real-time performance chart
   - **AI Chat** — ask the copilot anything about the results

---

## ⚙️ Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | — | Groq API key for LLM calls |
| `MONGO_URI` | ❌ No | `mongodb://localhost:27017` | MongoDB connection URI |

All other settings (browsers, page limits, users, duration) are configured through the UI or CLI prompts at runtime.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq API — `llama-3.3-70b-versatile` |
| Browser automation | Playwright (Python async API) |
| Workflow orchestration | LangGraph |
| Backend | Python `http.server.ThreadingHTTPServer` |
| Persistence | MongoDB + JSON file fallback |
| Frontend | React 18 + Vite |
| Load testing | Python `urllib` + `ThreadPoolExecutor` |

---

## 🗺 Roadmap

- [ ] Export test results to JUnit XML / HTML report
- [ ] CI/CD integration (GitHub Actions workflow)
- [ ] Support for authenticated pages (login flow configuration)
- [ ] Scheduled runs with email/Slack notifications
- [ ] Docker Compose setup for one-command startup

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'feat: add my feature'`
4. Push and open a PR

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

This tool sends real HTTP requests to target websites. Use it only on websites you own or have explicit permission to test. Misconfigured load tests can overload servers.
