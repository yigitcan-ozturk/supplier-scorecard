"""Vendor-risk trend integration for supplier-scorecard.

This module consumes the historical trend contract produced by
``vendor-risk-engine`` without changing supplier-scorecard's frozen numeric
scoring formula. Trend is an explicit decision/gate signal, never a hidden
score adjustment.
"""

import json
from copy import deepcopy
from pathlib import Path

from main import explain_supplier, extract_vendor_risk, load_json, score_from_tools

TREND_INTEGRATION_VERSION = "1.0"
TREND_DIRECTIONS = {
    "IMPROVING",
    "STABLE",
    "DETERIORATING",
    "INSUFFICIENT_HISTORY",
}
RISK_CLASSES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _same_supplier(expected, actual):
    return str(expected).strip().casefold() == str(actual).strip().casefold()


def _bounded_score(name, value):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be between 0 and 100.") from exc
    if not 0 <= number <= 100:
        raise ValueError(f"{name} must be between 0 and 100.")
    return number


def normalize_vendor_trend(payload, supplier, *, current_vendor_risk=None, score_tolerance=0.05):
    """Validate and normalize a vendor-risk-engine trend artifact.

    When ``current_vendor_risk`` is supplied, the trend artifact must describe
    the same current score within ``score_tolerance``. This fail-closed check
    prevents a historical artifact for a different scoring snapshot from being
    attached to a supplier decision.
    """

    if not isinstance(payload, dict):
        raise ValueError("vendor-risk trend JSON must be an object.")

    actual = payload.get("vendor", payload.get("supplier"))
    if actual is None or not _same_supplier(supplier, actual):
        raise ValueError(
            f"vendor-risk trend supplier mismatch: expected '{supplier}', found '{actual}'."
        )

    direction = str(payload.get("direction", "")).strip().upper()
    if direction not in TREND_DIRECTIONS:
        raise ValueError(
            "vendor-risk trend direction must be one of: "
            + ", ".join(sorted(TREND_DIRECTIONS))
        )

    risk_class = str(payload.get("current_risk", "")).strip().upper()
    if risk_class not in RISK_CLASSES:
        raise ValueError(
            "vendor-risk trend current_risk must be one of: "
            + ", ".join(sorted(RISK_CLASSES))
        )

    current_score = _bounded_score("vendor-risk trend current_score", payload.get("current_score"))

    try:
        observations = int(payload.get("observations"))
    except (TypeError, ValueError) as exc:
        raise ValueError("vendor-risk trend observations must be a positive integer.") from exc
    if observations < 1 or float(payload.get("observations")) != observations:
        raise ValueError("vendor-risk trend observations must be a positive integer.")

    latest_delta = payload.get("latest_delta")
    if latest_delta is not None:
        try:
            latest_delta = float(latest_delta)
        except (TypeError, ValueError) as exc:
            raise ValueError("vendor-risk trend latest_delta must be numeric or null.") from exc

    if direction == "INSUFFICIENT_HISTORY" and latest_delta is not None:
        raise ValueError("INSUFFICIENT_HISTORY trend must have latest_delta = null.")
    if direction != "INSUFFICIENT_HISTORY" and observations < 2:
        raise ValueError(f"{direction} trend requires at least two observations.")

    if current_vendor_risk is not None:
        current = _bounded_score("current vendor risk", current_vendor_risk)
        tolerance = float(score_tolerance)
        if tolerance < 0:
            raise ValueError("score_tolerance cannot be negative.")
        if abs(current_score - current) > tolerance:
            raise ValueError(
                "vendor-risk trend current_score does not match the current vendor-risk artifact: "
                f"trend={current_score:.2f}, current={current:.2f}, tolerance={tolerance:.2f}."
            )

    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    engine = meta.get("engine")
    if engine is not None and engine != "vendor-risk-engine":
        raise ValueError("vendor-risk trend meta.engine must be 'vendor-risk-engine'.")

    return {
        "integration_version": TREND_INTEGRATION_VERSION,
        "vendor": str(actual).strip(),
        "current_score": current_score,
        "current_risk": risk_class,
        "direction": direction,
        "latest_delta": latest_delta,
        "change_from_first": payload.get("change_from_first"),
        "observations": observations,
        "first_as_of_date": payload.get("first_as_of_date"),
        "current_as_of_date": payload.get("current_as_of_date"),
        "trend_tolerance": payload.get("trend_tolerance"),
        "source_meta": {
            "engine": meta.get("engine", "vendor-risk-engine"),
            "engine_version": meta.get("engine_version"),
            "model_version": meta.get("model_version"),
            "schema_version": meta.get("schema_version"),
        },
    }


