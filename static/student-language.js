"use strict";

// Copy and disclosure only. Outcomes and witnesses come from StudentReasoningView.
const StudentLanguage = (() => {
  const labels = {satisfied: "Met", not_satisfied: "Not met yet", unresolved: "Not enough information yet", conflict: "Conflicting information", unsupported: "CRE cannot assess this question", awarded: "Award evidence supplied", not_awarded: "No award recorded"};
  const titles = {entry: "Entry requirements", completion: "Academic requirements", graduation: "Graduation eligibility", award: "Formal award"};
  const institution = config => config.institution_short_name || config.institution_name || "The institution";
  function origin(config = {}) {
    const owner = institution(config);
    if (config.evidence_origin === "institution_supplied") return `information ${owner} supplied for this session`;
    if (config.evidence_origin === "demo_record") return `demonstration information ${owner} supplied for this session`;
    if (["user_supplied", "manual_entry"].includes(config.evidence_origin)) return "information you supplied for this session";
    if (config.evidence_origin === "synthetic") return "demonstration information supplied for this session";
    return "information supplied for this session";
  }
  const course = (code, config) => config.course_titles?.[code] ? `${code} - ${config.course_titles[code]}` : code;
  function receiptIntro(config = {}) {
    const owner = institution(config);
    return ({manual_entry: "You supplied this information for the current assessment.", user_supplied: "This information came from the file you provided.", demo_record: `${owner} supplied this demonstration record for the current session.`, institution_supplied: `${owner} supplied this information for the current session.`, synthetic: "This is demonstration information for the current session."})[config.evidence_origin] || "This information is available for the current assessment.";
  }
  const title = (item, config) => config.requirement_titles?.[item.identity] || titles[item.kind] || item.title;
  function action(item, config) {
    return actionDetail(item, config).needs || "";
  }
  function actionDetail(item, config = {}) {
    const owner = institution(config);
    return ({
      SUPPLY_EVIDENCE: {needs: "More information is needed to answer this question.", can: "Check the information available here against your records.", ask: "What information is missing for this requirement, and how can I provide it?"},
      REVIEW_RECOGNITION: {needs: "A recognition decision needs review.", can: `Ask ${owner} to check whether previous study counts toward this requirement.`, ask: "Has my previous study been formally recognised toward this requirement?"},
      REVIEW_CONFLICT: {needs: `${owner} needs to clarify the conflicting information.`, can: "Ask which information should apply to this requirement.", ask: "These records point to different answers. Which should apply?"},
      SEEK_INSTITUTIONAL_DECISION: {needs: `${owner} still needs to decide this.`, can: `Ask ${owner} about the decision needed for this question.`, ask: "What decision is still needed, and has it been recorded?"},
      POLICY_NOT_SUPPORTED: {needs: "CRE cannot assess this rule yet.", can: `Check the rule with ${owner}.`, ask: "How does this rule apply to my situation?"},
      UNRESOLVED_NEXT_STEP: {needs: "This needs clarification before CRE can give a reliable answer."}
    })[item.next_action] || {};
  }
  function meaning(item, config = {}) {
    const owner = institution(config), outcome = item.outcome;
    let label = labels[outcome] || labels.unsupported;
    let text = ({satisfied: "You meet this requirement.", not_satisfied: "You do not meet this requirement yet. CRE has enough information to establish this shortfall.", unresolved: "CRE does not have enough information to decide this yet.", conflict: "Two pieces of information point to different conclusions, so CRE will not choose one automatically.", unsupported: "This type of question is not supported by CRE here.", awarded: "The information available includes evidence of a formal qualification award. CRE did not confer it.", not_awarded: "The information available includes an explicit decision that the qualification was not awarded."})[outcome] || "CRE cannot assess this requirement.";
    let boundary = "";
    if (item.kind === "entry") {
      boundary = "This is not an admission decision or applicant acceptance.";
      if (outcome === "satisfied") text = "You meet the represented entry requirements.";
      if (outcome === "unresolved") text = "CRE cannot yet tell whether you meet the represented entry requirements.";
    }
    if (item.kind === "completion") {
      boundary = "Academic completion alone does not establish graduation eligibility.";
      if (outcome === "satisfied") text = "Your academic requirements assessed here are complete.";
      if (outcome === "not_satisfied") text = "Your academic requirements assessed here are not yet complete.";
      if (outcome === "unresolved") text = "CRE does not have enough information to decide whether your academic requirements are complete.";
    }
    if (item.kind === "graduation") {
      boundary = "Graduation eligibility is not formal approval or a qualification award.";
      if (outcome === "satisfied") text = `${owner}'s represented graduation conditions are met.`;
      if (outcome === "unresolved") text = "CRE cannot yet tell whether all required graduation conditions are met.";
    }
    if (item.kind === "award" && outcome === "unresolved") text = "There is not enough information here to establish a formal award. This does not mean no award exists.";
    if (item.kind === "progression") {
      boundary = "This does not record exclusion or another formal institutional decision.";
      if (item.consequence_established) {
        label = item.consequence_type === "review_required" ? `${owner} needs to review this` : "Needs attention";
        text = ({progression_ineligible: "You do not currently meet this progression requirement.", review_required: `This policy requires ${owner} to review your case.`, advisory_risk: "Your record has triggered an academic-risk indicator."})[item.consequence_type] || item.explanation;
      } else if (["satisfied", "not_satisfied"].includes(outcome)) {
        label = outcome === "not_satisfied" ? "No issue identified by this rule" : "Consequence not established";
        text = "This rule has not established a progression restriction, required review or academic-risk indicator.";
      }
    }
    return {label, text, boundary};
  }
  function why(item, config) {
    const detail = String(item.detail || ""), parts = [];
    // Translate only explicit existing explanation templates; never derive an outcome.
    if (/completion recogni[sz]ed/.test(detail) && item.outcome === "satisfied") parts.push("The information available includes an institutional recognition decision that counts toward this requirement. Recognition is not a new course attempt or mark.");
    if (/recognition/i.test(detail) && item.outcome === "conflict") parts.push("The recognition information does not agree and needs clarification.");
    if (/recognition/i.test(detail) && item.outcome === "unresolved") parts.push("Recognition information may affect this result, but the relevant decision is not established here yet.");
    if (item.kind === "entry") {
      parts.push("Only confirmed information supporting the entry assessment is shown here.");
      asArray(item.supporting_details).forEach(fact => {
        if (fact.includes("qualifying achievement witness")) parts.push("Your supplied course achievement meets the represented achievement requirement.");
        if (fact.startsWith("External ") && fact.includes("satisfies the threshold")) parts.push("A supplied external subject result meets the represented achievement requirement.");
        if (fact.startsWith("Prior qualification ") && fact.includes("evidenced as attained")) parts.push("The supplied information establishes a qualifying prior qualification. This is an exact qualification match, not equivalence.");
      });
    }
    if (item.kind === "curriculum" && !parts.length && !/[=:]|coverage|status|authority|recognition|choose_n/i.test(detail)) parts.push(detail);
    const codes = asArray(item.used_course_codes);
    if (codes.length) parts.push(`Information supporting this result relates to: ${codes.map(code => course(code, config)).join("; ")}. A recognition decision is not a course attempt.`);
    if (item.outcome === "unresolved") parts.push("Not confirmed does not mean not completed. More information may change what CRE can establish.");
    if (!parts.filter(Boolean).length) parts.push(`This answer uses the ${origin(config)}. A more specific explanation is not available here; the advisor inspector retains the technical detail.`);
    const clearances = asArray(item.clearance_assessments).map((child, index) => `<p>Required institutional clearance ${index + 1}: ${esc(labels[child.outcome] || labels.unsupported)}.</p>`).join("");
    return [...new Set(parts)].map(text => `<p>${esc(text)}</p>`).join("") + clearances;
  }
  function relationship(type) {
    return ({DIRECT_RULE_SOURCE: "Direct rule source", INHERITED_POLICY_SOURCE: "Inherited policy source, not a separate rule-level citation", PACKAGE_SOURCE: "Package-level source, not direct confirmation of this rule", EVIDENCE_SOURCE: "Reference for supplied student information, not an institutional rule"})[type] || "Source relationship not specified";
  }
  function source(ref) {
    const locator = typeof ref.locator === "object" && ref.locator ? Object.entries(ref.locator).map(([key, value]) => `${({record_id: "Record", clause: "Clause", page: "Page", section: "Section"})[key] || "Location"} ${value}`).join(" · ") : ref.locator;
    const description = relationship(ref.relationship);
    return `<p><strong>${esc(ref.title)}</strong></p><p>${esc(locator || "Location not recorded")}</p><small>${esc(description)} This does not mean the institution has formally confirmed CRE's interpretation.</small>`;
  }
  function card(item, config = {}) {
    const copy = meaning(item, config), next = actionDetail(item, config);
    const instruction = config.requirement_instructions?.[item.identity];
    const appearance = item.kind === "progression" && ["satisfied", "not_satisfied"].includes(item.outcome) ? (item.consequence_established ? "policy_triggered" : "policy_clear") : item.outcome;
    const evidenceRefs = asArray(item.source_references).filter(ref => ref.relationship === "EVIDENCE_SOURCE");
    const ruleRefs = asArray(item.source_references).filter(ref => ref.relationship !== "EVIDENCE_SOURCE");
    const qualified = ["satisfied", "not_satisfied", "awarded", "not_awarded"].includes(item.outcome) && item.status && item.status !== "verified";
    return `<article class="notice-row ${esc(appearance)} human-card" tabindex="-1" data-conclusion-id="${esc(item.identity)}"><header><strong>${esc(title(item, config))}</strong><span class="badge ${esc(appearance)}">${esc(copy.label)}</span></header>
      <p class="human-meaning">${esc(copy.text)}</p>${copy.boundary ? `<p class="human-boundary">${esc(copy.boundary)}</p>` : ""}
      ${qualified ? "<small>CRE's interpretation has not yet been institutionally confirmed.</small>" : ""}
      ${next.needs ? `<div class="next-action"><strong>${esc(next.needs)}</strong>${next.can ? `<p><strong>What you can do</strong><br>${esc(next.can)}</p>` : ""}${next.ask ? `<details><summary>What to ask</summary><p>${esc(next.ask)}</p></details>` : ""}</div>` : ""}
      <details class="human-why"><summary>Why?</summary>${why(item, config)}${evidenceRefs.map(ref => `<section><h4>Where this information came from</h4>${source(ref)}</section>`).join("")}</details>
      ${item.kind === "award" ? "" : `<details class="human-rule"><summary>What the rule requires</summary><p>${esc(instruction || "A plain-language rule description is not available here. Check the linked source; CRE has not reconstructed the rule from its title.")}</p></details><details class="human-source"><summary>Where this comes from</summary>${ruleRefs.map(source).join("") || "<p>A rule source is not currently linked to this assessment.</p>"}<button type="button" data-view="sources">Open source directory</button></details>`}</article>`;
  }
  return {labels, title, meaning, action, actionDetail, course, source, card, origin, receiptIntro, relationship};
})();
