"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character]));

const adminState = { permissions: null };

async function api(url, options = {}) {
  const { headers = {}, ...fetchOptions } = options;
  const response = await fetch(url, {
    ...fetchOptions,
    headers: { Accept: "application/json", ...headers },
    credentials: "same-origin",
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "The governance status could not be loaded.");
  return payload;
}

async function loadGovernance() {
  try {
    const status = await api("/api/v1/governance/status");
    const ok = status.integrity === "verified";
    $("integrityBadge").className = `badge ${ok ? "verified" : "conflict"}`;
    $("integrityBadge").textContent = ok ? "Baseline verified" : "Attention required";
    $("releaseSeal").className = `release-seal ${ok ? "ok" : "bad"}`;
    $("releaseSeal").innerHTML = `<span class="badge ${ok ? "verified" : "conflict"}">${ok ? "Integrity verified" : "Integrity warning"}</span><strong>${esc(status.release?.release_id || "No release")}</strong><small>${esc(status.message)}</small>`;
    const release = status.release || {};
    $("releaseMetrics").innerHTML = `
      <div class="release-metric"><strong>${esc(release.academic_year || "—")}</strong><span>academic year</span></div>
      <div class="release-metric"><strong>${esc(release.file_count ?? "—")}</strong><span>catalogue files</span></div>
      <div class="release-metric"><strong>${esc(release.state || "—")}</strong><span>release state</span></div>
      <div class="release-metric"><strong>${esc(String(release.content_sha256 || "—").slice(0, 12))}</strong><span>content fingerprint</span></div>
    `;
    const verification = status.verification || {};
    $("integrityDetail").innerHTML = `
      <div class="integrity-list">
        <div><span>Missing files</span><strong class="${verification.missing?.length ? "bad" : "ok"}">${esc(verification.missing?.length || 0)}</strong></div>
        <div><span>Changed files</span><strong class="${verification.changed?.length ? "bad" : "ok"}">${esc(verification.changed?.length || 0)}</strong></div>
        <div><span>Unexpected files</span><strong class="${verification.unexpected?.length ? "bad" : "ok"}">${esc(verification.unexpected?.length || 0)}</strong></div>
        <div><span>Aggregate content hash</span><strong class="${verification.content_hash_matches ? "ok" : "bad"}">${verification.content_hash_matches ? "Matches" : "Mismatch"}</strong></div>
      </div>
      <div class="message neutral">${esc(status.publication_note || "Publication remains disabled.")}</div>
    `;
  } catch (error) {
    $("integrityBadge").className = "badge conflict";
    $("integrityBadge").textContent = "Unavailable";
    $("releaseSeal").className = "release-seal bad";
    $("releaseSeal").innerHTML = `<strong>Status unavailable</strong><small>${esc(error.message)}</small>`;
    $("releaseMetrics").innerHTML = `<div class="message error">${esc(error.message)}</div>`;
  }
}

function setMessage(id, kind, message) {
  const node = $(id);
  if (!node) return;
  node.className = `message ${kind}`;
  node.textContent = message;
}

function populateAdminForm(permissions) {
  const roleSelect = $("actorRole");
  const fieldSelect = $("editField");
  roleSelect.innerHTML = permissions.roles
    .map(role => `<option value="${esc(role.role)}">${esc(role.label)}</option>`)
    .join("");
  fieldSelect.innerHTML = permissions.quick_edit.allowed_fields
    .map(field => `<option value="${esc(field.field)}">${esc(field.label)}</option>`)
    .join("");
  $("submitQuickEdit").disabled = !(permissions.writes_enabled && permissions.write_token_configured);
}

function renderRoleMatrix(permissions) {
  $("roleMatrix").innerHTML = `
    <div class="role-row heading">
      <span>Role</span><span>Scope</span><span>Tier 1 fields</span><span>Review</span><span>Release</span>
    </div>
    ${permissions.roles.map(role => `
      <div class="role-row">
        <strong>${esc(role.label)}</strong>
        <span>${esc(role.scope)}</span>
        <span>${role.tier_1_quick_edit.length ? role.tier_1_quick_edit.map(esc).join(", ") : "None"}</span>
        <span>${role.tier_2_review ? "Yes" : "No"}</span>
        <span>${role.tier_3_release_approval ? "Yes" : "No"}</span>
      </div>
    `).join("")}
  `;
}

function renderWriteState(permissions) {
  const enabled = permissions.writes_enabled && permissions.write_token_configured;
  $("writeStateBadge").className = `badge ${enabled ? "verified" : "provisional"}`;
  $("writeStateBadge").textContent = enabled ? "Write gated" : "Disabled";
  const message = enabled
    ? "Tier 1 edits require the configured token and are written only to the audit overlay."
    : "Tier 1 edits are disabled until ADMIN_WRITES_ENABLED=1 and ADMIN_WRITE_TOKEN are configured.";
  setMessage("adminWriteState", enabled ? "neutral" : "warning", message);
}

async function loadAdminPermissions() {
  try {
    const permissions = await api("/api/v1/admin/permissions");
    adminState.permissions = permissions;
    populateAdminForm(permissions);
    renderRoleMatrix(permissions);
    renderWriteState(permissions);
  } catch (error) {
    setMessage("adminWriteState", "error", error.message);
    $("roleMatrix").innerHTML = `<div class="message error">${esc(error.message)}</div>`;
  }
}

function quickEditPayload() {
  return {
    actor_name: $("actorName").value,
    actor_email: $("actorEmail").value,
    actor_role: $("actorRole").value,
    faculty_key: $("editFaculty").value,
    course_code: $("editCourseCode").value,
    field: $("editField").value,
    new_value: $("editNewValue").value,
    reason: $("editReason").value,
    owner_unit: $("editOwnerUnit").value,
    source_page_or_section: $("editSourcePage").value,
  };
}

function tokenHeader() {
  const token = $("adminToken").value.trim();
  return token ? { "X-Admin-Token": token } : {};
}

function renderAudit(edits) {
  if (!edits.length) {
    $("quickEditAudit").innerHTML = `<div class="message neutral">No quick edits have been recorded.</div>`;
    return;
  }
  $("quickEditAudit").innerHTML = edits.map(edit => `
    <div class="audit-event">
      <strong>${esc(edit.course_code)} ${esc(edit.field_label || edit.field)}</strong>
      <span>${esc(edit.faculty_key)} · ${esc(edit.applied_at)}</span>
      <p>${esc(edit.actor?.name || "Unknown editor")} changed ${esc(edit.old_value)} to ${esc(edit.new_value)}</p>
    </div>
  `).join("");
}

async function loadRecentQuickEdits() {
  try {
    const payload = await api("/api/v1/admin/quick-edits", { headers: tokenHeader() });
    renderAudit(payload.edits || []);
  } catch (error) {
    $("quickEditAudit").innerHTML = `<div class="message error">${esc(error.message)}</div>`;
  }
}

async function submitQuickEdit(event) {
  event.preventDefault();
  $("submitQuickEdit").disabled = true;
  setMessage("quickEditResult", "neutral", "Applying quick edit.");
  try {
    const payload = await api("/api/v1/admin/quick-edit", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...tokenHeader() },
      body: JSON.stringify(quickEditPayload()),
    });
    setMessage(
      "quickEditResult",
      "success",
      `Applied ${payload.change_id}. Publication effect: ${payload.publication_effect}.`
    );
    await loadRecentQuickEdits();
  } catch (error) {
    setMessage("quickEditResult", "error", error.message);
  } finally {
    const permissions = adminState.permissions;
    $("submitQuickEdit").disabled = !(permissions?.writes_enabled && permissions?.write_token_configured);
  }
}

$("quickEditForm").addEventListener("submit", submitQuickEdit);
$("loadQuickEdits").addEventListener("click", loadRecentQuickEdits);

loadGovernance();
loadAdminPermissions();
