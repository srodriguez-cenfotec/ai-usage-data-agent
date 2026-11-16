const form = document.querySelector("#query-form");
const input = document.querySelector("#question");
const results = document.querySelector("#results");
const welcome = document.querySelector("#welcome");
const send = document.querySelector("#send");

fetch("/api/status")
  .then((response) => {
    if (!response.ok) throw new Error("Could not load dataset status.");
    return response.json();
  })
  .then((status) => {
    document.querySelector("#dataset-status").textContent = `${status.records} survey responses · cleaned CSV`;
    document.querySelector("#record-count").textContent = status.records.toLocaleString();
    document.querySelector("#mode-tag").textContent = status.mode === "Rule-based" ? "RULE-BASED" : "LOCAL LLM";
    document.querySelector("#mode-tag").title = status.mode;
  })
  .catch(() => {
    document.querySelector("#dataset-status").textContent = "Dataset status unavailable";
  });

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderResult(data, question) {
  welcome.hidden = true;
  results.replaceChildren();

  const query = element("div", "question-bubble", question);
  const card = element("article", "result-card");
  const heading = element("div", "result-heading");
  const headingText = element("div");
  headingText.append(element("p", "eyebrow", "DATASET RESULT"), element("h2", "", data.title));
  const badge = element("span", "result-badge", `${data.matched} / ${data.available} rows`);
  badge.title = data.mode || "Rules";
  heading.append(headingText, badge);
  card.append(heading, element("p", "summary", data.summary));

  const scope = element("div", "scope");
  scope.append(element("strong", "", "Scope"), element("span", "", data.filters));
  card.append(scope);

  const chartSection = element("section", "chart-section");
  chartSection.append(element("h3", "", "Breakdown"));
  const chart = element("div", "chart");
  const max = Math.max(...data.chart.map((item) => item.value), 1);
  for (const item of data.chart) {
    const row = element("div", "bar-row");
    const label = element("span", "bar-label", item.label);
    const track = element("div", "bar-track");
    const bar = element("div", "bar");
    bar.style.width = `${Math.max(2, (item.value / max) * 100)}%`;
    track.append(bar);
    row.append(label, track, element("span", "bar-value", Number(item.value).toLocaleString(undefined, { maximumFractionDigits: 2 })));
    chart.append(row);
  }
  chartSection.append(chart);
  card.append(chartSection);

  const tableSection = element("section", "table-section");
  tableSection.append(element("h3", "", "Result details"));
  const table = element("table");
  const thead = element("thead");
  const headerRow = element("tr");
  for (const column of data.columns) headerRow.append(element("th", "", column));
  thead.append(headerRow);
  const tbody = element("tbody");
  for (const values of data.rows) {
    const row = element("tr");
    for (const value of values) row.append(element("td", "", String(value)));
    tbody.append(row);
  }
  table.append(thead, tbody);
  const tableWrap = element("div", "table-wrap");
  tableWrap.append(table);
  tableSection.append(tableWrap);
  card.append(tableSection);
  results.append(query, card);
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderError(message, question) {
  welcome.hidden = true;
  results.replaceChildren();
  results.append(element("div", "question-bubble", question));
  const error = element("div", "error-card");
  error.append(element("strong", "", "I couldn't answer that question"), element("p", "", message));
  results.append(error);
}

async function submitQuestion(question) {
  if (!question.trim()) return;
  send.disabled = true;
  input.disabled = true;
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The query could not be completed.");
    renderResult(data, question);
  } catch (error) {
    renderError(error.message, question);
  } finally {
    send.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value;
  input.value = "";
  input.style.height = "auto";
  submitQuestion(question);
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".suggestion, .starter-prompt").forEach((button) => {
  button.addEventListener("click", () => {
    const question = button.querySelector("span:not(.suggestion-icon):not(.starter-icon):not(.prompt-arrow)")?.textContent
      || button.textContent;
    input.value = question.trim();
    submitQuestion(input.value);
    input.value = "";
  });
});
