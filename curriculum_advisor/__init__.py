"""Product-layer helpers for the CurriculumAdvisor modular monolith.

The academic engine and catalogue data remain in their existing locations.
This package owns product metadata, release integrity views, and future-facing
web concerns so presentation changes do not mutate academic rules.
"""

from .product import PRODUCT_NAME, PRODUCT_VERSION

__all__ = ["PRODUCT_NAME", "PRODUCT_VERSION"]
