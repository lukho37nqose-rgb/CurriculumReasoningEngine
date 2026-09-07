"""Institution release registry and compatibility models."""

from .achievement import ExternalQualificationSystem, NumericAchievementScheme, SymbolicAchievementScheme
from .catalogues import CatalogueDescriptor, InstitutionCatalogueResolver
from .coding import CourseCodeScheme
from .course_load import CourseLoadFramework
from .credit_framework import AcademicCreditFramework
from .grading import GradingScheme, ResultState
from .models import AcademicUnit, InstitutionRelease
from .periods import AcademicPeriodScheme, ExplicitAcademicPeriodScheme, LegacyAcademicYearPeriodScheme
from .registry import (
    get_institution_release,
    register_institution_release,
    unregister_institution_release,
)
from .routing import InstitutionRouteResolver, RouteResolution
from .uct_coding import UCTCourseCodeScheme
from .uct_course_load import UCTCourseLoadFramework
from .uct_credit_framework import UCTCreditFramework
from .uct_grading import UCTGradingScheme

__all__ = [
    "AcademicUnit",
    "AcademicCreditFramework",
    "CatalogueDescriptor",
    "NumericAchievementScheme",
    "SymbolicAchievementScheme",
    "ExternalQualificationSystem",
    "CourseCodeScheme",
    "CourseLoadFramework",
    "GradingScheme",
    "InstitutionRelease",
    "AcademicPeriodScheme",
    "ExplicitAcademicPeriodScheme",
    "LegacyAcademicYearPeriodScheme",
    "InstitutionCatalogueResolver",
    "InstitutionRouteResolver",
    "ResultState",
    "RouteResolution",
    "UCTCreditFramework",
    "UCTCourseCodeScheme",
    "UCTCourseLoadFramework",
    "UCTGradingScheme",
    "get_institution_release",
    "register_institution_release",
    "unregister_institution_release",
]
