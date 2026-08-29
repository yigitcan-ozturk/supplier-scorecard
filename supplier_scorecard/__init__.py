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
from .vendor_trend import (
    TREND_INTEGRATION_VERSION,
    apply_vendor_trend,
    normalize_vendor_trend,
    score_from_tools_with_trend,
    vendor_trend_decision,
)

__version__ = "1.1.0"

__all__ = [
    "CATEGORY_PROFILES",
    "DEFAULT_POLICY",
    "TREND_INTEGRATION_VERSION",
    "VERSION",
    "__version__",
    "apply_policy",
    "apply_vendor_trend",
    "explain_portfolio",
    "get_category_profile",
    "load_profile_file",
    "normalize_policy",
    "normalize_vendor_trend",
    "normalize_weights",
    "recommendation",
    "resolve_profile",
    "score_csv",
    "score_from_tools",
    "score_from_tools_with_trend",
    "score_supplier",
    "vendor_trend_decision",
]
