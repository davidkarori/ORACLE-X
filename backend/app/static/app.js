const $ = (id) => document.getElementById(id);
let currentRun = null;
let pollTimer = null;

const roles = ["ATHENA", "HADES", "HERMES", "MORPHEUS"];

function committeeSkeleton() {
  $("committee").innerHTML = roles.map(role => `<article class="agent pending"><strong>${role}</strong></article>`).join("");
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: {"Content-Type": "application/json"}, ...options });
  if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
  return response.json();
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
  $("runList").innerHTML = runs.map(run => `<button class="run-item ${run.id === currentRun ? "active" : ""}" data-id="${run.id}"><span><strong>${run.symbol}</strong><small>${run.mode}</small></span><span>${run.state}</span></button>`).join("");
  document.querySelectorAll(".run-item").forEach(button => button.addEventListener("click", () => selectRun(button.dataset.id)));
}

async function startRun() {
  $("runButton").disabled = true;
  try {
    const run = await api("/api/runs", {method: "POST", body: JSON.stringify({symbol: $("symbol").value, execute: $("execute").checked})});
    currentRun = run.id;
    committeeSkeleton();
    await renderRun(run.id);
    pollTimer = setInterval(() => renderRun(run.id), 900);
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
    $("providerLabel").textContent = run.mode.toUpperCase();
    renderCommittee(run.decisions);
    renderStrategy(run);
    renderGates(run);
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
  if (run.status === "EXECUTION_READY") return "All deterministic gates passed. Dry run complete; no broker mutation was requested.";
  if (run.status === "SUBMITTED") return `Paper order submitted: ${run.broker_order?.status || "pending"}.`;
  if (run.status === "REJECTED") return `Execution blocked: ${run.risk?.reason_codes?.join(", ") || run.execution_guard?.reason_codes?.join(", ")}.`;
  return run.status;
}

function showNotice(message, error = false) {
  $("notice").textContent = message;
  $("notice").className = error ? "notice error" : "notice";
}

function renderCommittee(decisions) {
  const byRole = Object.fromEntries(decisions.map(item => [item.role, item]));
  $("committee").innerHTML = roles.map(role => {
    const item = byRole[role];
    if (!item) return `<article class="agent pending"><strong>${role}</strong></article>`;
    return `<article class="agent"><header><strong>${role}</strong><span class="decision">${item.decision}</span></header><p>${item.summary}</p><small>${item.provider} / confidence ${Math.round(item.confidence * 100)}%</small></article>`;
  }).join("");
}

function renderStrategy(run) {
  if (!run.strategy || !run.quant) { $("strategy").className = "data-panel empty-panel"; $("strategy").textContent = "No normalized strategy."; return; }
  const leg = run.strategy.legs[0];
  const values = [
    ["STRATEGY", run.strategy.strategy_type], ["MIDPOINT", `$${run.quant.midpoint.toFixed(2)}`], ["SPREAD", `${run.quant.spread_pct.toFixed(2)}%`],
    ["MAX LOSS", `$${run.quant.max_loss.toFixed(2)}`], ["BREAK EVEN", `$${run.strategy.break_even[0].toFixed(2)}`], ["QUANTITY", run.quant.position_quantity]
  ];
  $("strategy").className = "data-panel";
  $("strategy").innerHTML = `<div class="metrics">${values.map(([k,v]) => `<div class="metric"><small>${k}</small><strong>${v}</strong></div>`).join("")}</div><div class="leg">BUY ${leg.quantity} &middot; ${leg.contract_symbol} &middot; ${leg.expiration} &middot; $${leg.strike.toFixed(2)} CALL</div>`;
}

function renderGates(run) {
  const gates = [...(run.risk?.gates || []), ...(run.execution_guard?.checks || [])];
  if (!gates.length) { $("gates").className = "data-panel empty-panel"; $("gates").textContent = "No risk evaluation."; return; }
  $("gates").className = "data-panel";
  $("gates").innerHTML = gates.map(gate => `<div class="gate ${gate.passed ? "" : "fail"}"><span class="status">${gate.passed ? "OK" : "X"}</span><strong>${gate.code.replaceAll("_", " ")}</strong><small>${String(gate.measured)}</small></div>`).join("");
}

function renderTimeline(events) {
  $("eventCount").textContent = `${events.length} EVENTS`;
  $("timeline").innerHTML = events.map(event => `<div class="event"><time>${new Date(event.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"})}</time><span class="kind">${event.kind}</span><span class="actor">${event.actor}</span><p>${event.payload.reason || event.payload.message || event.payload.to || event.payload.symbol || "Recorded"}</p></div>`).join("") || `<p class="empty">Audit events will appear here.</p>`;
}

$("runButton").addEventListener("click", startRun);
$("refreshButton").addEventListener("click", loadRuns);
$("killSwitch").addEventListener("change", async (event) => {
  await api(`/api/system/kill-switch?active=${event.target.checked}`, {method: "POST"});
  showNotice(event.target.checked ? "Kill switch active. New approvals will fail closed." : "Kill switch cleared for paper-mode analysis.");
});

committeeSkeleton();
Promise.all([loadHealth(), loadRuns()]).catch(error => showNotice(error.message, true));
