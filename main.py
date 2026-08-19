import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path

VERSION = "0.8"
COMPONENTS = ("quotation", "commercial", "vendor_risk")
DEFAULT_WEIGHTS = {"quotation": 0.50, "commercial": 0.20, "vendor_risk": 0.30}
WEIGHTS = DEFAULT_WEIGHTS
CSV_COLUMNS = ("supplier", "quotation_score", "commercial_risk", "vendor_risk")

DEFAULT_POLICY = {
    "commercial_review_threshold": 80.0,
    "vendor_review_threshold": 75.0,
    "compliance_review_incidents": 1,
    "compliance_block_incidents": 3,
    "minimum_auto_score": 65.0,
}

CATEGORY_PROFILES = {
    "general-procurement": {
        "description": "Balanced default profile for general supplier decisions.",
        "weights": {"quotation": 0.50, "commercial": 0.20, "vendor_risk": 0.30},
        "policy": dict(DEFAULT_POLICY),
    },
    "office-supplies": {
        "description": "Quotation-led profile for lower-complexity, replaceable supply categories.",
        "weights": {"quotation": 0.65, "commercial": 0.20, "vendor_risk": 0.15},
        "policy": {
            "commercial_review_threshold": 90,
            "vendor_review_threshold": 85,
            "compliance_review_incidents": 2,
            "compliance_block_incidents": 4,
            "minimum_auto_score": 65,
        },
    },
    "critical-machining": {
        "description": "Risk-led profile for quality-sensitive machining and engineered components.",
        "weights": {"quotation": 0.30, "commercial": 0.15, "vendor_risk": 0.55},
        "policy": {
            "commercial_review_threshold": 70,
            "vendor_review_threshold": 55,
            "compliance_review_incidents": 1,
            "compliance_block_incidents": 2,
            "minimum_auto_score": 80,
        },
    },
    "single-source": {
        "description": "Conservative profile for dependency-heavy single-source procurement.",
        "weights": {"quotation": 0.30, "commercial": 0.20, "vendor_risk": 0.50},
        "policy": {
            "commercial_review_threshold": 70,
            "vendor_review_threshold": 60,
            "compliance_review_incidents": 1,
            "compliance_block_incidents": 2,
            "minimum_auto_score": 80,
        },
    },
    "high-value-capex": {
        "description": "Approval-focused profile for high-value capital expenditure decisions.",
        "weights": {"quotation": 0.40, "commercial": 0.30, "vendor_risk": 0.30},
        "policy": {
            "commercial_review_threshold": 60,
            "vendor_review_threshold": 65,
            "compliance_review_incidents": 1,
            "compliance_block_incidents": 2,
            "minimum_auto_score": 80,
        },
    },
}

COMPONENT_LABELS = {
    "quotation": "quotation competitiveness",
    "commercial": "commercial/payment risk",
    "vendor_risk": "vendor risk",
}


def validate_score(name, value):
    value = float(value)
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100.")
    return value


