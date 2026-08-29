"""Public Python API for supplier-scorecard.

Package release v1.1 adds operational decision-record capabilities while the
frozen deterministic scoring/result contract remains version 1.0 in the
repository's compatibility modules (`main.py` and `pipeline.py`).
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

__version__ = "1.1.0"

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
