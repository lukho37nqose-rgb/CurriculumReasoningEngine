"use strict";

// Copy and disclosure only. Outcomes and witnesses come from StudentReasoningView.
const StudentLanguage = (() => {
  const labels = {satisfied: "Met", not_satisfied: "Needs attention", unresolved: "Not enough information yet", conflict: "Conflicting information", unsupported: "Not assessed by CRE", awarded: "Award evidence supplied", not_awarded: "No award recorded"};
  const titles = {entry: "Entry requirements", completion: "Academic requirements", graduation: "Graduation eligibility", award: "Formal award"};
  const institution = config => config.institution_short_name || config.institution_name || "The institution";
  const course = (code, config) => config.course_titles?.[code] ? `${code} - ${config.course_titles[code]}` : code;
  const title = (item, config) => config.requirement_titles?.[item.identity] || titles[item.kind] || item.title;
  function action(item, config) {
    const owner = institution(config);
    return ({SUPPLY_EVIDENCE: "Provide more information", REVIEW_RECOGNITION: "Recognition needs review", REVIEW_CONFLICT: `Ask ${owner} to clarify this information`, SEEK_INSTITUTIONAL_DECISION: `Ask ${owner} about the institutional decision`, POLICY_NOT_SUPPORTED: "CRE cannot assess this rule", UNRESOLVED_NEXT_STEP: `Ask ${owner} what information is needed`})[item.next_action] || "";
  }
  function meaning(item, config = {}) {
    const owner = institution(config), outcome = item.outcome;
    let label = labels[outcome] || labels.unsupported;
    let text = ({satisfied: "Based on the represented rules, you meet this requirement.", not_satisfied: "This requirement is not currently met. CRE has enough information to determine this.", unresolved: `CRE cannot determine this requirement from the information ${owner} supplied for this session.`, conflict: `${owner} supplied information that points to different conclusions, so CRE will not choose one automatically.`, unsupported: "CRE cannot assess this requirement with its current capabilities.", awarded: `${owner} supplied evidence of a formal qualification award. CRE did not confer it.`, not_awarded: `${owner} supplied a decision recording that the qualification was not awarded.`})[outcome] || "CRE cannot assess this requirement.";
    let boundary = "";
    if (item.kind === "entry") {
      boundary = "This is not an admission decision or applicant acceptance.";
      if (outcome === "satisfied") text = "The represented entry requirements are met.";
    }
    if (item.kind === "completion") {
      boundary = "Academic completion alone does not establish graduation eligibility.";
      if (outcome === "satisfied") text = "Your represented academic requirements are complete.";
    }
    if (item.kind === "graduation") {
      boundary = "Graduation eligibility is not formal approval or a qualification award.";
      if (outcome === "satisfied") text = `${owner}'s represented graduation conditions are met.`;
      if (outcome === "unresolved") text = `${owner}'s represented graduation conditions are not yet established.`;
    }
    if (item.kind === "award" && outcome === "unresolved") text = "A formal award has not been established from the information supplied. This does not mean no award exists.";
    if (item.kind === "progression") {
      boundary = "This does not record exclusion or another formal institutional decision.";
      if (item.consequence_established) {
        label = item.consequence_type === "review_required" ? "Institutional action required" : "Needs attention";
        text = ({progression_ineligible: "You do not currently meet this represented progression requirement.", review_required: "The represented policy requires institutional review.", advisory_risk: "Your record has triggered an academic-risk indicator."})[item.consequence_type] || item.explanation;
      } else if (["satisfied", "not_satisfied"].includes(outcome)) {
        label = outcome === "not_satisfied" ? "No issue identified by this rule" : "Consequence not established";
        text = "This rule has not established a progression restriction, required review or academic-risk indicator.";
      }
    }
    return {label, text, boundary};
  }
  function why(item, config) {
    const owner = institution(config), detail = String(item.detail || ""), parts = [];
    const instruction = config.requirement_instructions?.[item.identity];
    if (instruction) parts.push(instruction);
    // Translate only explicit existing explanation templates; never derive an outcome.
    if (/completion recogni[sz]ed/.test(detail) && item.outcome === "satisfied") parts.push(`${owner} supplied a recognition decision that counts toward this requirement. Recognition is not a new course attempt or mark.`);
    if (/recognition/i.test(detail) && item.outcome === "conflict") parts.push(`${owner} supplied recognition information that conflicts and needs review.`);
    if (/recognition/i.test(detail) && item.outcome === "unresolved") parts.push("Recognition information may affect this result; the relevant decision is not yet established from the information supplied.");
    if (item.kind === "entry") {
      parts.push("Only confirmed information supporting the entry assessment is shown here.");
      asArray(item.supporting_details).forEach(fact => {
        if (fact.includes("qualifying achievement witness")) parts.push("Your supplied course achievement meets the represented achievement requirement.");
        if (fact.startsWith("External ") && fact.includes("satisfies the threshold")) parts.push("A supplied external subject result meets the represented achievement requirement.");
        if (fact.startsWith("Prior qualification ") && fact.includes("evidenced as attained")) parts.push(`${owner} has a qualifying prior qualification on record. This is an exact qualification match, not equivalence.`);
      });
    }
    if (!instruction && item.kind === "curriculum" && !parts.length && !/[=:]|coverage|status|authority|recognition|choose_n/i.test(detail)) parts.push(detail);
    const codes = asArray(item.used_course_codes);
    if (codes.length) parts.push(`${item.kind === "entry" ? "Supporting identifiers" : "Confirmed completion (including recognised completion where supplied)"}: ${codes.map(code => course(code, config)).join("; ")}.`);
    if (item.outcome === "unresolved") parts.push("Not confirmed does not mean not completed. More information may change what CRE can establish.");
    if (!parts.length) parts.push("The assessment uses the supplied information and the represented rule. More technical detail is available in the advisor inspector.");
    const clearances = asArray(item.clearance_assessments).map((child, index) => `<p>Required institutional clearance ${index + 1}: ${esc(labels[child.outcome] || labels.unsupported)}.</p>`).join("");
    return [...new Set(parts)].map(text => `<p>${esc(text)}</p>`).join("") + clearances;
  }
  function source(ref) {
    const locator = typeof ref.locator === "object" && ref.locator ? Object.entries(ref.locator).map(([key, value]) => `${({record_id: "Record", clause: "Clause", page: "Page", section: "Section"})[key] || "Location"} ${value}`).join(" · ") : ref.locator;
    const description = ref.relationship === "EVIDENCE_SOURCE" ? "This is a reference for supplied information, not a rule or a decision made by CRE." : "CRE has this source location linked to the represented rule.";
    return `<p><strong>${esc(ref.title)}</strong></p><p>${esc(locator || "Location not recorded")}</p><small>${esc(description)} This does not mean the institution has formally confirmed CRE's interpretation.</small>`;
  }
  function card(item, config = {}) {
    const copy = meaning(item, config), next = action(item, config);
    const appearance = item.kind === "progression" && ["satisfied", "not_satisfied"].includes(item.outcome) ? (item.consequence_established ? "policy_triggered" : "policy_clear") : item.outcome;
    const evidenceRefs = asArray(item.source_references).filter(ref => ref.relationship === "EVIDENCE_SOURCE");
    const ruleRefs = asArray(item.source_references).filter(ref => ref.relationship !== "EVIDENCE_SOURCE");
    const qualified = ["satisfied", "not_satisfied", "awarded", "not_awarded"].includes(item.outcome) && item.status && item.status !== "verified";
    return `<article class="notice-row ${esc(appearance)} human-card"><header><strong>${esc(title(item, config))}</strong><span class="badge ${esc(appearance)}">${esc(copy.label)}</span></header>
      <p class="human-meaning">${esc(copy.text)}</p>${copy.boundary ? `<p class="human-boundary">${esc(copy.boundary)}</p>` : ""}
      ${qualified ? "<small>CRE's interpretation has not yet been institutionally confirmed.</small>" : ""}
      ${next ? `<p class="next-action"><strong>${esc(next)}</strong>${["REVIEW_CONFLICT", "REVIEW_RECOGNITION", "SEEK_INSTITUTIONAL_DECISION"].includes(item.next_action) ? `<br>CRE cannot resolve this itself; ${esc(institution(config))} needs to review or decide it.` : ""}</p>` : ""}
      <details class="human-why"><summary>Why?</summary>${why(item, config)}${evidenceRefs.map(ref => `<section><h4>Where this information came from</h4>${source(ref)}</section>`).join("")}</details>
      ${item.kind === "award" ? "" : `<details class="human-source"><summary>Where is the rule?</summary>${ruleRefs.map(source).join("") || "<p>A rule source is not currently linked to this assessment.</p>"}</details>`}</article>`;
  }
  return {labels, title, meaning, action, course, source, card};
})();