def vendor_trend_decision(trend):
    """Translate trend into an explicit non-numeric decision signal."""

    direction = trend["direction"]
    risk_class = trend["current_risk"]
    delta = trend.get("latest_delta")
    delta_text = "n/a" if delta is None else f"{delta:+.2f}"

    if direction == "DETERIORATING" and risk_class in {"HIGH", "CRITICAL"}:
        return {
            "status": "ESCALATE",
            "review_required": True,
            "rule": "vendor_trend_deteriorating_high",
            "reason": (
                f"Vendor risk is {risk_class} and deteriorating ({delta_text} points versus the previous observation); "
                "human escalation is required."
            ),
        }
    if direction == "DETERIORATING" and risk_class == "MEDIUM":
        return {
            "status": "REVIEW",
            "review_required": True,
            "rule": "vendor_trend_deteriorating_medium",
            "reason": (
                f"Vendor risk is MEDIUM and deteriorating ({delta_text} points versus the previous observation); "
                "human review is required."
            ),
        }
    if direction == "DETERIORATING":
        return {
            "status": "OBSERVE",
            "review_required": False,
            "rule": "vendor_trend_deteriorating_low",
            "reason": (
                f"Vendor risk is LOW but deteriorating ({delta_text} points versus the previous observation); "
                "the trend is surfaced for monitoring without changing automatic eligibility."
            ),
        }
    if direction == "IMPROVING":
        return {
            "status": "IMPROVING",
            "review_required": False,
            "rule": "vendor_trend_improving",
            "reason": (
                f"Vendor risk is improving ({delta_text} points versus the previous observation); "
                "this does not override the current risk score or existing policy gates."
            ),
        }
    if direction == "STABLE":
        return {
            "status": "STABLE",
            "review_required": False,
            "rule": "vendor_trend_stable",
            "reason": "Vendor risk is stable within the upstream trend tolerance; no trend gate is applied.",
        }
    return {
        "status": "INSUFFICIENT_HISTORY",
        "review_required": False,
        "rule": "vendor_trend_insufficient_history",
        "reason": "Vendor trend is not used for gating because fewer than two comparable observations are available.",
    }


def apply_vendor_trend(result, trend):
    """Attach trend evidence and, when required, add an explicit review gate.

    The numeric ``score``, component values and weights are never modified.
    """

    updated = deepcopy(result)
    decision = vendor_trend_decision(trend)
    updated["vendor_trend"] = {
        "signal": deepcopy(trend),
        "decision": decision,
        "score_adjustment": 0.0,
    }

    if decision["review_required"]:
        policy = updated.get("policy")
        if not isinstance(policy, dict):
            raise ValueError("supplier result must include policy metadata before trend gating.")
        triggers = list(policy.get("triggers") or [])
        if not any(item.get("rule") == decision["rule"] for item in triggers if isinstance(item, dict)):
            triggers.append(
                {
                    "rule": decision["rule"],
                    "severity": "REVIEW",
                    "value": trend["direction"],
                    "threshold": trend["current_risk"],
                    "reason": decision["reason"],
                }
            )
        policy["triggers"] = triggers
        if policy.get("status") != "BLOCKED":
            policy["status"] = "REVIEW"
        policy["auto_eligible"] = False
        score_rec = updated.get("recommendation")
        policy["final_decision"] = (
            "BLOCKED"
            if policy.get("status") == "BLOCKED"
            else "REVIEW"
            if score_rec in {"PREFERRED", "ACCEPTABLE"}
            else score_rec
        )
        updated["final_decision"] = policy["final_decision"]
        updated["explanation"] = explain_supplier(updated)
    else:
        explanation = updated.get("explanation")
        if isinstance(explanation, dict):
            explanation.setdefault("trend_note", decision["reason"])

    return updated


def score_from_tools_with_trend(
    supplier,
    rfq_json,
    payment_json,
    vendor_risk_json,
    vendor_risk_trend_json,
    *,
    technical_compliance=None,
    category_profile=None,
    profile_file=None,
    score_tolerance=0.05,
):
    """Score existing upstream artifacts and attach a vendor-risk trend gate."""

    result = score_from_tools(
        supplier,
        rfq_json,
        payment_json,
        vendor_risk_json,
        technical_compliance=technical_compliance,
        category_profile=category_profile,
        profile_file=profile_file,
    )
    vendor_payload = load_json(vendor_risk_json)
    trend_payload = load_json(vendor_risk_trend_json)
    current_vendor_risk = extract_vendor_risk(vendor_payload, supplier)
    trend = normalize_vendor_trend(
        trend_payload,
        supplier,
        current_vendor_risk=current_vendor_risk,
        score_tolerance=score_tolerance,
    )
    result = apply_vendor_trend(result, trend)
    result.setdefault("sources", {})["vendor_risk_trend"] = {
        "path": str(Path(vendor_risk_trend_json)),
        "tool": trend["source_meta"]["engine"],
        "version": trend["source_meta"]["engine_version"],
        "model_version": trend["source_meta"]["model_version"],
        "schema_version": trend["source_meta"]["schema_version"],
    }
    return result
