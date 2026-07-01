"use strict";

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const FACULTY_CODES = {
  uct_humanities: "HUM",
  uct_commerce: "COM",
  uct_ebe: "EBE",
  uct_law: "LAW",
  uct_science: "SCI",
  uct_health: "FHS",
};

const state = {
  bootstrap: null,
  faculty: null,
  context: null,
  programme: null,
  pathway: null,
  programmeDetails: null,
  courses: {},
  selectedFile: null,
  report: null,
  reportTab: "overview",
  currentStep: "route",
  serviceReady: false,
};

const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[character]));
const titleCase = value => String(value || "")
  .replaceAll("_", " ")
  .replace(/\b\w/g, character => character.toUpperCase());
const asArray = value => Array.isArray(value) ? value : [];

function announce(message) {
  const region = $("liveRegion");
  region.textContent = "";
  window.setTimeout(() => { region.textContent = message; }, 20);
}

function detailMessage(detail) {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(item => item?.msg || item?.detail || "").filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  return "The request could not be completed.";
}

async function api(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  let response;
  try {
    response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  } catch (error) {
    const origin = window.location.origin;
    throw new Error(
      `CurriculumAdvisor could not reach its server at ${origin}. `
      + "Reload the deployed site, or restart the local FastAPI server if you are working on your computer."
    );
  }
  let payload = {};
  if (response.status !== 204) {
    try { payload = await response.json(); }
    catch { payload = { detail: "The server returned an unexpected response." }; }
  }
  if (!response.ok) {
    const error = new Error(detailMessage(payload.detail));
    error.status = response.status;
    error.retryAfter = response.headers.get("Retry-After");
    throw error;
  }
  return payload;
}

function setStatus(kind, label) {
  const button = $("statusButton");
  button.classList.remove("ready", "failed");
  if (kind) button.classList.add(kind);
  $("statusLabel").textContent = label;
}

async function checkReadiness({ openDialog = false } = {}) {
  setStatus("", "Checking service");
  if (openDialog) {
    $("statusDialogHeading").textContent = "Checking readiness";
    $("statusDialogBody").innerHTML = '<span class="spinner" aria-hidden="true"></span>';
    $("statusDialog").showModal();
  }
  try {
    const readiness = await api("/api/v1/system/ready");
    state.serviceReady = readiness.status === "ready";
    setStatus(state.serviceReady ? "ready" : "failed", state.serviceReady ? "Service ready" : "Needs attention");
    const faculties = Object.entries(readiness.faculties || {}).map(([key, row]) => `
      <div class="status-faculty">
        <span>${esc(state.bootstrap?.faculties?.find(item => item.key === key)?.name || titleCase(key))}</span>
        <strong>${esc(row.programmes)} routes · ${esc(row.courses)} courses</strong>
      </div>
    `).join("");
    $("statusDialogHeading").textContent = state.serviceReady ? "The reasoning service is ready" : "Some catalogues could not load";
    $("statusDialogBody").innerHTML = `
      <div class="message ${state.serviceReady ? "success" : "error"}">
        ${state.serviceReady
          ? "All enabled faculty catalogues loaded successfully."
          : `Failures: ${esc(Object.keys(readiness.failures || {}).join(", ") || "unknown")}`}
      </div>
      ${faculties}
    `;
  } catch (error) {
    state.serviceReady = false;
    setStatus("failed", "Server unavailable");
    $("statusDialogHeading").textContent = "The service could not be reached";
    $("statusDialogBody").innerHTML = `<div class="message error">${esc(error.message)}</div>`;
  }
}

function renderDecisionLenses() {
  const lenses = state.bootstrap?.decision_lenses;
  if (!lenses?.length) return;
  $("decisionLensList").innerHTML = lenses.map((lens, index) => `
    <li><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${esc(lens.title)}</strong><p>${esc(lens.description)}</p></div></li>
  `).join("");
}

function renderTrustBoundaries() {
  const boundaries = state.bootstrap?.trust_boundaries || [];
  $("trustBoundaryList").innerHTML = boundaries.map(item => `<div><span aria-hidden="true">→</span><span>${esc(item)}</span></div>`).join("");
}

