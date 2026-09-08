"use strict";
const ns = id => document.getElementById(`ns-${id}`);
let nsGeneration = 0, nsPayload = null, nsConfig = {}, nsView = "dashboard";

async function nsRequest(path, body = {}) {
  let response;
  try { response = await fetch(`/api/northstar/${path}`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body), cache: "no-store"}); }
  catch { throw new Error(StudentWorkspace.errorMessage(0)); }
  if (!response.ok) {
    throw new Error(StudentWorkspace.errorMessage(response.status));
  }
  try { return await response.json(); } catch { throw new Error(StudentWorkspace.errorMessage("malformed")); }
}

let nsWorkspace = null;
function nsShow(view, focus = false) { nsWorkspace?.show(view, focus); }

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
  ns("login").hidden = true; ns("workspace").hidden = false;
  ns("sources").replaceChildren();
  nsWorkspace = StudentWorkspace.mount(ns("results"), payload.report, nsConfig, {
    section: nsView, navigation: ns("nav"), focusTarget: ns("content"), inspector: false,
    retrieval: payload.retrieval, registration_duration: payload.registration_duration,
    onSection: section => { nsView = section; ns("title").textContent = StudentWorkspace.tabs(nsConfig).find(([key]) => key === section)?.[1] || "Overview"; }
  });
}

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
    await nsRequest("logout"); nsWorkspace?.destroy(); nsWorkspace = null; nsPayload = null; ns("workspace").hidden = true;
    ["results", "debug", "sources"].forEach(id => ns(id).replaceChildren()); document.querySelector(".ns-debug").open = false;
    ns("login").hidden = false; ns("message").textContent = "Session ended. Choose another demonstration account."; ns("subject").focus();
  } catch (error) { ns("message").textContent = error.message; }
});
ns("form").querySelector("button").disabled = true;
fetch("/api/northstar/presentation", {cache: "no-store"}).then(response => { if (!response.ok) throw new Error("Unavailable"); return response.json(); }).then(payload => {
  nsConfig = {...payload.config, evidence_origin: "demo_record", capabilities: {course_exploration: true, export: true}};
  ns("brand").textContent = nsConfig.institution_name;
  ns("nav").innerHTML = StudentWorkspace.navigation(nsConfig, "overview");
  ns("subject").innerHTML = payload.cases.map(item => `<option value="${esc(item.subject)}">${esc(item.subject)} · ${esc(item.label)}</option>`).join("");
  ns("form").querySelector("button").disabled = false;
}).catch(() => { ns("message").textContent = "The demo directory is unavailable. Reload this page to try again."; });
