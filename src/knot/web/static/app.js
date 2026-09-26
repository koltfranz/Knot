/* 结绳 Knot 前端：零依赖，消费 /api/* 与同一份 ChartSpec。 */
"use strict";

const TOKEN = new URLSearchParams(location.search).get("口令") || "";
const money = new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" });

async function api(path, options = {}) {
  const headers = Object.assign({ "X-Knot-Token": TOKEN }, options.headers || {});
  const response = await fetch(path, Object.assign({}, options, { headers }));
  const payload = await response.json().catch(() => ({ 错误: "响应不是 JSON" }));
  if (!response.ok) throw new Error(payload.错误 || `HTTP ${response.status}`);
  return payload;
}

const post = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const el = (id) => document.getElementById(id);
const esc = (text) => String(text ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const amount = (text) => {
  const value = Number(String(text ?? "").replace(/[,¥\s]/g, ""));
  return Number.isFinite(value) ? money.format(value) : esc(text);
};

function table(headers, rows, numeric = []) {
  const head = headers.map((h, i) => `<th class="${numeric.includes(i) ? "num" : ""}">${esc(h)}</th>`).join("");
  const body = rows.map((row) => "<tr>" + row.map((cell, i) =>
    `<td class="${numeric.includes(i) ? "num" : ""}">${cell}</td>`).join("") + "</tr>").join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${headers.length}" class="hint">暂无数据</td></tr>`}</tbody></table>`;
}

/* ---------- ChartSpec → SVG（与 CLI / TUI 消费同一 JSON） ---------- */

const PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#eeca3b", "#b279a2", "#ff9da6"];

function renderChart(spec) {
  const width = 460, height = 240, pad = 28;
  const labels = spec.标签 || [];
  const series = (spec.系列 || []).map((s) => ({ name: s.名称, values: s.数值.map(Number) }));
  const kind = spec.类型;
  if (!labels.length || !series.length) return `<p class="hint">暂无数据</p>`;

  const max = Math.max(...series.flatMap((s) => s.values.map(Math.abs)), 1);
  const scale = (value) => (Math.abs(value) / max) * (height - pad * 2);

  if (kind === "waterfall") {
    const values = series[0]?.values || [];
    const totalIndexes = [0, values.length - 1];
    let running = 0;
    const points = values.map((value, index) => {
      const base = totalIndexes.includes(index) ? 0 : running;
      const end = totalIndexes.includes(index) ? value : running + value;
      running = end;
      return { base, end };
    });
    const top = Math.max(...values, ...points.map((p) => Math.max(p.base, p.end)), 1);
    const bottom = Math.min(0, ...values, ...points.map((p) => Math.min(p.base, p.end)));
    const span = top - bottom || 1;
    const slot = (width - 70) / Math.max(1, values.length);
    const bars = points.map((point, index) => {
      const y1 = 200 - ((Math.max(point.base, point.end) - bottom) / span) * 150;
      const y2 = 200 - ((Math.min(point.base, point.end) - bottom) / span) * 150;
      const color = totalIndexes.includes(index) ? "#4c78a8" : (values[index] >= 0 ? "#54a24b" : "#e45756");
      return `<rect x="${40 + index * slot + slot * 0.2}" y="${y1}" width="${slot * 0.6}" height="${Math.max(2, y2 - y1)}" fill="${color}"><title>${esc(labels[index])} ${amount(values[index])}</title></rect>
        <text x="${40 + index * slot + slot * 0.5}" y="220" font-size="10" text-anchor="middle">${esc(labels[index])}</text>`;
    }).join("");
    return `<svg viewBox="0 0 ${width} 240">${bars}</svg>`;
  }

  if (kind === "gauge") {
    const actual = series[0]?.values || [];
    const planned = series[1]?.values || [];
    const rows = labels.map((label, index) => {
      const top = planned[index] || 0;
      const used = actual[index] || 0;
      const ratio = top ? used / top : 0;
      const width = Math.max(2, Math.min(1, ratio) * 240);
      const color = ratio <= 1 ? "#54a24b" : "#e45756";
      return `<text x="110" y="${40 + index * 26}" font-size="12" text-anchor="end">${esc(label.slice(0, 14))}</text>
        <rect x="120" y="${30 + index * 26}" width="240" height="14" rx="7" fill="#eef1f3"></rect>
        <rect x="120" y="${30 + index * 26}" width="${width}" height="14" rx="7" fill="${color}"><title>${esc(label)} 已用 ${amount(used)} / 预算 ${amount(top)}</title></rect>
        <text x="370" y="${42 + index * 26}" font-size="11" fill="#555">${(ratio * 100).toFixed(0)}%</text>`;
    }).join("");
    return `<svg viewBox="0 0 ${width} ${Math.max(90, 40 + labels.length * 26)}">${rows}</svg>`;
  }

  if (kind === "pie") {
    const values = series[0].values;
    const total = values.reduce((a, b) => a + Math.abs(b), 0) || 1;
    let angle = -90, paths = "";
    values.forEach((value, index) => {
      const sweep = (Math.abs(value) / total) * 360;
      const rad = (deg) => (deg * Math.PI) / 180;
      const x1 = 110 + 80 * Math.cos(rad(angle)), y1 = height / 2 + 80 * Math.sin(rad(angle));
      const x2 = 110 + 80 * Math.cos(rad(angle + sweep)), y2 = height / 2 + 80 * Math.sin(rad(angle + sweep));
      paths += `<path d="M110,${height / 2} L${x1},${y1} A80,80 0 ${sweep > 180 ? 1 : 0} 1 ${x2},${y2} Z" fill="${PALETTE[index % PALETTE.length]}"><title>${esc(labels[index])} ${amount(value)}</title></path>`;
      angle += sweep;
    });
    const legend = labels.slice(0, 8).map((label, index) =>
      `<text x="230" y="${40 + index * 20}" font-size="12" fill="#333">${esc(label)}</text>`).join("");
    return `<svg viewBox="0 0 ${width} ${height}">${paths}${legend}</svg>`;
  }

  if (kind === "heatmap") {
    const values = series[0].values;
    const top = Math.max(...values, 1);
    const cells = labels.map((label, index) => {
      const [y, m, d] = label.split("-").map(Number);
      const shade = Math.round(240 - (Math.abs(values[index]) / top) * 190);
      return `<rect x="${pad + (d - 1) * 12}" y="${pad + (m - 1) * 15}" width="10" height="13" fill="rgb(${shade},${Math.round(shade * 0.85)},${Math.round(shade * 0.5)})"><title>${esc(label)} ${amount(values[index])}</title></rect>`;
    }).join("");
    return `<svg viewBox="0 0 ${pad * 2 + 31 * 12} ${pad * 2 + 12 * 15}">${cells}</svg>`;
  }

  const step = (width - pad * 2) / Math.max(labels.length, 1);
  if (kind === "line") {
    const points = series[0].values.map((value, index) =>
      `${pad + index * step + step / 2},${height - pad - scale(value)}`).join(" ");
    const dots = points.split(" ").map((point) => {
      const [x, y] = point.split(",");
      return `<circle cx="${x}" cy="${y}" r="2" fill="${PALETTE[0]}"></circle>`;
    }).join("");
    const ticks = labels.filter((_, index) => index % Math.ceil(labels.length / 6) === 0)
      .map((label, index) => `<text x="${pad + index * step * Math.ceil(labels.length / 6) + step / 2}" y="${height - 8}" font-size="10" text-anchor="middle">${esc(label.slice(2))}</text>`).join("");
    return `<svg viewBox="0 0 ${width} ${height}"><polyline points="${points}" fill="none" stroke="${PALETTE[0]}" stroke-width="2"></polyline>${dots}${ticks}</svg>`;
  }

  const group = step;
  const barWidth = Math.max(2, group / (series.length + 1));
  const bars = labels.map((label, index) =>
    series.map((s, si) => {
      const value = s.values[index] ?? 0;
      const barHeight = scale(value);
      const x = pad + index * group + si * barWidth + group / 8;
      const y = height - pad - barHeight;
      return `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" fill="${PALETTE[si % PALETTE.length]}"><title>${esc(label)} ${esc(s.name)} ${amount(value)}</title></rect>`;
    }).join("")).join("");
  const legend = series.map((s, index) =>
    `<rect x="${pad + index * 90}" y="6" width="10" height="10" fill="${PALETTE[index % PALETTE.length]}"></rect><text x="${pad + 14 + index * 90}" y="15" font-size="11">${esc(s.name)}</text>`).join("");
  const ticks = labels.filter((_, index) => index % Math.ceil(labels.length / 8) === 0)
    .map((label, index) => `<text x="${pad + index * group * Math.ceil(labels.length / 8) + group / 2}" y="${height - 8}" font-size="10" text-anchor="middle">${esc(label.slice(2))}</text>`).join("");
  return `<svg viewBox="0 0 ${width} ${height}">${bars}${legend}${ticks}</svg>`;
}

/* ---------- 各页面 ---------- */

async function loadDashboard() {
  const [index, recent] = await Promise.all([api("/api/概览"), api("/api/流水?条数=8")]);
  el("dashboard-cards").innerHTML = [
    ["交易数", index["交易数"]],
    ["科目数", index["科目数"]],
    ["待分类", index["待分类"] + " 笔"],
    ["诊断", `错误 ${index["错误"]} / 警告 ${index["警告"]}`],
  ].map(([label, value]) => `<div class="card"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("");

  el("dashboard-recent").innerHTML = table(
    ["日期", "摘要", "科目", "金额"],
    recent["流水"].slice(0, 8).map((tx) => [
      esc(tx["日期"]), esc(tx["收款方"] || tx["摘要"]),
      esc((tx["分录"][0] || {})["科目"] || ""),
      amount((tx["分录"][0] || {})["金额"] || "0"),
    ]), [3]);

  for (const [id, path] of [
    ["chart-networth", "/api/图表/净资产"],
    ["chart-monthly", "/api/图表/收支"],
    ["chart-expense", "/api/图表/分类"],
    ["chart-heatmap", "/api/图表/日历"],
    ["chart-waterfall", "/api/图表/现金流"],
  ]) {
    try {
      el(id).innerHTML = renderChart(await api(path));
    } catch (error) {
      el(id).innerHTML = `<p class="hint">${esc(error.message)}</p>`;
    }
  }
}

async function loadFlow() {
  const query = new URLSearchParams();
  const map = { "flow-月": "月", "flow-科目": "科目", "flow-标签": "标签", "flow-收款方": "收款方", "flow-关键词": "关键词" };
  for (const [id, key] of Object.entries(map)) if (el(id).value) query.set(key, el(id).value);
  const data = await api(`/api/流水?${query}`);
  el("flow-list").innerHTML = table(
    ["日期", "标志", "收款方/摘要", "科目", "金额", "币种"],
    data["流水"].flatMap((tx) => tx["分录"].map((posting) => [
      esc(tx["日期"]), esc(tx["标志"]), esc(tx["收款方"] || tx["摘要"]),
      esc(posting["科目"]), amount(posting["金额"]), esc(posting["币种"]),
    ])), [4]);
}

async function loadUncategorized() {
  const data = await api("/api/待分类");
  const rows = data["待分类"].map((row) => [
    esc(row["收款方"]), String(row["笔数"]),
    Object.entries(row["金额"]).map(([c, v]) => `${amount(v)} ${esc(c)}`).join("，"),
    `<input data-payee="${esc(row["收款方"])}" placeholder="目标科目"><button data-classify="${esc(row["收款方"])}">归类</button>`,
  ]);
  el("uncategorized").innerHTML = data["合计笔数"]
    ? table(["收款方", "笔数", "金额", "操作"], rows, [1, 2])
    : `<p class="hint">没有待分类交易。</p>`;
}

async function loadAccounts() {
  const [balance, accounts] = await Promise.all([api("/api/余额"), api("/api/科目")]);
  el("account-tree").innerHTML = balance["树"].map((node) => {
    const values = Object.entries(node["余额"]).map(([c, v]) => `${amount(v)} ${esc(c)}`).join("，");
    return `<div class="tree-row" data-account="${esc(node["科目"])}" style="padding-left:${node["层级"] * 18}px">${esc(node["名称"])}<span class="amount">${values}</span></div>`;
  }).join("") || `<p class="hint">暂无余额。</p>`;

  const detail = accounts["科目"].map((row) => {
    const trend = row["趋势"].map(Number);
    const points = trend.length > 1
      ? trend.map((value, index) => `${index * 30},${60 - Math.max(0, Math.min(60, value / (Math.max(...trend.map(Math.abs), 1) / 60)))}`).join(" ")
      : "";
    return `<div class="panel"><b>${esc(row["科目"])}</b>
      ${Object.entries(row["余额"]).map(([c, v]) => `${amount(v)} ${esc(c)}`).join("，")}
      <svg viewBox="0 0 ${Math.max(trend.length * 30, 60)} 60" width="240" height="60">
        <polyline points="${points}" fill="none" stroke="#4c78a8" stroke-width="2"></polyline>
      </svg></div>`;
  }).join("");
  el("account-detail").innerHTML = detail || `<p class="hint">暂无数据。</p>`;
}

async function loadReport() {
  const kind = el("report-kind").value;
  const query = new URLSearchParams();
  if (el("report-月").value) query.set("月", el("report-月").value);
  if (el("report-年").value) query.set("年", el("report-年").value);
  const data = await api(`/api/报表/${encodeURIComponent(kind)}?${query}`);
  const body = data["数据"];
  let html = `<h3>${esc(data["类型"])}</h3>`;

  if (data["类型"] === "资产负债表") {
    html += table(["项目", "金额"], [
      ...body["资产"].map(([name, value]) => ["资产 " + esc(name), amount(value)]),
      ["<b>资产合计</b>", `<b>${amount(body["资产合计"])}</b>`],
      ...body["负债"].map(([name, value]) => ["负债 " + esc(name), amount(value)]),
      ["<b>负债合计</b>", `<b>${amount(body["负债合计"])}</b>`],
      ...body["权益"].map(([name, value]) => ["权益 " + esc(name), amount(value)]),
      ["当期损益", amount(body["当期损益"])],
    ], [1]);
    html += `<p class="hint">${body["平衡"] ? "平衡校验通过" : "不平衡，请运行 knot 检查"}</p>`;
  } else if (data["类型"] === "利润表") {
    html += table(["项目", "金额"], [
      ...body["收入"].map(([name, value]) => ["收入 " + esc(name), amount(value)]),
      ["<b>收入合计</b>", `<b>${amount(body["收入合计"])}</b>`],
      ...body["费用"].map(([name, value]) => ["费用 " + esc(name), amount(value)]),
      ["<b>费用合计</b>", `<b>${amount(body["费用合计"])}</b>`],
      ["<b>净利润</b>", `<b>${amount(body["净利润"])}</b>`],
    ], [1]);
  } else if (data["类型"] === "现金流量表") {
    html += table(["类别", "净流量"], [
      ["经营", amount(body["经营"])], ["投资", amount(body["投资"])], ["筹资", amount(body["筹资"])],
      ["<b>净流量</b>", `<b>${amount(body["净流量"])}</b>`],
    ], [1]);
  } else if (Array.isArray(body)) {
    const keys = Object.keys(body[0] || {});
    html += table(keys, body.map((row) => keys.map((key) =>
      typeof row[key] === "number" || /^[-\d,.]/.test(String(row[key])) ? amount(row[key]) : esc(row[key]))));
  } else {
    html += `<pre>${esc(JSON.stringify(body, null, 2))}</pre>`;
  }
  el("report-body").innerHTML = html;
}

async function runImport(write) {
  const payload = {
    来源: el("import-source").value,
    文件: el("import-path").value.split(",").map((s) => s.trim()).filter(Boolean),
    账户: el("import-account").value || undefined,
  };
  if (!payload.文件.length) { el("import-body").innerHTML = `<p class="hint">请填写账单路径。</p>`; return; }
  const data = await post(write ? "/api/导入" : "/api/导入预览", payload);
  el("import-body").innerHTML = data["结果"].map((row) => `
    <h3>${esc(row["文件"])}</h3>
    <p>总 ${row["总行数"]} 行 · 可导入 ${row["可导入"]} · 重复 ${row["重复"]} · 待分类 ${row["待分类"]} · 解析失败 ${row["解析失败"]}</p>
    ${table(["日期", "收款方", "科目", "金额"], (row["预览"] || []).map((item) =>
      [esc(item["日期"]), esc(item["收款方"]), esc(item["科目"]), amount(item["金额"])]), [3])}
  `).join("");
}

/* ---------- 事件绑定与 SSE ---------- */

const loaders = {
  dashboard: loadDashboard,
  entry: loadUncategorized,
  flow: loadFlow,
  accounts: loadAccounts,
  reports: loadReport,
  import: () => { el("import-body").innerHTML = ""; },
};
let currentPage = "dashboard";

async function refresh() {
  el("status").textContent = "刷新中…";
  try {
    await loaders[currentPage]();
    el("status").textContent = `已更新 ${new Date().toLocaleTimeString("zh-CN")}`;
  } catch (error) {
    el("status").textContent = `错误：${error.message}`;
  }
}

el("tabs").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-page]");
  if (!button) return;
  currentPage = button.dataset.page;
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b === button));
  document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.id === currentPage));
  refresh();
});

el("entry-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = Object.fromEntries([...form.entries()].filter(([, value]) => value));
  if (payload["标签"]) payload["标签"] = payload["标签"].split(/[,，]/).map((s) => s.trim()).filter(Boolean);
  try {
    const result = await post("/api/记一笔", payload);
    el("entry-result").textContent = `已记入 ${result["已记入"]}\n${JSON.stringify(result["交易"], null, 2)}`;
    await loadUncategorized();
  } catch (error) {
    el("entry-result").textContent = `失败：${error.message}`;
  }
});

el("uncategorized").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-classify]");
  if (!button) return;
  const payee = button.dataset.classify;
  const input = el("uncategorized").querySelector(`input[data-payee="${CSS.escape(payee)}"]`);
  try {
    const result = await post("/api/归类", { 收款方: payee, 科目: input.value });
    el("status").textContent = `已归类 ${result["已归类"]} 笔`;
    await loadUncategorized();
  } catch (error) {
    el("status").textContent = `归类失败：${error.message}`;
  }
});

async function loadBudget() {
  const query = new URLSearchParams();
  if (el("report-月").value) query.set("月", el("report-月").value);
  const data = await api(`/api/预算?${query}`);
  if (!data["进度"].length) {
    el("budget-body").innerHTML = `<p class="hint">账本里还没有预算（可在年份文件写 <code>2026-01-01 budget monthly 费用:餐饮 2000.00 CNY</code>）。</p>`;
    return;
  }
  const chart = await api(`/api/图表/预算?${query}`);
  el("budget-body").innerHTML =
    renderChart(chart) +
    table(["科目", "月份", "预算", "实际", "剩余", "进度"],
      data["进度"].map((row) => [esc(row["科目"]), esc(row["月份"]), amount(row["预算"]),
        amount(row["实际"]), amount(row["剩余"]), esc(row["进度"])]), [2, 3, 4]) +
    `<p class="hint">合计：预算 ${esc(data["合计"]["预算合计"])} · 实际 ${esc(data["合计"]["实际合计"])} · 剩余 ${esc(data["合计"]["剩余合计"])}</p>`;
}

el("flow-search").addEventListener("click", loadFlow);
el("report-load").addEventListener("click", loadReport);
el("budget-load").addEventListener("click", loadBudget);
el("import-preview").addEventListener("click", () => runImport(false));
el("import-write").addEventListener("click", () => runImport(true));
el("account-tree").addEventListener("click", (event) => {
  const row = event.target.closest(".tree-row");
  if (row) el("status").textContent = `科目：${row.dataset.account}`;
});

function connectSSE() {
  const source = new EventSource(`/api/变更?口令=${encodeURIComponent(TOKEN)}`);
  source.onmessage = (event) => {
    const change = JSON.parse(event.data);
    if (change["事件"] === "变更") {
      el("status").textContent = `账本已变更（${change["交易数"]} 笔），刷新中…`;
      refresh();
    }
  };
  source.onerror = () => { el("status").textContent = "变更监听断开，稍后重连"; };
}

refresh();
connectSSE();
