"""
Utility functions for course weight, level, department, and major key normalisation.
Shared between rule_engine.py and reasoner.py to avoid circular imports.
"""
import re
from typing import List, Optional
from .models import Catalogue, StudentRecord

_SUFFIX_WEIGHTS = {
    "F": 1.0, "S": 1.0, "FS": 1.0, "SF": 1.0,
    "H": 1.0, "W": 2.0,
    "P": 1.0, "U": 1.0, "L": 1.0, "Z": 1.0,
}

_MAJOR_NAME_TO_KEY = {
    "history": "history",
    "historical studies": "history",
    "economics": "economics",
    "philosophy": "philosophy",
    "politics": "politics_and_governance",
    "politics & governance": "politics_and_governance",
    "politics and governance": "politics_and_governance",
    "political studies": "politics_and_governance",
    "sociology": "sociology",
    "african studies": "african_studies",
    "gender studies": "gender_studies",
    "linguistics": "linguistics",
    "anthropology": "anthropology",
    "archaeology": "archaeology",
    "psychology": "psychology",
    "social development": "social_development",
    "industrial sociology": "industrial_sociology",
    "applied statistics": "applied_statistics",
    "mathematical statistics": "mathematical_statistics",
    "theatre and dance studies": "theatre_dance_studies",
    "theatre & dance studies": "theatre_dance_studies",
    "the study of religions": "study_of_religions",
    "study of religions": "study_of_religions",
}


def _course_weight(code: str) -> float:
    """Return semester-course equivalent weight from the code suffix."""
    m = re.search(r"\d(\D+)$", code)
    if m:
        suffix = m.group(1).upper()
        return _SUFFIX_WEIGHTS.get(suffix, 1.0)
    return 1.0


def _is_senior(code: str) -> bool:
    """True if the course is 2000-level or above (senior = level 6/7)."""
    m = re.search(r"(\d)\d{3}", code)
    if m:
        return int(m.group(1)) >= 2
    return False


def _is_humanities(code: str, catalogue: Catalogue) -> bool:
    """Use the handbook-derived course flag rather than prefix inference."""
    fact = catalogue.courses.get(code)
    return bool(fact and fact.counts_as_humanities)


def _normalise_major_keys(declared: List[str], catalogue: Catalogue) -> List[str]:
    """Convert declared major names to catalogue keys using a multi-tiered matching strategy."""
    keys = []
    for name in declared:
        name_clean = name.lower().strip()
        # Remove common suffixes like "specialisation", "specialization", "major", "stream", "programme"
        name_clean = re.sub(r"\s+(specialisation|specialization|major|stream|programme)\b", "", name_clean)
        
        # Tier 1: Static mapping lookup
        key = _MAJOR_NAME_TO_KEY.get(name_clean)
        if key is not None:
            keys.append(key)
            continue
            
        # Tier 2: Direct key lookup
        direct_key = name_clean.replace(" ", "_").replace("&", "and").replace(":", "").replace(",", "").replace("(", "").replace(")", "")
        direct_key = re.sub(r"_+", "_", direct_key)
        if direct_key in catalogue.majors:
            keys.append(direct_key)
            continue
            
        # Tier 3: Code-based lookup (e.g. if the declared name is a qualification code)
        found_code = False
        for m_key, m_def in catalogue.majors.items():
            if v := m_def.__dict__.get("code"):
                if v.lower() == name_clean:
                    keys.append(m_key)
                    found_code = True
                    break
        if found_code:
            continue
            
        # Tier 4: Exact match against the catalogue display name.
        for m_key, m_def in catalogue.majors.items():
            m_name_clean = re.sub(
                r"\s+(specialisation|specialization|major|stream|programme)\b",
                "",
                m_def.name.lower(),
            ).strip()
            if name_clean == m_name_clean:
                keys.append(m_key)
                break
        else:
            m_key = None
        if m_key is not None:
            continue

        # Tier 5: Conservative word-overlap matching.  A low threshold can map
        # an unknown major to an unrelated catalogue entry and silently award
        # progress, so fuzzy matches must be near-exact.
        best_key = None
        best_score = 0.0
        # Clean up special characters to ensure words are split correctly
        name_clean_spaced = name_clean.replace("(", " ").replace(")", " ").replace(":", " ").replace("-", " ").replace(",", " ").replace("&", " and ")
        name_words = set(name_clean_spaced.split())
        for m_key, m_def in catalogue.majors.items():
            m_name_clean = re.sub(r"\s+(specialisation|specialization|major|stream|programme)\b", "", m_def.name.lower())
            m_name_spaced = m_name_clean.replace("(", " ").replace(")", " ").replace(":", " ").replace("-", " ").replace(",", " ").replace("&", " and ")
            m_words = set(m_name_spaced.split())
            intersection = name_words.intersection(m_words)
            if intersection:
                # Jaccard-like similarity score
                score = len(intersection) / max(len(name_words), len(m_words))
                if score > best_score:
                    best_score = score
                    best_key = m_key
                    
        if best_score >= 0.8:
            keys.append(best_key)
        else:
            # Fallback: skip (will generate a warning in the report)
            pass
            
    return keys


