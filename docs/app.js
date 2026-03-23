document.addEventListener("DOMContentLoaded", async () => {
  await loadTables();
});

async function loadTables() {
  await loadSingleTable({
    fileName: "ui_test_cases.json",
    containerId: "ui-table",
    title: "UI Test Cases"
  });

  await loadSingleTable({
    fileName: "backend_test_cases.json",
    containerId: "backend-table",
    title: "Backend Test Cases"
  });

  await loadSingleTable({
    fileName: "regression_test_cases.json",
    containerId: "regression-table",
    title: "Regression Test Cases"
  });
}

async function loadSingleTable({ fileName, containerId, title }) {
  try {
    const data = await fetchJson(fileName);
    console.log(fileName, data);
    renderTable(containerId, title, data);
  } catch (error) {
    console.error(`Failed to load ${fileName}:`, error);
    showError(containerId, `Could not load ${fileName}. Check filename, path, and JSON format.`);
  }
}

async function fetchJson(fileName) {
  const response = await fetch(fileName);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} - ${response.statusText}`);
  }

  return await response.json();
}

function renderTable(containerId, title, testCases) {
  const container = document.getElementById(containerId);

  if (!container) {
    console.warn(`Container with id "${containerId}" not found.`);
    return;
  }

  if (!Array.isArray(testCases) || testCases.length === 0) {
    container.innerHTML = `<h2>${title}</h2><p>No data found.</p>`;
    return;
  }

  const columns = getAllColumns(testCases);

  let html = `<h2>${title}</h2>`;
  html += `<div class="table-container">`;
  html += `<table>`;

  html += "<thead><tr>";
  columns.forEach((column) => {
    html += `<th>${formatHeader(column)}</th>`;
  });
  html += "</tr></thead>";

  html += "<tbody>";
  testCases.forEach((testCase) => {
    html += "<tr>";

    columns.forEach((column) => {
      const value = testCase[column];

      if (Array.isArray(value)) {
        html += `<td>${value.map(item => escapeHtml(String(item))).join("<br>")}</td>`;
      } else {
        html += `<td>${escapeHtml(String(value ?? ""))}</td>`;
      }
    });

    html += "</tr>";
  });
  html += "</tbody></table></div>";

  container.innerHTML = html;
}

function getAllColumns(items) {
  const preferredOrder = [
    "Test Case ID",
    "Module",
    "Title",
    "Objectives",
    "Preconditions",
    "Test_Steps",
    "Test_Data",
    "Expected_Result",
    "Priority",
    "Execution_Status",
    "Defect_ID",
    "Comments"
  ];

  const foundColumns = new Set();

  items.forEach((item) => {
    Object.keys(item).forEach((key) => foundColumns.add(key));
  });

  const orderedColumns = preferredOrder.filter((key) => foundColumns.has(key));
  const remainingColumns = [...foundColumns].filter((key) => !preferredOrder.includes(key));

  return [...orderedColumns, ...remainingColumns];
}

function formatHeader(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function showError(containerId, message) {
  const container = document.getElementById(containerId);
  if (container) {
    container.innerHTML = `<p style="color: red;">${message}</p>`;
  }
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
