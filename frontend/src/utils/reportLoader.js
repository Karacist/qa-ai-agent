export async function loadJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: ${res.status} ${res.statusText}`);
  }
  const text = await res.text();
  // If we accidentally got SPA HTML (404 -> index.html), surface a clearer message.
  const trimmed = text.trim();
  if (trimmed.startsWith("<")) {
    throw new Error(
      `Unexpected HTML response while loading JSON from ${url}. Check dev server routing/middleware.`
    );
  }
  return JSON.parse(text);
}

export function mergeCasesAndResults(cases, results) {
  const merged = [];
  const maxLen = Math.max(cases.length, results ? results.length : 0);

  for (let i = 0; i < maxLen; i++) {
    const tc = cases[i] || {};
    const rr = results ? results[i] : null;

    const testSeq = i + 1;
    const testId = String(tc.test_id || "");
    const pageUrl = String(tc.page_url || "");
    const originalName = String(tc.test_name || "");

    merged.push({
      _rowIndex: i,
      testSeq,
      testId,
      pageUrl,
      testName: originalName,
      steps: Array.isArray(tc.steps) ? tc.steps : [],
      expectedResult: String(tc.expected_result || ""),
      status: rr && rr.status ? rr.status : "pending",
      error: rr && rr.error != null ? String(rr.error) : null,
      screenshot: (() => {
        if (!rr || !rr.screenshot) return "";
        let s = String(rr.screenshot);
        // Normalize Windows paths to repo-relative web paths.
        s = s.replace(/\\/g, "/");
        const marker = "/reports/";
        const idx = s.lastIndexOf(marker);
        if (idx !== -1) return s.slice(idx + 1); // drop leading slash keep "reports/..."
        // If it already looks relative.
        if (s.startsWith("reports/") || s.startsWith("screenshots/")) return s;
        return s;
      })(),
    });
  }

  return merged;
}