def _fmt(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def recommendation(score):
    if score >= 80:
        return "PREFERRED"
    if score >= 65:
        return "ACCEPTABLE"
    if score >= 50:
        return "REVIEW"
    return "HIGH RISK"


def normalize_weights(weights=None):
    weights = DEFAULT_WEIGHTS if weights is None else weights
    if not isinstance(weights, dict):
        raise ValueError("weights must be a JSON object.")
    unknown = sorted(set(weights) - set(COMPONENTS))
    missing = sorted(set(COMPONENTS) - set(weights))
    if unknown:
        raise ValueError("unknown weight field(s): " + ", ".join(unknown))
    if missing:
        raise ValueError("weights are missing component(s): " + ", ".join(missing))
    normalized = {name: float(weights[name]) for name in COMPONENTS}
    for name, value in normalized.items():
        if value < 0:
            raise ValueError(f"{name} weight cannot be negative.")
    total = sum(normalized.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"weights must total 100%; current total is {total * 100:.2f}%.")
    return normalized


def normalize_policy(policy=None, *, base_policy=None):
    active = dict(DEFAULT_POLICY if base_policy is None else base_policy)
    if policy is not None:
        if not isinstance(policy, dict):
            raise ValueError("policy must be a JSON object.")
        unknown = sorted(set(policy) - set(DEFAULT_POLICY))
        if unknown:
            raise ValueError("unknown policy field(s): " + ", ".join(unknown))
        active.update(policy)
    for field, label in (
        ("commercial_review_threshold", "commercial review threshold"),
        ("vendor_review_threshold", "vendor review threshold"),
        ("minimum_auto_score", "minimum auto score"),
    ):
        active[field] = validate_score(label, active[field])
    for field in ("compliance_review_incidents", "compliance_block_incidents"):
        value = active[field]
        if isinstance(value, bool):
            raise ValueError(f"{field} must be a non-negative integer.")
        try:
            integer = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be a non-negative integer.") from exc
        if float(value) != integer or integer < 0:
            raise ValueError(f"{field} must be a non-negative integer.")
        active[field] = integer
    if active["compliance_review_incidents"] > active["compliance_block_incidents"]:
        raise ValueError("compliance_review_incidents cannot exceed compliance_block_incidents.")
    return active


def get_category_profile(name=None):
    name = "general-procurement" if not name else str(name).strip().lower()
    if name not in CATEGORY_PROFILES:
        raise ValueError(
            f"unknown category profile '{name}'. Available profiles: "
            + ", ".join(sorted(CATEGORY_PROFILES))
        )
    raw = deepcopy(CATEGORY_PROFILES[name])
    return {
        "name": name,
        "description": raw["description"],
        "weights": normalize_weights(raw["weights"]),
        "policy": normalize_policy(raw["policy"]),
        "source": {"type": "builtin", "name": name},
    }


def load_profile_file(path):
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("custom profile file must contain a JSON object.")
    allowed = {"name", "description", "weights", "policy"}
    required = {"name", "weights", "policy"}
    unknown = sorted(set(payload) - allowed)
    missing = sorted(required - set(payload))
    if unknown:
        raise ValueError("unknown custom profile field(s): " + ", ".join(unknown))
    if missing:
        raise ValueError("custom profile is missing field(s): " + ", ".join(missing))
    name = str(payload["name"]).strip()
    if not name:
        raise ValueError("custom profile name cannot be empty.")
    policy = payload["policy"]
    if not isinstance(policy, dict):
        raise ValueError("custom profile policy must be a JSON object.")
    missing_policy = sorted(set(DEFAULT_POLICY) - set(policy))
    unknown_policy = sorted(set(policy) - set(DEFAULT_POLICY))
    if missing_policy:
        raise ValueError("custom profile policy is missing field(s): " + ", ".join(missing_policy))
    if unknown_policy:
        raise ValueError("unknown custom profile policy field(s): " + ", ".join(unknown_policy))
    description = str(payload.get("description") or "Custom procurement profile.").strip()
    return {
        "name": name,
        "description": description,
        "weights": normalize_weights(payload["weights"]),
        "policy": normalize_policy(policy),
        "source": {"type": "file", "path": str(path.resolve())},
    }


def resolve_profile(category_profile=None, *, policy=None, weights=None, profile_file=None):
    if profile_file is not None and category_profile:
        raise ValueError("use either category_profile or profile_file, not both.")
    profile = load_profile_file(profile_file) if profile_file is not None else get_category_profile(category_profile)
    return {
        "name": profile["name"],
        "description": profile["description"],
        "weights": normalize_weights(profile["weights"] if weights is None else weights),
        "policy": normalize_policy(policy, base_policy=profile["policy"]),
        "source": profile["source"],
    }


def evaluate_policy(result, *, compliance_incidents=None, policy=None):
    active = normalize_policy(policy)
    commercial = validate_score("commercial risk", result["inputs"]["commercial_risk"])
    vendor = validate_score("vendor risk", result["inputs"]["vendor_risk"])
    triggers = []

    def add(rule, severity, value, threshold, reason):
        triggers.append({
            "rule": rule,
            "severity": severity,
            "value": value,
            "threshold": threshold,
            "reason": reason,
        })

    if commercial >= active["commercial_review_threshold"]:
        add(
            "commercial_exposure",
            "REVIEW",
            commercial,
            active["commercial_review_threshold"],
            f"Commercial/payment risk is {_fmt(commercial)}/100, meeting the review threshold of {_fmt(active['commercial_review_threshold'])}/100.",
        )
    if vendor >= active["vendor_review_threshold"]:
        add(
            "vendor_risk",
            "REVIEW",
            vendor,
            active["vendor_review_threshold"],
            f"Vendor risk is {_fmt(vendor)}/100, meeting the review threshold of {_fmt(active['vendor_review_threshold'])}/100.",
        )
    if compliance_incidents is not None:
        if isinstance(compliance_incidents, bool):
            raise ValueError("compliance incidents must be a non-negative integer.")
        try:
            incidents = int(compliance_incidents)
        except (TypeError, ValueError) as exc:
            raise ValueError("compliance incidents must be a non-negative integer.") from exc
        if float(compliance_incidents) != incidents or incidents < 0:
            raise ValueError("compliance incidents must be a non-negative integer.")
        if incidents >= active["compliance_block_incidents"]:
            add(
                "compliance_incidents",
                "BLOCKED",
                incidents,
                active["compliance_block_incidents"],
                f"Compliance incidents are {incidents}, meeting the block threshold of {active['compliance_block_incidents']}.",
            )
        elif incidents >= active["compliance_review_incidents"]:
            add(
                "compliance_incidents",
                "REVIEW",
                incidents,
                active["compliance_review_incidents"],
                f"Compliance incidents are {incidents}, meeting the review threshold of {active['compliance_review_incidents']}.",
            )

    score_rec = result["recommendation"]
    if score_rec in {"PREFERRED", "ACCEPTABLE"} and float(result["score"]) < active["minimum_auto_score"]:
        add(
            "minimum_auto_score",
            "REVIEW",
            float(result["score"]),
            active["minimum_auto_score"],
            f"Composite score is {result['score']:.2f}/100, below the category automatic-approval threshold of {active['minimum_auto_score']:.2f}/100.",
        )

    status = "BLOCKED" if any(t["severity"] == "BLOCKED" for t in triggers) else "REVIEW" if triggers else "PASS"
    if status == "BLOCKED":
        final = "BLOCKED"
    elif status == "REVIEW" and score_rec in {"PREFERRED", "ACCEPTABLE"}:
        final = "REVIEW"
    else:
        final = score_rec
    auto_eligible = (
        status == "PASS"
        and score_rec in {"PREFERRED", "ACCEPTABLE"}
        and float(result["score"]) >= active["minimum_auto_score"]
    )
    return {
        "status": status,
        "score_recommendation": score_rec,
        "final_decision": final,
        "auto_eligible": auto_eligible,
        "triggers": triggers,
        "rules": active,
    }


def apply_policy(result, *, compliance_incidents=None, policy=None):
    result["policy"] = evaluate_policy(result, compliance_incidents=compliance_incidents, policy=policy)
    result["final_decision"] = result["policy"]["final_decision"]
    result["explanation"] = explain_supplier(result)
    return result


def explain_supplier(result):
    inputs = result["inputs"]
    strengths, warnings = [], []
    if inputs["quotation_score"] >= 85:
        strengths.append(f"Strong quotation competitiveness ({_fmt(inputs['quotation_score'])}/100).")
    elif inputs["quotation_score"] < 60:
        warnings.append(f"Weak quotation competitiveness ({_fmt(inputs['quotation_score'])}/100).")
    if inputs["commercial_risk"] <= 20:
        strengths.append(f"Low commercial/payment exposure ({_fmt(inputs['commercial_risk'])}/100 risk).")
    elif inputs["commercial_risk"] >= 60:
        warnings.append(f"High commercial/payment exposure ({_fmt(inputs['commercial_risk'])}/100 risk).")
    if inputs["vendor_risk"] <= 25:
        strengths.append(f"Low vendor risk ({_fmt(inputs['vendor_risk'])}/100 risk).")
    elif inputs["vendor_risk"] >= 50:
        warnings.append(f"Elevated vendor risk ({_fmt(inputs['vendor_risk'])}/100 risk).")
    for trigger in result.get("policy", {}).get("triggers", []):
        if trigger["reason"] not in warnings:
            warnings.append(trigger["reason"])
    primary = max(result["weighted"], key=result["weighted"].get)
    driver = {
        "component": primary,
        "label": COMPONENT_LABELS[primary],
        "component_score": round(float(result["components"][primary]), 2),
        "weighted_points": round(float(result["weighted"][primary]), 2),
    }
    final = result.get("final_decision", result["recommendation"])
    policy = result.get("policy")
    if policy and policy["status"] in {"REVIEW", "BLOCKED"}:
        reason = policy["triggers"][0]["reason"]
        summary = (
            f"{result['supplier']} scores {result['score']:.2f}/100 ({result['recommendation']} by score) "
            f"but the final decision is {final} because {reason[0].lower() + reason[1:]}"
        )
    elif strengths:
        summary = f"{result['supplier']} is {final} at {result['score']:.2f}/100, supported by {strengths[0].lower()}"
    elif warnings:
        summary = f"{result['supplier']} is {final} at {result['score']:.2f}/100, with {warnings[0].lower()}"
    else:
        summary = f"{result['supplier']} is {final} at {result['score']:.2f}/100 with no extreme component signal."
    return {"summary": summary, "strengths": strengths, "warnings": warnings, "primary_driver": driver}


def _comparison_phrase(component, delta):
    points = f"{abs(float(delta)):.2f} weighted points"
    if component == "quotation":
        return f"stronger quotation score (+{points})" if delta > 0 else f"weaker quotation score (-{points})"
    if component == "commercial":
        return f"lower commercial/payment risk (+{points})" if delta > 0 else f"higher commercial/payment risk (-{points})"
    return f"lower vendor risk (+{points})" if delta > 0 else f"higher vendor risk (-{points})"


def rank_results(results):
    return sorted(results, key=lambda item: (-float(item["score"]), str(item["supplier"]).casefold()))


def explain_portfolio(results):
    ranked = rank_results(results)
    if not ranked:
        raise ValueError("portfolio explanation requires at least one supplier result.")
    winner = ranked[0]
    if len(ranked) == 1:
        return {
            "winner": winner["supplier"],
            "runner_up": None,
            "score_gap": None,
            "advantages": [],
            "tradeoffs": [],
            "summary": f"{winner['supplier']} is the only evaluated supplier at {winner['score']:.2f}/100.",
        }
    runner = ranked[1]
    gap = round(float(winner["score"]) - float(runner["score"]), 2)
    deltas = {
        component: round(float(winner["weighted"][component]) - float(runner["weighted"][component]), 2)
        for component in COMPONENTS
    }
    ordered = sorted(deltas.items(), key=lambda item: abs(item[1]), reverse=True)
    advantages = [
        {"component": c, "weighted_point_delta": d, "reason": _comparison_phrase(c, d)}
        for c, d in ordered if d > 0.05
    ]
    tradeoffs = [
        {"component": c, "weighted_point_delta": d, "reason": _comparison_phrase(c, d)}
        for c, d in ordered if d < -0.05
    ]
    summary = (
        f"{winner['supplier']} ranks first by {gap:.2f} points over {runner['supplier']}, mainly due to {advantages[0]['reason']}."
        if advantages
        else f"{winner['supplier']} ranks first by {gap:.2f} points over {runner['supplier']} through small combined advantages."
    )
    if tradeoffs:
        summary = summary[:-1] + f", despite {tradeoffs[0]['reason']}."
    return {
        "winner": winner["supplier"],
        "runner_up": runner["supplier"],
        "score_gap": gap,
        "advantages": advantages,
        "tradeoffs": tradeoffs,
        "summary": summary,
    }


def score_supplier(
    supplier,
    quotation_score,
    commercial_risk,
    vendor_risk,
    *,
    category_profile=None,
    policy=None,
    weights=None,
    compliance_incidents=None,
    profile_file=None,
):
    supplier = str(supplier).strip()
    if not supplier:
        raise ValueError("supplier name cannot be empty.")
    quotation_score = validate_score("quotation score", quotation_score)
    commercial_risk = validate_score("commercial risk", commercial_risk)
    vendor_risk = validate_score("vendor risk", vendor_risk)
    profile = resolve_profile(category_profile, policy=policy, weights=weights, profile_file=profile_file)
    components = {
        "quotation": quotation_score,
        "commercial": 100.0 - commercial_risk,
        "vendor_risk": 100.0 - vendor_risk,
    }
    weighted = {name: round(components[name] * profile["weights"][name], 2) for name in COMPONENTS}
    total = round(sum(weighted.values()), 2)
    result = {
        "tool": "supplier-scorecard",
        "version": VERSION,
        "supplier": supplier,
        "category_profile": profile["name"],
        "profile": {
            "name": profile["name"],
            "description": profile["description"],
            "source": profile["source"],
        },
        "score": total,
        "recommendation": recommendation(total),
        "components": components,
        "weighted": weighted,
        "weights": profile["weights"],
        "inputs": {
            "quotation_score": quotation_score,
            "commercial_risk": commercial_risk,
            "vendor_risk": vendor_risk,
        },
    }
    return apply_policy(result, compliance_incidents=compliance_incidents, policy=profile["policy"])


def score_csv(path, *, category_profile=None, profile_file=None):
    results = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV file must include a header row.")
        missing = [name for name in CSV_COLUMNS if name not in reader.fieldnames]
        if missing:
            raise ValueError("CSV is missing required column(s): " + ", ".join(missing))
        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            try:
                results.append(
                    score_supplier(
                        row["supplier"],
                        float(row["quotation_score"]),
                        float(row["commercial_risk"]),
                        float(row["vendor_risk"]),
                        category_profile=category_profile,
                        profile_file=profile_file,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"CSV row {row_number}: {exc}") from exc
    if not results:
        raise ValueError("CSV file contains no supplier rows.")
    return rank_results(results)


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _same_supplier(expected, actual):
    return str(expected).strip().casefold() == str(actual).strip().casefold()


def _validate_source_supplier(source, expected, actual):
    if actual is not None and not _same_supplier(expected, actual):
        raise ValueError(f"{source} supplier mismatch: expected '{expected}', found '{actual}'.")


def extract_rfq_score(payload, supplier):
    suppliers = payload.get("suppliers") if isinstance(payload, dict) else None
    if not isinstance(suppliers, list):
        raise ValueError("rfqdiff JSON must include a 'suppliers' list.")
    for item in suppliers:
        if not isinstance(item, dict):
            continue
        name = item.get("name", item.get("supplier"))
        if name is not None and _same_supplier(supplier, name):
            if "score" not in item:
                raise ValueError(f"rfqdiff entry for '{supplier}' is missing 'score'.")
            return validate_score("quotation score", item["score"])
    raise ValueError(f"rfqdiff JSON does not contain supplier '{supplier}'.")


def extract_commercial_risk(payload, supplier):
    if not isinstance(payload, dict):
        raise ValueError("payment-terms-parser JSON must be an object.")
    _validate_source_supplier("payment-terms-parser", supplier, payload.get("supplier"))
    if "commercial_risk" in payload:
        return validate_score("commercial risk", payload["commercial_risk"])
    if "buyer_exposure" in payload:
        return validate_score("commercial risk", payload["buyer_exposure"])
    raise ValueError("payment-terms-parser JSON must include 'commercial_risk' or 'buyer_exposure'.")


def extract_vendor_risk(payload, supplier):
    candidates = payload if isinstance(payload, list) else [payload]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = item.get("vendor", item.get("supplier"))
        if name is not None and not _same_supplier(supplier, name):
            continue
        if "score" in item:
            return validate_score("vendor risk", item["score"])
    raise ValueError(f"vendor-risk JSON does not contain supplier '{supplier}'.")


def extract_compliance_incidents(payload, supplier):
    candidates = payload if isinstance(payload, list) else [payload]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = item.get("vendor", item.get("supplier"))
        if name is not None and not _same_supplier(supplier, name):
            continue
        inputs = item.get("inputs")
        if isinstance(inputs, dict) and "compliance_incidents" in inputs:
            return inputs["compliance_incidents"]
    return None


def score_from_tools(supplier, rfq_json, payment_json, vendor_risk_json, *, category_profile=None, profile_file=None):
    rfq_payload = load_json(rfq_json)
    payment_payload = load_json(payment_json)
    vendor_payload = load_json(vendor_risk_json)
    result = score_supplier(
        supplier,
        extract_rfq_score(rfq_payload, supplier),
        extract_commercial_risk(payment_payload, supplier),
        extract_vendor_risk(vendor_payload, supplier),
        compliance_incidents=extract_compliance_incidents(vendor_payload, supplier),
        category_profile=category_profile,
        profile_file=profile_file,
    )
    result["sources"] = {
        "rfqdiff": {"path": str(rfq_json), "tool": rfq_payload.get("tool"), "version": rfq_payload.get("version")},
        "payment_terms_parser": {"path": str(payment_json), "tool": payment_payload.get("tool"), "version": payment_payload.get("version")},
        "vendor_risk_engine": {
            "path": str(vendor_risk_json),
            "tool": vendor_payload.get("tool", "vendor-risk-engine") if isinstance(vendor_payload, dict) else "vendor-risk-engine",
            "version": vendor_payload.get("version") if isinstance(vendor_payload, dict) else None,
        },
    }
    return result


def print_report(result):
    print(f"\nSUPPLIER SCORECARD v{VERSION}")
    print("-" * 76)
    print(f"Supplier             : {result['supplier']}")
    print(f"Category profile     : {result['category_profile']}")
    print(f"Composite score      : {result['score']:.2f} / 100")
    print(f"Score recommendation : {result['recommendation']}")
    print(f"Policy status        : {result['policy']['status']}")
    print(f"Final decision       : {result['final_decision']}")
    print(f"Auto eligible        : {'YES' if result['policy']['auto_eligible'] else 'NO'}")
    print(f"Decision reason      : {result['explanation']['summary']}")


def print_batch_report(results):
    ranked = rank_results(results)
    print(f"\nSUPPLIER SCORECARD v{VERSION} - PORTFOLIO")
    print("-" * 106)
    print(f"{'#':>3} {'Supplier':27} {'Score':>8} {'Score rec.':>12} {'Policy':>10} {'Final':>12}")
    print("-" * 106)
    for rank, result in enumerate(ranked, start=1):
        print(
            f"{rank:>3} {result['supplier'][:27]:27} {result['score']:8.2f} "
            f"{result['recommendation']:>12} {result['policy']['status']:>10} {result['final_decision']:>12}"
        )
    eligible = [item for item in ranked if item["policy"]["auto_eligible"]]
    print("-" * 106)
    print(f"Category profile      : {ranked[0]['category_profile']}")
    print(f"Auto-eligible supplier: {eligible[0]['supplier'] if eligible else 'none'}")
    print(f"Score leader          : {ranked[0]['supplier']}")
    print(f"Decision reason       : {explain_portfolio(ranked)['summary']}")


def print_profiles():
    print("CATEGORY PROFILES")
    print("-" * 92)
    for name in sorted(CATEGORY_PROFILES):
        profile = get_category_profile(name)
        w, p = profile["weights"], profile["policy"]
        print(
            f"{name:20} q={w['quotation']*100:>4.0f}% c={w['commercial']*100:>4.0f}% "
            f"v={w['vendor_risk']*100:>4.0f}%  min-auto={p['minimum_auto_score']:>5.1f}"
        )
        print(f"  {profile['description']}")


def build_parser():
    parser = argparse.ArgumentParser(description="Explainable, category-aware supplier scorecard.")
    parser.add_argument("supplier", nargs="?")
    parser.add_argument("--quotation-score", type=float)
    parser.add_argument("--commercial-risk", type=float)
    parser.add_argument("--vendor-risk", type=float)
    parser.add_argument("--csv", dest="csv_path")
    parser.add_argument("--rfq-json")
    parser.add_argument("--payment-json")
    parser.add_argument("--vendor-risk-json")
    parser.add_argument("--category-profile")
    parser.add_argument("--profile-file", help="Load a custom procurement profile from JSON.")
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def validate_cli_mode(parser, args):
    if args.list_profiles:
        if args.profile_file:
            parser.error("--list-profiles cannot be combined with --profile-file.")
        return "profiles"
    if args.category_profile and args.profile_file:
        parser.error("use either --category-profile or --profile-file, not both.")
    resolve_profile(args.category_profile, profile_file=args.profile_file)
    pipeline_values = (args.rfq_json, args.payment_json, args.vendor_risk_json)
    pipeline_requested = any(value is not None for value in pipeline_values)
    if args.csv_path:
        if args.supplier or pipeline_requested or any(
            value is not None for value in (args.quotation_score, args.commercial_risk, args.vendor_risk)
        ):
            parser.error("--csv cannot be combined with single-supplier inputs.")
        return "csv"
    if pipeline_requested:
        if not args.supplier:
            parser.error("pipeline mode requires a supplier name.")
        if not all(value is not None for value in pipeline_values):
            parser.error("pipeline mode requires: --rfq-json, --payment-json, --vendor-risk-json")
        if any(value is not None for value in (args.quotation_score, args.commercial_risk, args.vendor_risk)):
            parser.error("pipeline mode cannot be combined with manual score inputs.")
        return "pipeline"
    if not args.supplier:
        parser.error("supplier name is required unless --csv is used.")
    if any(value is None for value in (args.quotation_score, args.commercial_risk, args.vendor_risk)):
        parser.error("single-supplier mode requires: --quotation-score, --commercial-risk, --vendor-risk")
    return "manual"


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        mode = validate_cli_mode(parser, args)
        if mode == "profiles":
            print_profiles()
            return
        if mode == "csv":
            result = score_csv(args.csv_path, category_profile=args.category_profile, profile_file=args.profile_file)
        elif mode == "pipeline":
            result = score_from_tools(
                args.supplier,
                args.rfq_json,
                args.payment_json,
                args.vendor_risk_json,
                category_profile=args.category_profile,
                profile_file=args.profile_file,
            )
        else:
            result = score_supplier(
                args.supplier,
                args.quotation_score,
                args.commercial_risk,
                args.vendor_risk,
                category_profile=args.category_profile,
                profile_file=args.profile_file,
            )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif mode == "csv":
        print_batch_report(result)
    else:
        print_report(result)


if __name__ == "__main__":
    main()
