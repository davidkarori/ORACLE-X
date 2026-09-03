const $ = (id) => document.getElementById(id);
let currentRun = null;
let pollTimer = null;
const roles = ["ATHENA", "HADES", "HERMES", "MORPHEUS"];

function html(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[character]);
}

function committeeSkeleton() {
  $("committee").innerHTML = roles.map(role => `<article class="agent pending"><strong>${role}</strong></article>`).join("");
}

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  const text = await response.text();
  let payload;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = null; }
  if (!response.ok) throw new Error(payload?.detail || text || response.statusText);
  return payload;
}

async function loadHealth() {
  const health = await api("/api/health");
  const active = Object.entries(health.integrations).filter(([, value]) => value).map(([key]) => key.toUpperCase());
  $("integrationPill").textContent = active.length ? active.join(" + ") : "FIXTURE MODE";
  $("killSwitch").checked = health.kill_switch;
}

async function loadRuns() {
  const runs = await api("/api/runs");
  if (!runs.length) return;
  $("runList").innerHTML = runs.map(run => `<button class="run-item ${run.id === currentRun ? "active" : ""}" data-id="${html(run.id)}"><span><strong>${html(run.symbol)}</strong><small>${html(run.mode)}</small></span><span>${html(run.state)}</span></button>`).join("");
  document.querySelectorAll(".run-item").forEach(button => button.addEventListener("click", () => selectRun(button.dataset.id)));
}

async function startRun() {
  $("runButton").disabled = true;
  clearInterval(pollTimer);
  try {
    const body = {
      symbol: $("symbol").value,
      execute: $("execute").checked,
      simulate_lifecycle: $("simulate").checked,
      risk_profile: $("riskProfile").value,
    };
    const run = await api("/api/runs", {method: "POST", body: JSON.stringify(body)});
    currentRun = run.id;
    committeeSkeleton();
    await renderRun(run.id);
    if (run.status === "RUNNING") pollTimer = setInterval(() => renderRun(run.id), 900);
  } catch (error) {
    showNotice(error.message, true);
    $("runButton").disabled = false;
  }
}

async function selectRun(id) {
  currentRun = id;
  clearInterval(pollTimer);
  await renderRun(id);
}

async function renderRun(id) {
  try {
    const replay = await api(`/api/runs/${id}/replay`);
    const run = replay.run;
    $("caseTitle").textContent = `${run.symbol} OPTIONS CASE`;
    $("state").textContent = run.state;
    $("providerLabel").textContent = `${run.mode.toUpperCase()} / ${run.risk_profile}`;
    renderCommittee(run.decisions);
    renderMcp(run.mcp_calls);
    renderStrategy(run);
    renderGates(run);
    renderPosition(run);
    renderAutopsy(run);
    renderTimeline(replay.events);
    showNotice(run.error || statusMessage(run), Boolean(run.error || run.status === "REJECTED"));
    await loadRuns();
    if (run.status !== "RUNNING") {
      clearInterval(pollTimer);
      $("runButton").disabled = false;
    }
  } catch (error) {
    clearInterval(pollTimer);
    showNotice(error.message, true);
    $("runButton").disabled = false;
  }
}

function statusMessage(run) {
  if (run.status === "RUNNING") return "The committee is working through the controlled lifecycle.";
  if (run.status === "EXECUTION_READY") return "Every deterministic gate passed. No broker mutation was requested.";
  if (run.status === "SUBMITTED") return `Paper order submitted: ${run.broker_order?.status || "pending"}.`;
  if (run.status === "LEARNED") return "Fixture lifecycle complete. Morpheus stored an advisory-only lesson; no broker was contacted.";
  if (run.status === "REJECTED") return `Flow blocked: ${run.risk?.reason_codes?.join(", ") || run.execution_guard?.reason_codes?.join(", ") || "committee objection"}.`;
  return run.status;
}

function showNotice(message, error = false) {
  $("notice").textContent = message;
  $("notice").className = error ? "notice error" : "notice";
}

function renderCommittee(decisions) {
  const byRole = {};
  decisions.forEach(item => { byRole[item.role] = item; });
  $("committee").innerHTML = roles.map(role => {
    const item = byRole[role];
    if (!item) return `<article class="agent pending"><strong>${role}</strong></article>`;
    const content = {
      ATHENA: [item.bias, item.thesis],
      HADES: [item.recommendation, item.critique],
      HERMES: [item.recommendation, item.research_summary],
      MORPHEUS: [item.recommendation, item.outcome_summary],
    }[role];
    const disagreement = ["REJECT", "REVISE", "BLOCKED", "RETIRE"].includes(content[0]);
    return `<article class="agent ${disagreement ? "disagreement" : ""}"><header><strong>${role}</strong><span class="decision">${html(content[0])}</span></header><p>${html(content[1])}</p><small>${html(item.provider)} / confidence ${Math.round(item.confidence * 100)}%</small></article>`;
  }).join("");
}

function renderMcp(calls) {
  if (!calls?.length) {
    $("mcpCalls").className = "mcp-grid empty-panel";
    $("mcpCalls").textContent = "No mediated tool calls.";
    return;
  }
  $("mcpCalls").className = "mcp-grid";
  $("mcpCalls").innerHTML = calls.map(call => `<div class="mcp-call ${call.success ? "" : "failed"}"><span>${call.success ? "READ" : "FAIL"}</span><strong>${html(call.tool_name)}</strong><small>${html(call.requesting_agent)} · ${Number(call.latency_ms)} ms · ${html(call.result_metadata.transport || "unknown")}</small></div>`).join("");
}

