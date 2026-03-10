// app.js
// Expects these files in the same folder:
// - ui_test.json
// - backend_test.json
//
// Expects this HTML somewhere on the page:
//
// <h2>UI Test Cases</h2>
// <div id="ui-table"></div>
//
// <h2>Backend Test Cases</h2>
// <div id="backend-table"></div>

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const [uiData, backendData] = await Promise.all([
      fetchJson("ui_test.json"),
      fetchJson("backend_test.json")
    ]);

    renderTable("ui-table", "UI Test Cases", uiData.test_cases || []);
    renderTable("backend-table", "Backend Test Cases", backendData.test_cases || []);
  } catch (error) {
    console.error("Failed to load test case files:", error);
    showError("ui-table", "Could not load ui_test.json");
    showError("backend-table", "Could not load backend_test.json");
  }
});

async function fetchJson(fileName) {
  const response = await fetch(fileName);

  if (!response.ok) {
    throw new Error(`Failed to fetch ${fileName}: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

function renderTable(containerId, title, testCases) {
  const container = document.getElementById(containerId);

  if (!container) {
    console.warn(`Container with id "${containerId}" not found.`);
    return;
  }

  if (!Array.isArray(testCases) || testCases.length === 0) {
    container.innerHTML = `<p>No data available for ${title}.</p>`;
    return;
  }

  const columns = getAllColumns(testCases);

  const wrapper = document.createElement("div");
  wrapper.style.overflowX = "auto";
  wrapper.style.marginBottom = "24px";

  const heading = document.createElement("h3");
  heading.textContent = title;
  heading.style.marginBottom = "12px";

  const table = document.createElement("table");
  table.style.borderCollapse = "collapse";
  table.style.width = "100%";
  table.style.minWidth = "700px";

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");

  columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = formatHeader(column);
    th.style.border = "1px solid #ccc";
    th.style.padding = "10px";
    th.style.textAlign = "left";
    th.style.backgroundColor = "#f4f4f4";
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");

  testCases.forEach((testCase) => {
    const row = document.createElement("tr");

    columns.forEach((column) => {
      const td = document.createElement("td");
      td.style.border = "1px solid #ccc";
      td.style.padding = "10px";
      td.style.verticalAlign = "top";

      const value = testCase[column];

      if (Array.isArray(value)) {
        td.innerHTML = value.map((item) => escapeHtml(String(item))).join("<br>");
      } else if (value === undefined || value === null) {
        td.textContent = "";
      } else {
        td.textContent = String(value);
      }

      row.appendChild(td);
    });

    tbody.appendChild(row);
  });

  table.appendChild(tbody);
  wrapper.appendChild(heading);
  wrapper.appendChild(table);
  container.appendChild(wrapper);
}

function getAllColumns(items) {
  const preferredOrder = [
    "id",
    "scenario",
    "input",
    "steps",
    "expected_result",
    "priority"
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
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function showError(containerId, message) {
  const container = document.getElementById(containerId);
  if (container) {
    container.innerHTML = `<p style="color: red;">${message}</p>`;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}