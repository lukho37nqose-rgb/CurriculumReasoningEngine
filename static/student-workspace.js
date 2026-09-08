"use strict";

// Presentation only: the report and StudentReasoningView remain the truth owners.
const StudentWorkspace = (() => {
  const aliases = {dashboard: "overview", requirements: "curriculum", next: "explore"};
  const sectionKey = key => aliases[key] || key;
  function errorMessage(status) {
    return ({0: "The service could not be reached. Try again; no new academic conclusion was made.",
      401: "The account or session could not be confirmed. Return to the entry page and try again.",
      413: "This file is too large. Choose a smaller transcript file.",
      422: "The selected release or supplied evidence could not be used. Check your selection or input and try again.",
      429: "The service is busy. Please wait before trying again.",
      503: "Your record or reasoning service is unavailable. Try again; no new academic conclusion was made.",
      malformed: "The service returned an unusable response. Please try again."})[status] || "Reasoning is unavailable. Try again; no new conclusion was made.";
  }
  function tabs(config = {}) {
    const rows = [["overview", "Overview"], ["curriculum", "My Curriculum"], ["evidence", "My information"], ["sources", "Sources"]];
    if (config.capabilities?.course_exploration) rows.push(["explore", "Courses to explore"]);
    rows.push(["help", "Help & limits"]);
    return rows;
  }
  function navigation(config, active) {
    return tabs(config).map(([key, label]) => `<button type="button" data-view="${key}" data-report-tab="${key}" aria-current="${key === sectionKey(active) ? "page" : "false"}">${esc(label)}</button>`).join("");
  }
  function overview(report, config) {
    const view = report.student_reasoning_view || {}, counts = StudentPortal.counts(view);
    const items = asArray(view.conclusions).filter(item => !item.legacy_compatibility);
    const attention = items.filter(item => item.kind === "progression" ? item.consequence_established || ["unresolved", "conflict", "unsupported"].includes(item.outcome) : ["not_satisfied", "unresolved", "conflict", "unsupported"].includes(item.outcome));
    const priority = {conflict: 0, not_satisfied: 1, unresolved: 2, unsupported: 3};
    attention.sort((a, b) => (priority[a.outcome] ?? 1) - (priority[b.outcome] ?? 1));
    const actions = [...new Set(attention.map(item => StudentLanguage.action(item, config)).filter(Boolean))];
    return `<section class="cre-questions" aria-label="Your three questions">
      <div><h2>Where am I?</h2><strong>${counts.satisfied} requirements met</strong><p>${counts.not_satisfied} not met; ${counts.unresolved} need more information; ${counts.conflict} with conflicting information; ${counts.unsupported} not assessed.</p><p>These are requirement counts, not a percentage of your qualification.</p></div>
      <div><h2>What needs attention?</h2>${attention.slice(0, 3).map(item => `<p class="cre-alert ${esc(item.outcome)}"><strong>${esc(StudentLanguage.title(item, config))}</strong><br>${esc(StudentLanguage.meaning(item, config).label)}</p>`).join("") || "<p>No issue is established by the checks shown here.</p>"}<button data-view="curriculum">View all requirements</button></div>
      <div><h2>What can I do next?</h2>${actions.slice(0, 2).map(action => `<p>${esc(action)}</p>`).join("") || "<p>No next action is identified here.</p>"}${config.capabilities?.course_exploration ? `<button data-view="explore">Explore ${asArray(report.eligible_courses).length} courses</button>` : ""}<button data-view="evidence">Check my information</button></div>
    </section><section class="cre-position"><h2>Academic position</h2><p><strong>${esc(report.credits_completed ?? "Not supplied")}</strong> ${esc(config.credit_label || "credits counted from supplied results")}. This is not a claim that the entire record is available.</p></section>
    <section><h2>Completion and institutional boundaries</h2>${StudentPortal.sequence(view, config)}</section>`;
  }
  function exploration(report, config) {
    if (!config.capabilities?.course_exploration) return "<p>Course exploration is not available in this workspace.</p>";
    return `<section><h2>Courses to explore</h2><p>Courses CRE can currently identify as compatible with the represented curriculum conditions. These are curriculum and prerequisite conclusions, not live registration promises. Check timetable fit, places, permission and concurrent registration with your institution.</p>
      <label>Find a course<input data-course-query type="search" placeholder="Course code, name or academic unit"></label>
      <div class="cre-courses">${asArray(report.eligible_courses).map(course => `<article data-course-search="${esc(`${course.code} ${course.name} ${course.department || ""}`.toLowerCase())}"><h3>${esc(course.name || course.code)}</h3><p>${esc(course.code)}</p><p>${esc(course.reason || "Visible within the selected route.")}</p><p>${esc(course.credits)} credits${course.department ? ` · ${esc(course.department)}` : ""}</p>${asArray(course.offered).length ? `<p>${esc(course.offered.join(", "))}</p>` : ""}<details><summary>What can CRE confirm?</summary><p>${course.status === "verified" ? "The represented course information is verified." : "This course information is not fully verified."} This does not establish registration or availability.</p></details></article>`).join("") || "<p>No course option is currently established from the supplied information.</p>"}</div></section>`;
  }
  function sources(view, config) {
    const linked = StudentPortal.sources(view, false, config);
    const broader = asArray(view.source_directory).filter(source => !asArray(source.conclusion_links).length);
    return `<section><h2>Where the rules come from</h2><p>These institutional sources explain the rules. My information shows what CRE knows about you. A source link does not mean the institution has approved CRE\'s interpretation.</p>${linked}</section>${broader.length ? `<details><summary>Broader source directory</summary><p>These entries are not direct rule-level confirmation of your conclusions.</p>${broader.map(source => `<p>${esc(source.title)}</p>`).join("")}</details>` : ""}`;
  }
  function renderSection(report, config, key, context = {}) {
    const view = report.student_reasoning_view || {};
    switch (sectionKey(key)) {
      case "overview": return overview(report, config);
      case "curriculum": return `<div class="student-reasoning-view">${StudentPortal.curriculum(view, config)}</div>`;
      case "evidence": return StudentPortal.evidence(view, config, context.retrieval || [], context.registration_duration);
      case "sources": return sources(view, config);
      case "explore": return exploration(report, config);
      case "help": return StudentPortal.help(config) + (asArray(view.limitations).length ? `<section><h2>Limits of this assessment</h2>${view.limitations.map(item => `<p>${esc(item)}</p>`).join("")}</section>` : "");
      default: return "<p>This section is not available.</p>";
    }
  }
  function exportText(report, config) {
    return ["CRE reasoning output - not an official academic record", report.programme_name || "Academic workspace",
      `Based on the ${StudentLanguage.origin(config)}. Where information came from does not establish its verification status.`,
      ...asArray(report.student_reasoning_view?.conclusions).filter(item => !item.legacy_compatibility).map(item => `${StudentLanguage.title(item, config)}: ${StudentLanguage.meaning(item, config).label}. ${StudentLanguage.meaning(item, config).text}${item.status && item.status !== "verified" ? " This assessment is not fully verified." : ""}`),
      "Entry eligibility is not admission. Academic completion, graduation eligibility and formal award are separate."].join("\n");
  }
  function inspector(report) {
    return `<details class="cre-inspector"><summary>Advisor / technical detail</summary><p>Technical explanation, not institutional authorisation.</p><pre>${esc(JSON.stringify(report.advisor_reasoning_view || {}, null, 2))}</pre><details><summary>Legacy compatibility detail (not canonical assessments)</summary><pre>${esc(JSON.stringify({majors: report.majors, distinction: report.distinction, exclusion_risk: report.exclusion_risk}, null, 2))}</pre></details></details>`;
  }
  function mount(root, report, config = {}, context = {}) {
    const allowed = tabs(config).map(([key]) => key);
    const requested = new URLSearchParams(location.hash.slice(1)).get("section");
    let active = allowed.includes(sectionKey(context.section || requested)) ? sectionKey(context.section || requested) : "overview";
    root.classList.add("cre-workspace");
    root.innerHTML = `<header class="cre-account"><div><span>Your curriculum</span><h1>${esc(report.student_name || config.student_label || "Academic account")}</h1><p>${esc(report.programme_name || "Selected programme")}${report.pathway_name ? ` · ${esc(report.pathway_name)}` : ""}</p><small>Programme/workspace being evaluated, not proof of admission or current registration.</small></div><span class="cre-wordmark">CRE<br><small>Student workspace</small></span></header>
      <div class="cre-tools">${config.capabilities?.export !== false ? '<button data-copy>Copy summary</button><button data-print>Print</button>' : ""}<span role="status" data-workspace-message></span></div>
      ${context.navigation ? "" : '<nav class="cre-nav" aria-label="Workspace views"></nav>'}<div class="cre-section" tabindex="-1"></div>${context.inspector === false ? "" : inspector(report)}`;
    const nav = context.navigation || root.querySelector(".cre-nav"), body = root.querySelector(".cre-section");
    const show = (key, focus = false, historyEntry = true) => {
      key = sectionKey(key);
      if (!allowed.includes(key)) return;
      active = key;
      nav.innerHTML = navigation(config, active);
      body.innerHTML = renderSection(report, config, active, context);
      body.dataset.section = active;
      if (historyEntry) history.pushState(null, "", `#section=${active}`);
      context.onSection?.(active);
      if (focus) (context.focusTarget || body).focus();
    };
    const click = event => {
      const target = event.target.closest("button[data-conclusion-target]");
      if (target) {
        show("curriculum", false);
        const card = [...body.querySelectorAll("[data-conclusion-id]")].find(item => item.dataset.conclusionId === target.dataset.conclusionTarget);
        card?.focus();
        return;
      }
      const button = event.target.closest("button[data-view]");
      if (button) show(button.dataset.view, true);
    };
    root.onclick = click;
    if (context.navigation) nav.onclick = click;
    root.oninput = event => {
      if (!event.target.matches("[data-course-query]")) return;
      const query = event.target.value.trim().toLowerCase();
      body.querySelectorAll("[data-course-search]").forEach(card => { card.hidden = !card.dataset.courseSearch.includes(query); });
    };
    root.querySelector("[data-copy]")?.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(exportText(report, config)); root.querySelector("[data-workspace-message]").textContent = "Reasoning summary copied. Not an official academic record."; }
      catch { root.querySelector("[data-workspace-message]").textContent = "Copy is unavailable. You can use Print instead."; }
    });
    root.querySelector("[data-print]")?.addEventListener("click", () => window.print());
    if (root._creHistory) window.removeEventListener("popstate", root._creHistory);
    root._creHistory = () => show(new URLSearchParams(location.hash.slice(1)).get("section") || "overview", false, false);
    window.addEventListener("popstate", root._creHistory);
    show(active, false, false);
    return {show, destroy: () => window.removeEventListener("popstate", root._creHistory)};
  }
  return {tabs, navigation, overview, exploration, sources, renderSection, exportText, mount, errorMessage};
})();