function money(value) {
  return value == null ? "UNBOUNDED" : `$${Number(value).toFixed(2)}`;
}

function renderStrategy(run) {
  if (!run.strategy || !run.quant) {
    $("strategy").className = "data-panel empty-panel";
    $("strategy").textContent = "No normalized strategy.";
    return;
  }
  const values = [
    ["STRATEGY", run.strategy.strategy_type], ["NET DEBIT", money(run.quant.net_debit)],
    ["NET CREDIT", money(run.quant.net_credit)], ["MAX LOSS", money(run.quant.max_loss)],
    ["MAX PROFIT", money(run.quant.max_profit)], ["REWARD / RISK", run.quant.reward_risk ?? "N/A"],
    ["MAX SPREAD", `${run.quant.max_spread_pct.toFixed(2)}%`], ["EXPOSURE", money(run.quant.exposure)],
    ["GREEKS", run.quant.greeks_status],
  ];
  const legs = run.strategy.legs.map((leg, index) => `<div class="leg"><b>${index + 1}</b> ${html(leg.side)} ${Number(leg.ratio)} · ${html(leg.contract_symbol)} · ${money(leg.midpoint)} · ${html(leg.position_intent)}</div>`).join("");
  const scenarios = run.quant.scenario_pnl.map(item => `<span class="scenario ${item.pnl < 0 ? "negative" : "positive"}">${html(item.label)}<b>${money(item.pnl)}</b></span>`).join("");
  $("strategy").className = "data-panel";
  $("strategy").innerHTML = `<div class="metrics">${values.map(([key, value]) => `<div class="metric"><small>${html(key)}</small><strong>${html(value)}</strong></div>`).join("")}</div><div class="legs">${legs}</div><div class="scenarios">${scenarios}</div>`;
}

function renderGates(run) {
  const stress = run.stress ? `<div class="stress ${run.stress.recommendation.toLowerCase()}"><strong>STRESS ${run.stress.recommendation}</strong><span>${run.stress.scenarios.filter(item => item.breaks_thesis).length} break scenarios</span></div>` : "";
  const gates = [...(run.risk?.gates || []), ...(run.execution_guard?.checks || [])];
  if (!gates.length) {
    $("gates").className = "data-panel empty-panel";
    $("gates").textContent = "No risk evaluation.";
    return;
  }
  $("gates").className = "data-panel";
  $("gates").innerHTML = stress + gates.map(gate => `<div class="gate ${gate.passed ? "" : "fail"}"><span class="status">${gate.passed ? "OK" : "X"}</span><strong>${html(gate.code.replaceAll("_", " "))}</strong><small>${html(typeof gate.measured === "object" ? JSON.stringify(gate.measured) : gate.measured)}</small></div>`).join("");
}

function renderPosition(run) {
  if (!run.position) {
    $("position").className = "data-panel empty-panel";
    $("position").textContent = `No position. Current state: ${run.state}.`;
    return;
  }
  const position = run.position;
  $("position").className = "data-panel";
  $("position").innerHTML = `<div class="metrics"><div class="metric"><small>STATUS</small><strong>${position.status}</strong></div><div class="metric"><small>ENTRY VALUE</small><strong>${money(position.entry_value)}</strong></div><div class="metric"><small>REALIZED P&L</small><strong>${money(position.realized_pnl)}</strong></div></div><p class="panel-copy">${position.simulated ? "Fixture simulation: no broker mutation." : "Alpaca paper position."}</p>`;
}

function renderAutopsy(run) {
  if (!run.autopsy || !run.memory) {
    $("autopsy").className = "data-panel empty-panel";
    $("autopsy").textContent = "No completed autopsy.";
    return;
  }
  $("autopsy").className = "data-panel";
  $("autopsy").innerHTML = `<div class="autopsy-head"><strong>${html(run.autopsy.recommendation)}</strong><span>NO EXECUTION AUTHORITY</span></div><p class="panel-copy">${html(run.autopsy.outcome_summary)}</p><ul>${run.memory.lessons.map(lesson => `<li>${html(lesson)}</li>`).join("")}</ul>`;
}

function renderTimeline(events) {
  $("eventCount").textContent = `${events.length} EVENTS`;
  $("timeline").innerHTML = events.map(event => {
    const detail = event.payload.reason || event.payload.message || event.payload.to || event.payload.symbol || event.payload.tool_name || event.payload.strategy_type || "Recorded";
    return `<div class="event"><time>${new Date(event.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"})}</time><span class="kind">${html(event.kind)}</span><span class="actor">${html(event.actor)}</span><p>${html(detail)}</p></div>`;
  }).join("") || `<p class="empty">Audit events will appear here.</p>`;
}

$("runButton").addEventListener("click", startRun);
$("refreshButton").addEventListener("click", loadRuns);
$("killSwitch").addEventListener("change", async event => {
  const reason = encodeURIComponent(event.target.checked ? "Operator activated War Room kill switch" : "Operator cleared War Room kill switch");
  await api(`/api/system/kill-switch?active=${event.target.checked}&reason=${reason}`, {method: "POST"});
  showNotice(event.target.checked ? "Kill switch active. New approvals will fail closed." : "Kill switch cleared for paper-mode analysis.");
});

committeeSkeleton();
Promise.all([loadHealth(), loadRuns()]).catch(error => showNotice(error.message, true));