function renderFaculties() {
  const faculties = state.bootstrap?.faculties || [];
  $("facultyGrid").innerHTML = faculties.map((faculty, index) => `
    <button class="faculty-card" type="button" data-faculty="${esc(faculty.key)}">
      <span class="faculty-index">${String(index + 1).padStart(2, "0")}</span>
      <div>
        <h3>${esc(faculty.name)}</h3>
        <p>${esc(faculty.description)}</p>
        <div class="faculty-meta"><span class="mini-badge">2026 catalogue</span><span class="mini-badge">Available</span></div>
      </div>
    </button>
  `).join("");
  document.querySelectorAll("[data-faculty]").forEach(button => {
    button.addEventListener("click", () => openFaculty(button.dataset.faculty));
  });
}

async function boot() {
  try {
    state.bootstrap = await api("/api/v1/bootstrap");
    renderDecisionLenses();
    renderTrustBoundaries();
    renderFaculties();
  } catch (error) {
    $("facultyGrid").innerHTML = `<div class="message error">${esc(error.message)}</div>`;
  }
  checkReadiness();
  const facultyFromPath = location.pathname.startsWith("/faculty/")
    ? decodeURIComponent(location.pathname.split("/").filter(Boolean).pop())
    : null;
  if (facultyFromPath) openFaculty(facultyFromPath, { historyMode: "replace" });
}

function resetRouteState() {
  state.programme = null;
  state.pathway = null;
  state.programmeDetails = null;
  state.courses = {};
  state.selectedFile = null;
  state.report = null;
  state.reportTab = "overview";
  $("programmeSelect").value = "";
  $("pathwaySelect").innerHTML = '<option value="">Choose the applicable pathway</option>';
  $("pathwayField").classList.add("hidden");
  for (const id of ["majorOne", "majorTwo", "majorThree"]) {
    $(id).innerHTML = id === "majorThree"
      ? '<option value="">No additional major</option>'
      : '<option value="">Choose a major</option>';
  }
  $("yearsRegistered").value = "";
  $("transcriptFile").value = "";
  $("selectedFile").textContent = "No file selected";
  $("analyseButton").disabled = true;
  $("routeContinue").disabled = true;
  $("programmePreview").className = "programme-preview empty-state";
  $("programmePreview").innerHTML = '<div class="empty-symbol" aria-hidden="true">↳</div><div><strong>Your programme defines the reasoning boundary.</strong><p>Select it to see duration, credit expectations, majors and source status.</p></div>';
}

