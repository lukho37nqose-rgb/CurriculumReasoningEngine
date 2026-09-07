"""Legacy utility functions and major key normalisation."""

import re

from curriculum_reasoning_engine.institutions import (
    UCTCourseLoadFramework,
    get_institution_release,
)

from .models import Catalogue

_LEGACY_UCT_LOAD_FRAMEWORK = UCTCourseLoadFramework()

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
    """Legacy UCT course-load shim; new reasoning uses CourseLoadFramework."""
    return _LEGACY_UCT_LOAD_FRAMEWORK.load_equivalent(code)


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


def _normalise_major_keys(declared: list[str], catalogue: Catalogue) -> list[str]:
    """Convert declared major names to catalogue keys using a multi-tiered matching strategy."""
    keys = []
    for name in declared:
        name_clean = name.lower().strip()
        # Remove common suffixes like "specialisation", "specialization", "major", "stream", "programme"
        name_clean = re.sub(
            r"\s+(specialisation|specialization|major|stream|programme)\b",
            "",
            name_clean,
        )

        # Tier 1: Static mapping lookup
        key = _MAJOR_NAME_TO_KEY.get(name_clean)
        if key is not None:
            keys.append(key)
            continue

        # Tier 2: Direct key lookup
        direct_key = (
            name_clean.replace(" ", "_")
            .replace("&", "and")
            .replace(":", "")
            .replace(",", "")
            .replace("(", "")
            .replace(")", "")
        )
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
        name_clean_spaced = (
            name_clean.replace("(", " ")
            .replace(")", " ")
            .replace(":", " ")
            .replace("-", " ")
            .replace(",", " ")
            .replace("&", " and ")
        )
        name_words = set(name_clean_spaced.split())
        for m_key, m_def in catalogue.majors.items():
            m_name_clean = re.sub(
                r"\s+(specialisation|specialization|major|stream|programme)\b",
                "",
                m_def.name.lower(),
            )
            m_name_spaced = (
                m_name_clean.replace("(", " ")
                .replace(")", " ")
                .replace(":", " ")
                .replace("-", " ")
                .replace(",", " ")
                .replace("&", " and ")
            )
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
    """Transitional shim for legacy imports; UCT policy lives on the release."""
    return get_institution_release("uct", "2026").infer_programme(programme_name)


def _infer_faculty_key(programme_name: str) -> str:
    """Transitional shim for legacy imports; UCT policy lives on the release."""
    return get_institution_release("uct", "2026").infer_academic_unit(programme_name)