def _infer_programme_key(programme_name: str) -> str:
    """Map common UCT transcript programme labels to catalogue routes."""
    name = programme_name.lower().strip()
    # Commerce transcripts commonly expose the official programme/plan code.
    # Preserve that exact route rather than guessing from a broad BCom or
    # BBusSci label.  Some printed material omits a leading zero in CB25 codes.
    commerce_code = re.search(r"\b(c[bu]\d{2,3}[a-z]{3}\d{2})\b", name, re.I)
    if commerce_code:
        key = commerce_code.group(1).lower()
        prefix = re.match(r"(c[bu])(\d{2,3})([a-z]{3}\d{2})", key, re.I)
        if prefix and len(prefix.group(2)) == 2:
            key = prefix.group(1).lower() + "0" + prefix.group(2) + prefix.group(3).lower()
        return key
    if ("bachelor of science" in name or re.search(r"\bbsc\b", name)) and "engineering" not in name and "bsc(eng)" not in name and "bsc (eng)" not in name:
        return "bsc_science_edp" if ("extended" in name or "sb016" in name) else "bsc_science"
    if "bachelor of laws" in name or re.search(r"\bllb\b", name):
        if "five" in name or "5-year" in name or "lb003" in name:
            return "llb_five_year_continuing"
        if "two-year" in name or "2-year" in name or "combined" in name:
            return "llb_two_year_combined"
        if "three-year" in name or "3-year" in name or "graduate" in name:
            return "llb_three_year_graduate"
        return "llb_four_year_undergraduate"
    extended = "extended" in name
    if "philosophy, politics and economics" in name or "ppe" in name:
        return "bsocsc_ppe"
    if "social work" in name or "bsw" in name:
        return "bsw"
    if "screen production" in name:
        return "ba_screen_production"
    if "fine art" in name:
        return "ba_fine_art"
    if "music" in name or "bmus" in name:
        return "diploma_music_performance" if "diploma" in name else "bmus"
    if "theatre" in name or "performance" in name:
        return "diploma_theatre_performance" if "diploma" in name else "ba_theatre_performance"
    if "bachelor of social science" in name or "bsocsc" in name:
        return "bsocsc_extended" if extended else "bsocsc_regular"
    if "bachelor of arts" in name or re.search(r"\bba\b", name):
        return "ba_extended" if extended else "ba_regular"
    if "extended" in name:
        return "bsocsc_extended"
    return "unknown_programme"


def _infer_faculty_key(programme_name: str) -> str:
    """Map the student's programme string to the correct faculty key."""
    name = programme_name.lower()
    if (
        "commerce" in name
        or "bcom" in name
        or "business science" in name
        or "actuarial science" in name
    ):
        return "uct_commerce"
    elif (
        "engineering" in name
        or "bsc(eng)" in name
        or "bsc (eng)" in name
        or "architectural studies" in name
        or "architecture" in name
        or "geomatics" in name
        or "construction studies" in name
        or "property studies" in name
        or "city and regional planning" in name
    ):
        return "uct_ebe"
    elif (
        "medicine" in name
        or "surgery" in name
        or "mbchb" in name
        or "health science" in name
        or "occupational therapy" in name
        or "physiotherapy" in name
        or "audiology" in name
        or "speech-language pathology" in name
    ):
        return "uct_health"
    elif (
        "bachelor of laws" in name
        or re.search(r"\bllb\b", name)
        or "law faculty" in name
    ):
        return "uct_law"
    elif (
        "social science" in name
        or "social work" in name
        or "bachelor of arts" in name
        or "bachelor of social" in name
        or "music" in name
        or "fine art" in name
        or "theatre" in name
        or "performance" in name
        or "adult and community education" in name
        or "foundation phase" in name
        or "intermediate phase" in name
    ):
        return "uct_humanities"
    elif "science" in name or "bsc" in name:
        return "uct_science"
    elif "law" in name or "llb" in name:
        return "uct_law"
    return "unknown_faculty"
