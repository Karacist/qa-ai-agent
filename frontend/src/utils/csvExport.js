function escapeCsvCell(value) {
  const str = value == null ? "" : String(value);
  // Quote if it contains commas, quotes, or newlines.
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function downloadCsv(filename, rows) {
  const headers = [
    "Test #",
    "Test ID",
    "Generated Test Name",
    "Renamed Test Name",
    "Page URL",
    "Status",
    "Error",
    "Steps",
    "Expected Result",
    "Screenshot Path",
  ];

  const csvLines = [headers.map(escapeCsvCell).join(",")];
  for (const r of rows) {
    const stepsText = Array.isArray(r.steps) ? r.steps.join(" | ") : "";
    const line = [
      escapeCsvCell(r.testSeq),
      escapeCsvCell(r.testId),
      escapeCsvCell(r.testName),
      escapeCsvCell(r.displayName),
      escapeCsvCell(r.pageUrl),
      escapeCsvCell(r.status),
      escapeCsvCell(r.error),
      escapeCsvCell(stepsText),
      escapeCsvCell(r.expectedResult),
      escapeCsvCell(r.screenshot),
    ].join(",");
    csvLines.push(line);
  }

  const csv = csvLines.join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

