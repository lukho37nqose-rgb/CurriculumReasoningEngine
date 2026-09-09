"use strict";

// Internal shared frontend API, not a public external API. No institution shell state.
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

function studentConclusionCard(item, presentation = {}) {
  // Array.map supplies an index as its second argument, not presentation metadata.
  return StudentLanguage.card(item, typeof presentation === "object" ? presentation : {});
}
