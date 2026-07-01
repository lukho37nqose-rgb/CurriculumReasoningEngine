"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character]));

async function api(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
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

loadGovernance();
