"use strict";
const ns = id => document.getElementById(`ns-${id}`);
let nsGeneration = 0, nsPayload = null, nsConfig = {}, nsView = "dashboard";

async function nsRequest(path, body = {}) {
  let response;
  try { response = await fetch(`/api/northstar/${path}`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body), cache: "no-store"}); }
  catch { throw new Error("The service could not be reached. Try again; no new academic conclusion was made."); }
  if (!response.ok) {
    const messages = {401: "The demo account or session could not be confirmed. Log in again with a listed account.", 422: "The selected release or supplied evidence could not be used. Try again or ask for help with the demonstration.", 503: "Your record or reasoning service is unavailable. Try again; no new academic conclusion was made."};
    throw new Error(messages[response.status] || "Reasoning is unavailable. Try again; no new conclusion was made.");
  }
  try { return await response.json(); } catch { throw new Error("The service returned an unusable response. Please try again."); }
}

function nsShow(view, focus = false) {
  if (!nsPayload || !Object.hasOwn(nsConfig.navigation, view)) return;
  nsView = view;
  ns("title").textContent = nsConfig.navigation[view];
  ns("nav").querySelectorAll("button").forEach(button => button.setAttribute("aria-current", button.dataset.view === view ? "page" : "false"));
  const projection = nsPayload.report.student_reasoning_view;
  ns("sources").replaceChildren();
  if (view === "dashboard") ns("results").innerHTML = StudentPortal.dashboard(projection, nsConfig);
  if (view === "curriculum") ns("results").innerHTML = StudentPortal.curriculum(projection, nsConfig);
  if (view === "evidence") ns("results").innerHTML = StudentPortal.evidence(projection, nsConfig, nsPayload.retrieval, nsPayload.registration_duration);
  if (view === "sources") {
    ns("results").innerHTML = "<header class='portal-heading'><h2>Why these rules are represented</h2><p>Institutional sources establish the represented rules. Student evidence is shown separately in Academic Evidence.</p></header>";
    ns("sources").innerHTML = StudentPortal.sources(projection, false, nsConfig);
  }
  if (view === "help") ns("results").innerHTML = StudentPortal.help(nsConfig);
  if (focus) ns("content").focus();
}

function nsRender(payload) {
  nsPayload = payload;
  ns("programme").textContent = payload.report.programme_name;
  ns("profile").textContent = nsConfig.student_label;
  ns("release").textContent = `${nsConfig.records_name}. Information retrieved for this session.`;
  const unavailable = payload.retrieval.filter(item => item.state === "UNAVAILABLE_OR_MALFORMED");
  ns("domain-warning").hidden = !unavailable.length;
  ns("domain-warning").textContent = unavailable.length ? "Some evidence could not be retrieved or used. Open Academic Evidence for the affected categories. This is not an academic failure." : "";
  const outcomes = payload.report.advisor_reasoning_view.advisor_detail.canonical_outcomes;
  ns("debug").innerHTML = `<p>Subject: ${esc(payload.subject_reference)} | Release: ${esc(payload.release_id)}</p><p>Records boundary: ${esc(nsConfig.records_name)}</p>${payload.retrieval.map(item => `<p>${esc(titleCase(item.domain))}: ${esc(item.state)}</p>`).join("")}
    <table><thead><tr><th>Canonical assessment</th><th>Outcome</th><th>Complete</th><th>Authority</th></tr></thead><tbody>${outcomes.map(item => `<tr><td>${esc(item.identity)}</td><td>${esc(item.outcome)}</td><td>${esc(item.assessment_complete)}</td><td>${esc(item.status)}</td></tr>`).join("")}</tbody></table>
    <details><summary>Source identities and relationships</summary><pre>${esc(JSON.stringify(payload.report.student_reasoning_view.source_relationships, null, 2))}</pre></details>
    <details><summary>Full reasoning detail and recognition explanations</summary><pre>${esc(JSON.stringify(payload.report.advisor_reasoning_view, null, 2))}</pre></details>
    <details><summary>Entry and registration detail</summary><pre>${esc(JSON.stringify({entry: payload.report.programme_entry_eligibility_assessment, registration: payload.registration_duration}, null, 2))}</pre></details>`;
  ns("login").hidden = true; ns("workspace").hidden = false; nsShow(nsView);
}

document.addEventListener("click", event => { const button = event.target.closest("button[data-view]"); if (button) nsShow(button.dataset.view, true); });
ns("form").addEventListener("submit", async event => {
  event.preventDefault(); const generation = ++nsGeneration; const button = event.currentTarget.querySelector("button");
  button.disabled = true; nsPayload = null; ns("workspace").hidden = true; ns("results").replaceChildren(); ns("message").textContent = "Confirming the demo account...";
  try {
    await nsRequest("login", {subject: ns("subject").value, access_code: ns("code").value});
    ns("message").textContent = "Retrieving your current record and assessing the supplied evidence...";
    const payload = await nsRequest("analyse"); if (generation !== nsGeneration) return;
    nsView = "dashboard"; nsRender(payload); ns("message").textContent = "Evidence retrieved for this session."; ns("content").focus();
  } catch (error) { ns("message").textContent = error.message; } finally { button.disabled = false; }
});
ns("refresh").addEventListener("click", async () => {
  const generation = ++nsGeneration; ns("refresh").disabled = true; ns("message").textContent = "Retrieving the current record...";
  try { const payload = await nsRequest("analyse"); if (generation !== nsGeneration) return; nsRender(payload); ns("message").textContent = "Evidence retrieved again for this session."; }
  catch (error) { ns("message").textContent = `${error.message} The previous assessment remains displayed; it has not been refreshed.`; }
  finally { ns("refresh").disabled = false; }
});
ns("switch").addEventListener("click", async () => {
  ++nsGeneration;
  try {
    await nsRequest("logout"); nsPayload = null; ns("workspace").hidden = true;
    ["results", "debug", "sources"].forEach(id => ns(id).replaceChildren()); document.querySelector(".ns-debug").open = false;
    ns("login").hidden = false; ns("message").textContent = "Session ended. Choose another demonstration account."; ns("subject").focus();
  } catch (error) { ns("message").textContent = error.message; }
});
ns("form").querySelector("button").disabled = true;
fetch("/api/northstar/presentation", {cache: "no-store"}).then(response => { if (!response.ok) throw new Error("Unavailable"); return response.json(); }).then(payload => {
  nsConfig = payload.config; ns("brand").textContent = nsConfig.institution_name;
  ns("nav").innerHTML = Object.entries(nsConfig.navigation).map(([key, title]) => `<button data-view="${esc(key)}">${esc(title)}</button>`).join("");
  ns("subject").innerHTML = payload.cases.map(item => `<option value="${esc(item.subject)}">${esc(item.subject)} · ${esc(item.label)}</option>`).join("");
  ns("form").querySelector("button").disabled = false;
}).catch(() => { ns("message").textContent = "The demo directory is unavailable. Reload this page to try again."; });
