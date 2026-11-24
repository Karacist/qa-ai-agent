## QA Agent Frontend (React)

This dashboard reads the latest pipeline outputs from:

- `reports/test_cases.json`
- `reports/test_results.json`
- `reports/test_screenshots/*.png`

### Setup

1. Install Node.js (recommended: 18+)
2. Open a terminal in this folder and install deps:
   - `cd frontend`
   - `npm install`

### Run Dev Server

- `npm run dev`

Then open the URL shown in the terminal (usually `http://localhost:5173`).

### Export

- Click **Download CSV** to export the currently filtered rows.
- The CSV opens in Excel or Google Sheets.