async function openFaculty(key, { historyMode = "push" } = {}) {
  const meta = state.bootstrap?.faculties?.find(item => item.key === key);
  if (!meta) return;
  state.faculty = key;
  state.context = null;
  resetRouteState();
  setStep("route");
  $("landingView").classList.add("hidden");
  $("workspaceView").classList.remove("hidden");
  $("setupPanel").classList.remove("hidden");
  $("reportPanel").classList.add("hidden");
  $("railFacultyName").textContent = meta.short_name || meta.name;
  $("railFacultyCode").textContent = FACULTY_CODES[key] || meta.name.slice(0, 3).toUpperCase();
  $("programmeSelect").innerHTML = '<option value="">Loading programmes…</option>';
  if (historyMode === "push") history.pushState({ faculty: key }, "", `/faculty/${encodeURIComponent(key)}`);
  else history.replaceState({ faculty: key }, "", `/faculty/${encodeURIComponent(key)}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  announce(`Loading ${meta.name} routes.`);
  try {
    state.context = await api(`/api/v1/faculties/${encodeURIComponent(key)}`);
    populateProgrammes();
    announce(`${meta.name} routes loaded.`);
  } catch (error) {
    $("setupError").textContent = error.message;
    $("setupError").classList.remove("hidden");
    $("programmeSelect").innerHTML = '<option value="">Programmes unavailable</option>';
  }
}

function programmeGroup(programme) {
  if (state.faculty === "uct_ebe") {
    if (programme.name.includes("Engineering")) return "Engineering";
    if (programme.name.includes("Architecture")) return "Architecture";
    return "Built environment";
  }
  if (state.faculty === "uct_commerce") {
    if (programme.name.includes("Business Science")) return "Business Science";
    if (programme.name.includes("Advanced Diploma")) return "Advanced diplomas";
    return "Commerce";
  }
  if (state.faculty === "uct_humanities") {
    return programme.programme_type === "general_degree" ? "General degrees" : "Structured qualifications";
  }
  return "Programmes";
}

function populateProgrammes() {
  const programmes = state.context?.programmes || [];
  const grouped = new Map();
  for (const programme of programmes) {
    const group = programmeGroup(programme);
    if (!grouped.has(group)) grouped.set(group, []);
    grouped.get(group).push(programme);
  }
  $("programmeSelect").innerHTML = '<option value="">Choose your programme</option>'
    + [...grouped.entries()].map(([label, rows]) => `
      <optgroup label="${esc(label)}">
        ${rows.map(programme => `<option value="${esc(programme.key)}">${esc(programme.name)}</option>`).join("")}
      </optgroup>
    `).join("");
}

function selectedPathway() {
  if (!state.programme) return null;
  const key = $("pathwaySelect").value || state.programme.default_pathway_key || "";
  return asArray(state.programme.pathways).find(pathway => pathway.key === key) || null;
}

function selectedMajors() {
  const keys = [$("majorOne").value, $("majorTwo").value, $("majorThree").value].filter(Boolean);
  return [...new Set(keys)];
}

function renderProgrammePreview() {
  const programme = state.programme;
  if (!programme) return;
  const pathway = selectedPathway();
  const sourcePage = programme.source?.page || programme.source?.pages || programme.source?.section || "Recorded source";
  const notes = [
    ["Admission", asArray(programme.admission_notes)[0] || "No additional admission note represented."],
    ["Progression", asArray(programme.progression_notes)[0] || "Progression is assessed from represented programme rules."],
    ["Award", asArray(programme.award_notes)[0] || "Award status remains subject to complete and verified evidence."],
  ];
  $("programmePreview").className = "programme-preview";
  $("programmePreview").innerHTML = `
    <div class="programme-card-head">
      <div><h3>${esc(programme.name)}</h3><p>${pathway ? esc(pathway.name) : esc(programme.degree_category || titleCase(programme.route_type))} · source ${esc(sourcePage)}</p></div>
      <span class="badge ${esc(programme.scope_status)}">${esc(programme.scope_status)}</span>
    </div>
    <div class="programme-metrics">
      <div><strong>${esc(programme.minimum_nqf_credits || "—")}</strong><span>minimum NQF credits</span></div>
      <div><strong>${esc(programme.minimum_duration_years || "—")}</strong><span>minimum years</span></div>
      <div><strong>${esc(programme.required_majors || 0)}</strong><span>required majors</span></div>
      <div><strong>${esc(programme.course_count || 0)}</strong><span>courses in route scope</span></div>
    </div>
    <div class="programme-notes">
      ${notes.map(([label, text]) => `<article><strong>${label}</strong><p>${esc(text)}</p></article>`).join("")}
    </div>
  `;
  $("routeSummaryButton").classList.remove("hidden");
}

function routeIsReady() {
  if (!state.programme) return false;
  if (state.programme.pathway_required && !selectedPathway()) return false;
  return true;
}

function onProgrammeChange() {
  const key = $("programmeSelect").value;
  state.programme = state.context?.programmes?.find(programme => programme.key === key) || null;
  state.pathway = null;
  state.programmeDetails = null;
  state.courses = {};
  if (!state.programme) {
    $("pathwayField").classList.add("hidden");
    $("routeContinue").disabled = true;
    return;
  }
  const pathways = asArray(state.programme.pathways);
  $("pathwaySelect").innerHTML = '<option value="">Choose the applicable pathway</option>'
    + pathways.map(pathway => `<option value="${esc(pathway.key)}">${esc(pathway.name)}</option>`).join("");
  if (state.programme.pathway_required || pathways.length > 1) {
    $("pathwayField").classList.remove("hidden");
    if (state.programme.default_pathway_key) $("pathwaySelect").value = state.programme.default_pathway_key;
  } else {
    $("pathwayField").classList.add("hidden");
    if (pathways.length === 1) $("pathwaySelect").value = pathways[0].key;
  }
  state.pathway = selectedPathway();
  renderProgrammePreview();
  configureMajors();
  $("routeContinue").disabled = !routeIsReady();
}

function onPathwayChange() {
  state.pathway = selectedPathway();
  renderProgrammePreview();
  configureMajors();
  $("routeContinue").disabled = !routeIsReady();
}

function configureMajors() {
  const majors = asArray(state.programme?.majors);
  const required = Number(state.programme?.required_majors || 0);
  const options = '<option value="">Choose a major</option>'
    + majors.map(major => `<option value="${esc(major.key)}">${esc(major.name)}</option>`).join("");
  for (const id of ["majorOne", "majorTwo"]) $(id).innerHTML = options;
  $("majorThree").innerHTML = '<option value="">No additional major</option>'
    + majors.map(major => `<option value="${esc(major.key)}">${esc(major.name)}</option>`).join("");
  $("majorOneField").classList.toggle("hidden", required < 1 || !majors.length);
  $("majorTwoField").classList.toggle("hidden", required < 2 || !majors.length);
  $("majorThreeField").classList.toggle("hidden", !majors.length);
  $("intentNotice").textContent = majors.length
    ? `${required || "No fixed number of"} major${required === 1 ? "" : "s"} represented for this route. Major choices affect requirement and course reasoning.`
    : "This is a structured route. The selected programme or pathway supplies the curriculum; no general-degree major selection is required.";
}

async function loadRouteData() {
  const pathway = selectedPathway();
  const params = new URLSearchParams({ faculty_key: state.faculty, programme_key: state.programme.key });
  if (pathway) params.set("pathway_key", pathway.key);
  const [programmeDetails, courses] = await Promise.all([
    api(`/api/v1/programme?${params}`),
    api(`/api/v1/catalogue?${params}`),
  ]);
  state.programmeDetails = programmeDetails;
  state.courses = courses;
}

function setStep(step) {
  state.currentStep = step;
  const order = ["route", "intent", "evidence", "account"];
  const currentIndex = order.indexOf(step);
  document.querySelectorAll("#stepList li").forEach(item => {
    const index = order.indexOf(item.dataset.step);
    item.classList.toggle("active", index === currentIndex);
    item.classList.toggle("complete", index < currentIndex);
  });
  $("routeStep").classList.toggle("hidden", step !== "route");
  $("intentStep").classList.toggle("hidden", step !== "intent");
  $("evidenceStep").classList.toggle("hidden", step !== "evidence");
  const labels = {
    route: ["Step 1 of 3", "Choose the qualification that governs you"],
    intent: ["Step 2 of 3", "Define the academic route you are trying to complete"],
    evidence: ["Step 3 of 3", "Bring the transcript into the reasoning process"],
  };
  if (labels[step]) {
    $("workspaceKicker").textContent = labels[step][0];
    $("workspaceTitle").textContent = labels[step][1];
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function continueFromRoute() {
  if (!routeIsReady()) return;
  $("routeContinue").disabled = true;
  $("routeContinue").textContent = "Preparing route…";
  try {
    await loadRouteData();
    setStep("intent");
  } catch (error) {
    $("setupError").textContent = error.message;
    $("setupError").classList.remove("hidden");
  } finally {
    $("routeContinue").disabled = !routeIsReady();
    $("routeContinue").textContent = "Continue to academic intent";
  }
}

function validateIntent() {
  const required = Number(state.programme?.required_majors || 0);
  const selected = selectedMajors();
  if (selected.length < required) {
    $("setupError").textContent = `Select at least ${required} major${required === 1 ? "" : "s"} for this route.`;
    $("setupError").classList.remove("hidden");
    return false;
  }
  $("setupError").classList.add("hidden");
  return true;
}

function chooseFile(file) {
  $("analysisError").classList.add("hidden");
  if (!file) {
    state.selectedFile = null;
    $("selectedFile").textContent = "No file selected";
    $("analyseButton").disabled = true;
    return;
  }
  const validName = String(file.name || "").toLowerCase().endsWith(".pdf");
  const validType = !file.type || ["application/pdf", "application/octet-stream"].includes(file.type);
  if (!validName || !validType) {
    state.selectedFile = null;
    $("transcriptFile").value = "";
    $("selectedFile").textContent = "No file selected";
    $("analysisError").textContent = "Choose an official transcript PDF. Other file types cannot be analysed.";
    $("analysisError").classList.remove("hidden");
    $("analyseButton").disabled = true;
    return;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    state.selectedFile = null;
    $("transcriptFile").value = "";
    $("analysisError").textContent = `This PDF is ${(file.size / 1024 / 1024).toFixed(1)} MB. The upload limit is 20 MB.`;
    $("analysisError").classList.remove("hidden");
    $("analyseButton").disabled = true;
    return;
  }
  state.selectedFile = file;
  $("selectedFile").textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  $("analyseButton").disabled = false;
  announce(`${file.name} selected.`);
}

async function analyse() {
  if (!state.selectedFile || !state.programme) return;
  const params = new URLSearchParams({
    faculty: state.faculty,
    programme: state.programme.key,
    majors: selectedMajors().join(","),
  });
  const pathway = selectedPathway();
  if (pathway) params.set("pathway", pathway.key);
  const years = $("yearsRegistered").value;
  if (years) params.set("years_registered", years);
  const form = new FormData();
  form.append("file", state.selectedFile);
  $("analysisError").classList.add("hidden");
  $("analysisProgress").classList.remove("hidden");
  $("analyseButton").disabled = true;
  $("analysisProgressText").textContent = "Reading transcript evidence and applying only the selected route…";
  try {
    state.report = await api(`/api/v1/analyse?${params}`, { method: "POST", body: form });
    state.reportTab = "overview";
    renderReport();
    $("setupPanel").classList.add("hidden");
    $("reportPanel").classList.remove("hidden");
    setStep("account");
    announce("Your academic account is ready.");
  } catch (error) {
    const retry = error.status === 429 && error.retryAfter ? ` Try again in ${error.retryAfter} seconds.` : "";
    $("analysisError").textContent = `${error.message}${retry}`;
    $("analysisError").classList.remove("hidden");
    announce("The transcript could not be analysed.");
  } finally {
    $("analysisProgress").classList.add("hidden");
    $("analyseButton").disabled = !state.selectedFile;
  }
}

function blockingRequirements() {
  return asArray(state.report?.requirements).filter(requirement => requirement.blocking !== false);
}

function completionPercent() {
  const rows = blockingRequirements();
  if (!rows.length) return 0;
  return Math.round(rows.filter(row => row.complete).length / rows.length * 100);
}

function blockersSummary() {
  const report = state.report || {};
  const incomplete = blockingRequirements().filter(row => !row.complete);
  const failures = Object.values(report.failed_attempts || {}).reduce((total, count) => total + Number(count || 0), 0);
  if (report.exclusion_risk?.at_risk) return "A represented readmission threshold may require urgent attention.";
  if (incomplete.length) return `${incomplete.length} blocking requirement${incomplete.length === 1 ? " remains" : "s remain"} in the represented route.`;
  if (failures) return `${failures} failed attempt${failures === 1 ? " remains" : "s remain"} visible in the academic history.`;
  return "No represented blocking requirement is currently incomplete.";
}

function nextSummary() {
  const count = asArray(state.report?.eligible_courses).length;
  if (!count) return "No course can currently be recommended from represented prerequisite evidence.";
  return `${count} route-visible course option${count === 1 ? " is" : "s are"} available for consideration, subject to live registration conditions.`;
}

function reportTabs() {
  return [
    ["overview", "Overview"],
    ["requirements", "Requirements"],
    ["majors", "Majors"],
    ["next", "Next courses"],
    ["evidence", "Evidence & limits"],
  ];
}

function requirementCard(requirement) {
  const required = Number(requirement.required || 0);
  const current = Number(requirement.current || 0);
  const percent = required > 0 ? Math.max(0, Math.min(100, current / required * 100)) : (requirement.complete ? 100 : 0);
  return `
    <article class="requirement-card ${requirement.complete ? "complete" : ""}">
      <div class="requirement-icon" aria-hidden="true">${requirement.complete ? "✓" : "!"}</div>
      <div>
        <h3>${esc(requirement.label)}</h3>
        <p>${esc(requirement.detail || requirement.explanation || "No further explanation is represented.")}</p>
        <div class="progress-track" aria-label="${esc(requirement.label)} progress"><i style="width:${percent}%"></i></div>
      </div>
      <span class="badge ${esc(requirement.status || "unverified")}">${esc(requirement.status || "unverified")}</span>
    </article>
  `;
}

function overviewSection() {
  const report = state.report;
  const requirements = blockingRequirements();
  const completed = requirements.filter(row => row.complete).length;
  const risk = report.exclusion_risk || {};
  const distinction = report.distinction || {};
  return `
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Academic position</h2></div><p>These figures are computed within ${esc(report.programme_name)}${report.pathway_name ? ` · ${esc(report.pathway_name)}` : ""}.</p></div>
      <div class="metric-grid">
        <article class="metric-card"><strong>${esc(report.credits_completed)}</strong><span>NQF credits counted</span></article>
        <article class="metric-card"><strong>${esc(report.level_7_credits)}</strong><span>NQF level 7 credits</span></article>
        <article class="metric-card"><strong>${esc(report.semester_course_equivalents)}</strong><span>semester-course equivalents</span></article>
        <article class="metric-card"><strong>${completed}/${requirements.length}</strong><span>blocking requirements complete</span></article>
      </div>
    </section>
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Immediate judgment</h2></div><p>The system separates represented thresholds from matters that still require faculty confirmation.</p></div>
      <div class="notice-stack">
        <div class="notice-row ${risk.at_risk ? "" : "info"}"><strong>${risk.at_risk ? "Possible readmission risk" : "Readmission indicator"}</strong><br>${esc(risk.basis || "No programme-specific readmission conclusion could be produced.")} ${esc(asArray(risk.reasons).join(" "))}</div>
        <div class="notice-row info"><strong>${distinction.qualification_eligible ? "Represented distinction threshold appears met" : "Distinction is not confirmed"}</strong><br>${esc(distinction.reason || "The represented evidence does not establish a distinction conclusion.")}</div>
      </div>
    </section>
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Most important outstanding rules</h2></div><p>Open the Requirements tab for the full rule account.</p></div>
      <div class="requirement-list">${requirements.filter(row => !row.complete).slice(0, 5).map(requirementCard).join("") || '<div class="empty-report">No represented blocking requirement is incomplete.</div>'}</div>
    </section>
  `;
}

function requirementsSection() {
  const rows = asArray(state.report?.requirements);
  return `
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Qualification requirements</h2></div><p>Completion and verification are separate. A rule may appear complete but remain provisional.</p></div>
      <div class="requirement-list">${rows.map(requirementCard).join("") || '<div class="empty-report">No requirement records were produced.</div>'}</div>
    </section>
  `;
}

function majorsSection() {
  const majors = asArray(state.report?.majors);
  return `
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Major progress</h2></div><p>Only majors represented within the selected route are assessed.</p></div>
      <div class="major-grid">${majors.map(major => `
        <article class="major-card">
          <div class="major-card-head"><h3>${esc(major.name)}</h3><span class="badge ${major.complete ? "complete" : esc(major.status)}">${major.complete ? "complete" : esc(major.status)}</span></div>
          ${asArray(major.completed_requirements).length ? `<ul>${major.completed_requirements.map(item => `<li>✓ ${esc(item)}</li>`).join("")}</ul>` : ""}
          ${asArray(major.outstanding_requirements).length ? `<ul>${major.outstanding_requirements.map(item => `<li>${esc(item)}</li>`).join("")}</ul>` : ""}
        </article>
      `).join("") || '<div class="empty-report">This programme does not use a represented major structure, or no majors were selected.</div>'}</div>
    </section>
  `;
}

function nextCoursesSection() {
  const courses = asArray(state.report?.eligible_courses);
  return `
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Route-visible next courses</h2></div><p>These are curriculum and prerequisite conclusions—not live registration promises.</p></div>
      <div class="filter-bar"><input id="courseFilter" placeholder="Search course code, name or department"><select id="courseStatusFilter"><option value="">All evidence states</option><option value="verified">Verified</option><option value="provisional">Provisional</option><option value="unverified">Unverified</option></select></div>
      <div class="course-grid" id="nextCourseGrid">${renderCourseCards(courses)}</div>
    </section>
  `;
}

function renderCourseCards(courses) {
  return courses.map(course => `
    <article class="course-card" data-course-search="${esc(`${course.code} ${course.name} ${course.department}`.toLowerCase())}" data-course-status="${esc(course.status || "unverified")}">
      <div class="course-card-head"><div><div class="course-code">${esc(course.code)}</div><h3>${esc(course.name)}</h3></div><span class="badge ${esc(course.status || "unverified")}">${esc(course.status || "unverified")}</span></div>
      <p>${esc(course.reason || "Visible within the selected route.")}</p>
      <div class="course-meta"><span>${esc(course.credits)} credits</span><span>${esc(course.department || "Department not recorded")}</span>${asArray(course.offered).length ? `<span>${esc(course.offered.join(", "))}</span>` : ""}</div>
    </article>
  `).join("") || '<div class="empty-report">No course recommendation can be made from the represented prerequisite data.</div>';
}

function evidenceSection() {
  const report = state.report;
  const programme = state.programme || {};
  const pathway = selectedPathway();
  const warnings = asArray(report.warnings);
  const verifications = asArray(report.verification_messages);
  return `
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Evidence and limits</h2></div><p>This is the audit surface: what was selected, what was computed, and what remains outside the model.</p></div>
      <div class="evidence-grid-report">
        <article class="evidence-card"><span>Scope</span><h3>${esc(report.programme_name)}</h3><p>${pathway ? esc(pathway.name) : "No additional pathway selected."} Scope status: ${esc(report.scope_status)}.</p></article>
        <article class="evidence-card"><span>Curriculum source</span><h3>${esc(state.context?.catalogue_version || "2026 catalogue")}</h3><p>${esc(state.context?.source || programme.source?.document || "Faculty handbook-derived catalogue")}</p></article>
        <article class="evidence-card"><span>Computed conclusion</span><h3>${esc(titleCase(report.graduation_status))}</h3><p>${report.graduation_eligible ? "All represented blocking rules are complete." : "At least one represented blocking rule is incomplete or cannot be verified."}</p></article>
        <article class="evidence-card"><span>Operational boundary</span><h3>Timetable not connected</h3><p>Live offering, clash, venue, capacity and registration-window information must still be confirmed institutionally.</p></article>
      </div>
    </section>
    <section class="report-section">
      <div class="report-section-heading"><div><h2>Warnings and verification questions</h2></div></div>
      <div class="notice-stack">
        ${verifications.map(item => `<div class="notice-row info">${esc(item)}</div>`).join("")}
        ${warnings.map(item => `<div class="notice-row">${esc(item)}</div>`).join("")}
        ${!verifications.length && !warnings.length ? '<div class="empty-report">No additional warning was produced.</div>' : ""}
      </div>
    </section>
  `;
}

function renderReportSection() {
  const container = $("reportSectionContent");
  const sections = {
    overview: overviewSection,
    requirements: requirementsSection,
    majors: majorsSection,
    next: nextCoursesSection,
    evidence: evidenceSection,
  };
  container.innerHTML = sections[state.reportTab]();
  if (state.reportTab === "next") {
    const applyFilters = () => {
      const query = $("courseFilter").value.trim().toLowerCase();
      const status = $("courseStatusFilter").value;
      document.querySelectorAll("#nextCourseGrid .course-card").forEach(card => {
        const matchesQuery = !query || card.dataset.courseSearch.includes(query);
        const matchesStatus = !status || card.dataset.courseStatus === status;
        card.classList.toggle("hidden", !(matchesQuery && matchesStatus));
      });
    };
    $("courseFilter").addEventListener("input", applyFilters);
    $("courseStatusFilter").addEventListener("change", applyFilters);
  }
}

function renderReport() {
  const report = state.report;
  const percent = completionPercent();
  const risk = report.exclusion_risk || {};
  const blockersClass = risk.at_risk ? "alert" : blockingRequirements().some(row => !row.complete) ? "caution" : "good";
  $("reportContent").innerHTML = `
    <section class="report-hero">
      <div>
        <span class="badge ${esc(report.graduation_status)}">${esc(titleCase(report.graduation_status))}</span>
        <h1>${esc(report.student_name || "Academic account")}</h1>
        <p>${esc(report.programme_name)}${report.pathway_name ? ` · ${esc(report.pathway_name)}` : ""} · ${esc(titleCase(report.scope_status))} scope</p>
      </div>
      <div class="report-score"><strong>${percent}%</strong><span>represented blockers complete</span></div>
    </section>
    <section class="decision-grid" aria-label="Decision summary">
      <article class="decision-card good"><span>Where am I now?</span><h2>${esc(report.credits_completed)} credits counted</h2><p>${blockingRequirements().filter(row => row.complete).length} of ${blockingRequirements().length} blocking requirements are represented as complete.</p></article>
      <article class="decision-card ${blockersClass}"><span>What is blocking me?</span><h2>${risk.at_risk ? "Attention may be urgent" : "Outstanding academic conditions"}</h2><p>${esc(blockersSummary())}</p></article>
      <article class="decision-card caution"><span>What can I do next?</span><h2>${asArray(report.eligible_courses).length} route-visible options</h2><p>${esc(nextSummary())}</p></article>
    </section>
    <nav class="report-tabs" aria-label="Academic account sections">
      ${reportTabs().map(([key, label]) => `<button class="report-tab ${state.reportTab === key ? "active" : ""}" type="button" data-report-tab="${key}">${label}</button>`).join("")}
    </nav>
    <div id="reportSectionContent"></div>
  `;
  document.querySelectorAll("[data-report-tab]").forEach(button => {
    button.addEventListener("click", () => {
      state.reportTab = button.dataset.reportTab;
      document.querySelectorAll("[data-report-tab]").forEach(tab => tab.classList.toggle("active", tab === button));
      renderReportSection();
    });
  });
  renderReportSection();
}

function copySummary() {
  if (!state.report) return;
  const report = state.report;
  const incomplete = blockingRequirements().filter(row => !row.complete).map(row => `- ${row.label}: ${row.detail || row.explanation || "incomplete"}`);
  const summary = [
    "CurriculumAdvisor academic account",
    `${report.student_name || "Student"} — ${report.programme_name}${report.pathway_name ? ` / ${report.pathway_name}` : ""}`,
    `Conclusion: ${titleCase(report.graduation_status)}`,
    `Credits counted: ${report.credits_completed}`,
    `NQF level 7 credits: ${report.level_7_credits}`,
    `Scope status: ${titleCase(report.scope_status)}`,
    "",
    "Outstanding represented requirements:",
    ...(incomplete.length ? incomplete : ["- None"]),
    "",
    "Important: live timetable, capacity, concessions and institutional approval remain confirmable.",
  ].join("\n");
  navigator.clipboard.writeText(summary).then(() => announce("Report summary copied."));
}

function showRouteDialog() {
  if (!state.programme) return;
  const pathway = selectedPathway();
  $("routeDialogContent").innerHTML = `
    <h2>${esc(state.programme.name)}</h2>
    ${pathway ? `<p><strong>Pathway:</strong> ${esc(pathway.name)}</p>` : ""}
    <div class="programme-metrics">
      <div><strong>${esc(state.programme.minimum_nqf_credits || "—")}</strong><span>minimum credits</span></div>
      <div><strong>${esc(state.programme.minimum_duration_years || "—")}</strong><span>minimum years</span></div>
      <div><strong>${esc(state.programme.required_majors || 0)}</strong><span>required majors</span></div>
      <div><strong>${esc(state.programme.scope_status || "—")}</strong><span>scope state</span></div>
    </div>
    <div class="trust-boundary-list"><div><span>→</span><span>Faculty: ${esc(state.context?.name)}</span></div><div><span>→</span><span>Selected majors: ${esc(selectedMajors().join(", ") || "None required or selected")}</span></div><div><span>→</span><span>Catalogue: ${esc(state.context?.catalogue_version || "2026")}</span></div></div>
  `;
  $("routeDialog").showModal();
}

function goHome() {
  state.faculty = null;
  state.context = null;
  resetRouteState();
  $("workspaceView").classList.add("hidden");
  $("landingView").classList.remove("hidden");
  history.pushState({}, "", "/");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetAnalysis() {
  state.report = null;
  state.selectedFile = null;
  $("transcriptFile").value = "";
  $("selectedFile").textContent = "No file selected";
  $("reportPanel").classList.add("hidden");
  $("setupPanel").classList.remove("hidden");
  setStep("evidence");
  $("analyseButton").disabled = true;
}

function bindEvents() {
  $("homeButton").addEventListener("click", goHome);
  $("backToFaculties").addEventListener("click", goHome);
  $("programmeSelect").addEventListener("change", onProgrammeChange);
  $("pathwaySelect").addEventListener("change", onPathwayChange);
  $("routeContinue").addEventListener("click", continueFromRoute);
  $("intentContinue").addEventListener("click", () => { if (validateIntent()) setStep("evidence"); });
  document.querySelectorAll("[data-back-step]").forEach(button => button.addEventListener("click", () => setStep(button.dataset.backStep)));
  $("uploadCard").addEventListener("click", () => $("transcriptFile").click());
  $("transcriptFile").addEventListener("change", event => chooseFile(event.target.files[0]));
  for (const eventName of ["dragenter", "dragover"]) {
    $("uploadCard").addEventListener(eventName, event => { event.preventDefault(); $("uploadCard").classList.add("drag"); });
  }
  for (const eventName of ["dragleave", "drop"]) {
    $("uploadCard").addEventListener(eventName, event => { event.preventDefault(); $("uploadCard").classList.remove("drag"); });
  }
  $("uploadCard").addEventListener("drop", event => chooseFile(event.dataTransfer.files[0]));
  $("analyseButton").addEventListener("click", analyse);
  $("newAnalysisButton").addEventListener("click", resetAnalysis);
  $("copySummaryButton").addEventListener("click", copySummary);
  $("printButton").addEventListener("click", () => window.print());
  $("routeSummaryButton").addEventListener("click", showRouteDialog);
  for (const id of ["methodButton", "exploreMethodButton"]) $(id).addEventListener("click", () => $("methodDialog").showModal());
  $("statusButton").addEventListener("click", () => checkReadiness({ openDialog: true }));
  window.addEventListener("popstate", () => {
    if (location.pathname.startsWith("/faculty/")) {
      const key = decodeURIComponent(location.pathname.split("/").filter(Boolean).pop());
      if (key !== state.faculty) openFaculty(key, { historyMode: "replace" });
    } else {
      $("workspaceView").classList.add("hidden");
      $("landingView").classList.remove("hidden");
    }
  });
}

bindEvents();
boot();
