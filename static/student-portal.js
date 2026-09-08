"use strict";

// Shared student navigation surfaces over an existing projection, never an evaluator.
const StudentPortal = (() => {
  const kinds = {entry: "Entry requirements", progression: "Progression", completion: "Academic requirements", graduation: "Graduation eligibility", award: "Formal award"};
  const states = {satisfied: "Met", not_satisfied: "Not met yet", unresolved: "Not enough information yet", conflict: "Conflicting information", unsupported: "CRE cannot assess this question"};
  const categories = {academic_record: "Academic results", course_completion_recognition: "Course recognition decisions", requirement_recognition: "Requirement recognition decisions", external_subject_achievement: "External subject results", prior_qualification: "Prior qualifications", registration_history: "Registration history", graduation_clearance: "Graduation information", qualification_award: "Award information"};
  const canonical = view => asArray(view.conclusions).filter(item => !item.legacy_compatibility);
  const curriculum = view => canonical(view).filter(item => item.kind === "curriculum");
  const heading = (title, detail = "") => `<header class="portal-heading"><h2>${esc(title)}</h2>${detail ? `<p>${esc(detail)}</p>` : ""}</header>`;
  const owner = config => config.institution_short_name || config.institution_name || "The institution";

  function counts(view) {
    return Object.fromEntries(Object.keys(states).map(outcome => [outcome, curriculum(view).filter(item => item.outcome === outcome).length]));
  }
  function summary(view) {
    return `<dl class="portal-counts">${Object.entries(counts(view)).filter(([outcome, count]) => count || outcome === "satisfied").map(([outcome, count]) => `<div class="count-${esc(outcome)}"><dt>${esc(states[outcome])}</dt><dd>${count}</dd></div>`).join("")}</dl><p class="portal-caption">Counts of the curriculum requirements assessed here, not a percentage of your qualification.</p>`;
  }
  function sequence(view, config) {
    return `<div class="portal-sequence">${["completion", "graduation", "award"].map(kind => {
      const item = canonical(view).find(row => row.kind === kind);
      const meaning = StudentLanguage.meaning(item || {outcome: "unsupported"}, config);
      return `<section><h3>${esc(kinds[kind])}</h3><p class="state-text ${esc(item?.outcome || "unsupported")}">${esc(meaning.label)}</p><p>${esc(meaning.text)}</p></section>`;
    }).join("")}</div><p class="portal-caption">Academic completion does not establish graduation eligibility. Eligibility does not establish a formal award.</p>`;
  }
  function dashboard(view, config) {
    return StudentWorkspace.overview({student_reasoning_view: view}, config);
  }
  function renderCurriculum(view, config) {
    const all = canonical(view), seen = new Set();
    const groups = asArray(config.curriculum_groups).map(group => {
      const rows = curriculum(view).filter(item => asArray(group.identities).includes(item.identity) && !seen.has(item.identity));
      rows.forEach(item => seen.add(item.identity));
      return {title: group.title, rows};
    });
    groups.push({title: "Other curriculum requirements", rows: curriculum(view).filter(item => !seen.has(item.identity))});
    Object.entries(kinds).forEach(([kind, title]) => groups.push({title, rows: all.filter(item => item.kind === kind)}));
    return heading("Your requirements", "CRE explains how the information here relates to your curriculum. It does not replace official records or institutional decisions.") + groups.filter(group => group.rows.length).map(group => `<section class="portal-group">${heading(group.title)}${group.rows.map(item => studentConclusionCard(item, config)).join("")}</section>`).join("");
  }
  function locator(value) {
    if (!value || typeof value !== "object") return esc(value || "Location not recorded");
    const labels = {record_id: "Record", clause: "Clause", page: "Page", section: "Section"};
    return Object.entries(value).map(([key, item]) => `${esc(labels[key] || "Location")} ${esc(typeof item === "object" ? JSON.stringify(item) : item)}`).join(" · ");
  }
  function sourceCard(source, links) {
    return `<article class="portal-source"><h3>${esc(source.title)}</h3>${source.status_language ? `<p>${esc(source.status_language)}</p>` : ""}${links.map(link => `<details><summary>${esc(link.title)}</summary><p>${locator(link.locator)}</p><p>${esc(StudentLanguage.relationship(link.relationship))}</p><small>CRE links this location to the assessment. This does not mean the institution has formally confirmed CRE's interpretation.</small>${link.conclusion_id ? `<p><button type="button" data-conclusion-target="${esc(link.conclusion_id)}">View requirement</button></p>` : ""}</details>`).join("")}</article>`;
  }
  function sources(view, evidenceOnly = false, config = {}) {
    return asArray(view.source_directory).map(source => {
      const links = asArray(source.conclusion_links).filter(link => (link.relationship === "EVIDENCE_SOURCE") === evidenceOnly).map(link => {
        const item = canonical(view).find(row => row.identity === link.conclusion_id);
        return item ? {...link, title: StudentLanguage.title(item, config)} : link;
      });
      return links.length ? sourceCard(source, links) : "";
    }).join("") || "<p>No source location in this category is linked to the assessment.</p>";
  }
  function scopeText(scope, config) {
    const state = ({COVERAGE_COMPLETE_FOR_SCOPE: "Complete information was supplied for the specific items below.", COVERAGE_PARTIAL: "Only some information was supplied for these items.", COVERAGE_UNKNOWN: "CRE does not know whether the supplied information is complete for this question."})[scope.coverage_state] || "Completeness is not established for this question.";
    const codes = asArray(scope.course_codes).map(code => StudentLanguage.course(code, config));
    const requirements = asArray(scope.requirement_ids).map(id => config.requirement_titles?.[`curriculum:${id}`] || "A named requirement");
    const named = [...codes, ...requirements];
    return `<p>${esc(state)}</p>${named.length ? `<ul>${named.map(name => `<li>${esc(name)}</li>`).join("")}</ul>` : "<p>This statement applies only to the named records supplied for this assessment, not to the entire academic record.</p>"}`;
  }
  function evidence(view, config, retrieval = [], duration = null) {
    const receipt = view.evidence_receipt || {}, institution = owner(config);
    const unavailable = retrieval.filter(item => item.state === "UNAVAILABLE_OR_MALFORMED");
    const durationUnit = {active_academic_cycles: "active academic cycles", registered_periods: "registered periods"}[duration?.basis] || "units of the specified duration measure";
    return heading("Information available to CRE", `${StudentLanguage.receiptIntro(config)} CRE does not own your academic record.`) +
      "<p>Where information came from does not establish its verification status. Not every item is used for every answer.</p>" +
      (unavailable.length ? `<aside class="portal-service-notice"><strong>Some information could not be retrieved or used.</strong><p>Try retrieving again or ask ${esc(institution)} for help. A service problem is not an academic failure.</p></aside>` : "") +
      `<div class="portal-evidence-list">${asArray(receipt.entries).map(entry => `<section><h3>${esc(categories[entry.category] || "Other supplied information")}</h3><p><strong>${entry.supplied ? "Received" : "Not supplied"}</strong></p><details><summary>What does this tell CRE?</summary>${asArray(entry.coverage_scopes).length ? entry.coverage_scopes.map(scope => scopeText(scope, config)).join("") : "<p>CRE does not know whether the supplied information is complete for this question.</p>"}</details></section>`).join("")}</div>` +
      (asArray(receipt.achievement_observations).length ? `<details class="portal-group"><summary>Achievement values supplied</summary><p>${esc(config.achievement_label || "Values as supplied, with no conversion.")}</p><ul>${receipt.achievement_observations.map(item => `<li>${esc(StudentLanguage.course(item.course_code, config))}: <strong>${esc(item.value)}</strong></li>`).join("")}</ul><p>These values were supplied; this does not mean every assessment used them.</p></details>` : "") +
      (duration ? `<details class="portal-group"><summary>What your registration history shows</summary><p>${duration.outcome === "known" ? `${esc(duration.value)} ${esc(durationUnit)} are established by the supplied history.` : "The supplied history does not establish an exact duration."}</p><p>This is historical information, not a current enrolment decision.</p></details>` : "") +
      heading("Where this information came from", "These references describe information about you, not the rules you must meet.") + sources(view, true, config);
  }
  function help(config) {
    const institution = owner(config);
    return heading("How this helps you") + `<div class="portal-help"><section><h3>What does CRE do?</h3><p>It explains how the information available here relates to your curriculum.</p></section>
      <section><h3>What does CRE not do?</h3><p>It does not replace ${esc(institution)}'s records or decisions. Entry eligibility is not admission. Past registration is not proof of current enrolment. Graduation eligibility is not a formal award.</p></section>
      <section><h3>Why might it be unable to decide?</h3><p>There may be too little information, conflicting information, or a matter that ${esc(institution)} needs to decide. Missing information is not the same as a failed requirement.</p></section>
      <section><h3>Where do the rules come from?</h3><p>Sources shows the institutional locations linked to the represented rules. My information describes the ${esc(StudentLanguage.origin(config))}. The two answer different questions.</p></section>
      ${["demo_record", "synthetic"].includes(config.evidence_origin) ? '<section><h3>About this demonstration</h3><p>These accounts contain no real student data. This is not production authentication or a security guarantee.</p></section>' : ""}</div>`;
  }
  return {counts, summary, sequence, dashboard, curriculum: renderCurriculum, evidence, sources, sourceCard, locator, help};
})();
