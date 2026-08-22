"""Public Python API for supplier-scorecard.

The v1.0 implementation remains in the repository's compatibility modules
(`main.py` and `pipeline.py`). This package provides a stable import namespace
without breaking existing source-checkout workflows.
"""

from main import (
    CATEGORY_PROFILES,
    DEFAULT_POLICY,
    VERSION,
    apply_policy,
    explain_portfolio,
    get_category_profile,
    load_profile_file,
    normalize_policy,
    normalize_weights,
    recommendation,
    resolve_profile,
    score_csv,
    score_from_tools,
    score_supplier,
)

__version__ = "1.0.0"

__all__ = [
    "CATEGORY_PROFILES",
    "DEFAULT_POLICY",
    "VERSION",
    "__version__",
    "apply_policy",
    "explain_portfolio",
    "get_category_profile",
    "load_profile_file",
    "normalize_policy",
    "normalize_weights",
    "recommendation",
    "resolve_profile",
    "score_csv",
    "score_from_tools",
    "score_supplier",
]
