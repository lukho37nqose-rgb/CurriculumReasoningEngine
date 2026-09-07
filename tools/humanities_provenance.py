"""Bounded declaration of the seven accepted PPE source relationships."""

PPE_IDS = (
    "ppe_year1", "ppe_year2_fixed", "ppe_year2_politics", "ppe_year2_other",
    "ppe_eco3025", "ppe_phi3", "ppe_pol3",
)
SOURCE_ID = "uct:2026:document:humanities-undergraduate-handbook"


def build_provenance(programmes):
    rules = programmes["bsocsc_ppe"]["curriculum_rules"]
    selected = []
    for key in PPE_IDS:
        matches = [rule for rule in rules if rule.get("id") == key]
        if len(matches) != 1:
            raise ValueError(f"Missing or duplicate governed PPE rule: {key}")
        rule = matches[0]
        source = rule["source"]
        if source["document"] != "2026 Humanities Undergraduate Handbook":
            raise ValueError("Unexpected PPE source identity")
        selected.append({
            "relationship_id": f"uct:2026:bsocsc_ppe:{key}:source",
            "institution_id": "uct", "release_id": "2026",
            "requirement_id": key, "programme_key": "bsocsc_ppe",
            "source_id": SOURCE_ID, "relationship_type": "DIRECT_RULE_SOURCE",
            "locator": {key: value for key, value in source.items() if key != "document"},
            "relationship_status": "unverified",
            "rule_status": rule.get("verification_status", "unverified"),
        })
    return {
        "institution_sources": [{
            "source_id": SOURCE_ID, "institution_id": "uct", "release_id": "2026",
            "source_kind": "document", "title": "2026 Humanities Undergraduate Handbook",
            "source_status": "checksum_mismatch_unverified_source_archive",
        }],
        "requirement_source_relationships": selected,
    }
