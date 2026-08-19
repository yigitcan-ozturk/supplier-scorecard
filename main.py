import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path

VERSION = "1.0"
COMPONENTS = ("quotation", "commercial", "vendor_risk", "technical")
LEGACY_COMPONENTS = COMPONENTS[:3]
DEFAULT_WEIGHTS = {"quotation": 0.40, "commercial": 0.16, "vendor_risk": 0.24, "technical": 0.20}
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
        "weights": {"quotation": .40, "commercial": .16, "vendor_risk": .24, "technical": .20},
        "policy": dict(DEFAULT_POLICY),
    },
    "office-supplies": {
        "description": "Quotation-led profile for lower-complexity, replaceable supply categories.",
        "weights": {"quotation": .585, "commercial": .18, "vendor_risk": .135, "technical": .10},
        "policy": {"commercial_review_threshold": 90, "vendor_review_threshold": 85, "compliance_review_incidents": 2, "compliance_block_incidents": 4, "minimum_auto_score": 65},
    },
    "critical-machining": {
        "description": "Risk-led profile for quality-sensitive machining and engineered components.",
        "weights": {"quotation": .21, "commercial": .105, "vendor_risk": .385, "technical": .30},
        "policy": {"commercial_review_threshold": 70, "vendor_review_threshold": 55, "compliance_review_incidents": 1, "compliance_block_incidents": 2, "minimum_auto_score": 80},
    },
    "single-source": {
        "description": "Conservative profile for dependency-heavy single-source procurement.",
        "weights": {"quotation": .24, "commercial": .16, "vendor_risk": .40, "technical": .20},
        "policy": {"commercial_review_threshold": 70, "vendor_review_threshold": 60, "compliance_review_incidents": 1, "compliance_block_incidents": 2, "minimum_auto_score": 80},
    },
    "high-value-capex": {
        "description": "Approval-focused profile for high-value capital expenditure decisions.",
        "weights": {"quotation": .34, "commercial": .255, "vendor_risk": .255, "technical": .15},
        "policy": {"commercial_review_threshold": 60, "vendor_review_threshold": 65, "compliance_review_incidents": 1, "compliance_block_incidents": 2, "minimum_auto_score": 80},
    },
}
COMPONENT_LABELS = {
    "quotation": "quotation competitiveness",
    "commercial": "commercial/payment risk",
    "vendor_risk": "vendor risk",
    "technical": "technical compliance",
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
    raw = DEFAULT_WEIGHTS if weights is None else weights
    if not isinstance(raw, dict):
        raise ValueError("weights must be a JSON object.")
    unknown = sorted(set(raw) - set(COMPONENTS))
    if unknown:
        raise ValueError("unknown weight field(s): " + ", ".join(unknown))
    if set(raw) == set(LEGACY_COMPONENTS):
        result = {name: float(raw[name]) for name in LEGACY_COMPONENTS}
        result["technical"] = 0.0
    else:
        missing = sorted(set(COMPONENTS) - set(raw))
        if missing:
            raise ValueError("weights are missing component(s): " + ", ".join(missing))
        result = {name: float(raw[name]) for name in COMPONENTS}
    if any(value < 0 for value in result.values()):
        raise ValueError("weights cannot be negative.")
    total = sum(result.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"weights must total 100%; current total is {total * 100:.2f}%.")
    return result


def effective_weights(profile_weights, technical_compliance=None):
    defined = normalize_weights(profile_weights)
    if technical_compliance is not None or defined["technical"] == 0:
        return defined
    total = sum(defined[name] for name in LEGACY_COMPONENTS)
    if total <= 0:
        raise ValueError("profile must weight at least one non-technical component.")
    active = {name: defined[name] / total for name in LEGACY_COMPONENTS}
    active["technical"] = 0.0
    return active


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
        raise ValueError(f"unknown category profile '{name}'. Available profiles: " + ", ".join(sorted(CATEGORY_PROFILES)))
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
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("custom profile file must contain a JSON object.")
    allowed, required = {"name", "description", "weights", "policy"}, {"name", "weights", "policy"}
    unknown, missing = sorted(set(payload) - allowed), sorted(required - set(payload))
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
    return {
        "name": name,
        "description": str(payload.get("description") or "Custom procurement profile.").strip(),
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
        triggers.append({"rule": rule, "severity": severity, "value": value, "threshold": threshold, "reason": reason})

    if commercial >= active["commercial_review_threshold"]:
        add("commercial_exposure", "REVIEW", commercial, active["commercial_review_threshold"], f"Commercial/payment risk is {_fmt(commercial)}/100, meeting the review threshold of {_fmt(active['commercial_review_threshold'])}/100.")
    if vendor >= active["vendor_review_threshold"]:
        add("vendor_risk", "REVIEW", vendor, active["vendor_review_threshold"], f"Vendor risk is {_fmt(vendor)}/100, meeting the review threshold of {_fmt(active['vendor_review_threshold'])}/100.")
    if compliance_incidents is not None:
        incidents = int(compliance_incidents)
        if float(compliance_incidents) != incidents or incidents < 0:
            raise ValueError("compliance incidents must be a non-negative integer.")
        if incidents >= active["compliance_block_incidents"]:
            add("compliance_incidents", "BLOCKED", incidents, active["compliance_block_incidents"], f"Compliance incidents are {incidents}, meeting the block threshold of {active['compliance_block_incidents']}.")
        elif incidents >= active["compliance_review_incidents"]:
            add("compliance_incidents", "REVIEW", incidents, active["compliance_review_incidents"], f"Compliance incidents are {incidents}, meeting the review threshold of {active['compliance_review_incidents']}.")
    if result["score"] < active["minimum_auto_score"]:
        add("minimum_auto_score", "REVIEW", result["score"], active["minimum_auto_score"], f"Composite score is {result['score']:.2f}/100, below the automatic-approval threshold of {_fmt(active['minimum_auto_score'])}/100.")

    status = "BLOCKED" if any(t["severity"] == "BLOCKED" for t in triggers) else "REVIEW" if triggers else "PASS"
    score_rec = result["recommendation"]
    final = "BLOCKED" if status == "BLOCKED" else "REVIEW" if status == "REVIEW" and score_rec in {"PREFERRED", "ACCEPTABLE"} else score_rec
    return {
        "status": status,
        "score_recommendation": score_rec,
        "final_decision": final,
        "auto_eligible": status == "PASS" and score_rec in {"PREFERRED", "ACCEPTABLE"},
        "triggers": triggers,
        "rules": active,
    }


def apply_policy(result, *, compliance_incidents=None, policy=None):
    result["policy"] = evaluate_policy(result, compliance_incidents=compliance_incidents, policy=policy)
    result["final_decision"] = result["policy"]["final_decision"]
    result["explanation"] = explain_supplier(result)
    return result


def explain_supplier(result):
    inputs, weighted = result["inputs"], result["weighted"]
    strengths, warnings = [], []
    q, c, v, t = inputs["quotation_score"], inputs["commercial_risk"], inputs["vendor_risk"], inputs.get("technical_compliance")
    if q >= 85:
        strengths.append(f"Strong quotation competitiveness ({_fmt(q)}/100).")
    elif q < 60:
        warnings.append(f"Weak quotation competitiveness ({_fmt(q)}/100).")
    if c <= 20:
        strengths.append(f"Low commercial/payment exposure ({_fmt(c)}/100 risk).")
    elif c >= 60:
        warnings.append(f"High commercial/payment exposure ({_fmt(c)}/100 risk).")
    if v <= 25:
        strengths.append(f"Low vendor risk ({_fmt(v)}/100 risk).")
    elif v >= 50:
        warnings.append(f"Elevated vendor risk ({_fmt(v)}/100 risk).")
    if t is not None:
        if t >= 85:
            strengths.append(f"Strong technical compliance ({_fmt(t)}/100).")
        elif t < 70:
            warnings.append(f"Weak technical compliance ({_fmt(t)}/100).")
    policy = result.get("policy")
    if policy:
        warnings.extend(trigger["reason"] for trigger in policy["triggers"] if trigger["reason"] not in warnings)
    primary = max(weighted, key=weighted.get)
    final = result.get("final_decision", result["recommendation"])
    if policy and policy["triggers"]:
        summary = f"{result['supplier']} scores {result['score']:.2f}/100 ({result['recommendation']} by score) but the final decision is {final} because {policy['triggers'][0]['reason'][0].lower() + policy['triggers'][0]['reason'][1:]}"
    elif strengths:
        summary = f"{result['supplier']} is {final} at {result['score']:.2f}/100, supported by {strengths[0].lower()}"
    elif warnings:
        summary = f"{result['supplier']} is {final} at {result['score']:.2f}/100, with {warnings[0].lower()}"
    else:
        summary = f"{result['supplier']} is {final} at {result['score']:.2f}/100 with no extreme component signal."
    return {
        "summary": summary,
        "strengths": strengths,
        "warnings": warnings,
        "primary_driver": {"component": primary, "label": COMPONENT_LABELS[primary], "weighted_points": round(weighted[primary], 2)},
    }


def rank_results(results):
    return sorted(results, key=lambda item: (-float(item["score"]), str(item["supplier"]).casefold()))


def _comparison_phrase(component, delta):
    points = f"{abs(delta):.2f} weighted points"
    if component == "quotation":
        return f"{'stronger' if delta > 0 else 'weaker'} quotation score ({'+' if delta > 0 else '-'}{points})"
    if component == "commercial":
        return f"{'lower' if delta > 0 else 'higher'} commercial/payment risk ({'+' if delta > 0 else '-'}{points})"
    if component == "vendor_risk":
        return f"{'lower' if delta > 0 else 'higher'} vendor risk ({'+' if delta > 0 else '-'}{points})"
    return f"{'stronger' if delta > 0 else 'weaker'} technical compliance ({'+' if delta > 0 else '-'}{points})"


def explain_portfolio(results):
    ranked = rank_results(results)
    if not ranked:
        raise ValueError("portfolio explanation requires at least one supplier result.")
    winner = ranked[0]
    if len(ranked) == 1:
        return {"winner": winner["supplier"], "runner_up": None, "score_gap": None, "advantages": [], "tradeoffs": [], "summary": f"{winner['supplier']} is the only evaluated supplier at {winner['score']:.2f}/100."}
    runner = ranked[1]
    gap = round(winner["score"] - runner["score"], 2)
    components = [name for name in COMPONENTS if name in winner["weighted"] and name in runner["weighted"]]
    deltas = {name: round(winner["weighted"][name] - runner["weighted"][name], 2) for name in components}
    ordered = sorted(deltas.items(), key=lambda item: abs(item[1]), reverse=True)
    advantages = [{"component": c, "weighted_point_delta": d, "reason": _comparison_phrase(c, d)} for c, d in ordered if d > .05]
    tradeoffs = [{"component": c, "weighted_point_delta": d, "reason": _comparison_phrase(c, d)} for c, d in ordered if d < -.05]
    summary = f"{winner['supplier']} ranks first by {gap:.2f} points over {runner['supplier']}"
    summary += f", mainly due to {advantages[0]['reason']}" if advantages else " through small combined advantages"
    summary += f", despite {tradeoffs[0]['reason']}" if tradeoffs else ""
    return {"winner": winner["supplier"], "runner_up": runner["supplier"], "score_gap": gap, "advantages": advantages, "tradeoffs": tradeoffs, "summary": summary + "."}


def score_supplier(supplier, quotation_score, commercial_risk, vendor_risk, *, technical_compliance=None, compliance_incidents=None, category_profile=None, policy=None, weights=None, profile_file=None):
    supplier = str(supplier).strip()
    if not supplier:
        raise ValueError("supplier name cannot be empty.")
    q = validate_score("quotation score", quotation_score)
    c = validate_score("commercial risk", commercial_risk)
    v = validate_score("vendor risk", vendor_risk)
    t = None if technical_compliance is None else validate_score("technical compliance", technical_compliance)
    profile = resolve_profile(category_profile, policy=policy, weights=weights, profile_file=profile_file)
    active_weights = effective_weights(profile["weights"], t)
    components = {"quotation": q, "commercial": 100 - c, "vendor_risk": 100 - v, "technical": 0.0 if t is None else t}
    weighted = {name: round(components[name] * active_weights[name], 2) for name in COMPONENTS}
    total = round(sum(weighted.values()), 2)
    result = {
        "tool": "supplier-scorecard", "version": VERSION, "supplier": supplier,
        "category_profile": profile["name"], "profile": profile,
        "scoring_mode": "legacy-3-component" if t is None else "4-component",
        "score": total, "recommendation": recommendation(total), "components": components,
        "weighted": weighted, "weights": active_weights,
        "inputs": {"quotation_score": q, "commercial_risk": c, "vendor_risk": v, "technical_compliance": t},
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
            technical = (row.get("technical_compliance") or "").strip()
            try:
                results.append(score_supplier(row["supplier"], float(row["quotation_score"]), float(row["commercial_risk"]), float(row["vendor_risk"]), technical_compliance=float(technical) if technical else None, category_profile=category_profile, profile_file=profile_file))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"CSV row {row_number}: {exc}") from exc
    if not results:
        raise ValueError("CSV file contains no supplier rows.")
    return rank_results(results)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _same_supplier(expected, actual):
    return str(expected).strip().casefold() == str(actual).strip().casefold()


def extract_rfq_score(payload, supplier):
    suppliers = payload.get("suppliers") if isinstance(payload, dict) else None
    if not isinstance(suppliers, list):
        raise ValueError("rfqdiff JSON must include a 'suppliers' list.")
    for item in suppliers:
        if isinstance(item, dict) and _same_supplier(supplier, item.get("name", item.get("supplier"))):
            return validate_score("quotation score", item["score"])
    raise ValueError(f"rfqdiff JSON does not contain supplier '{supplier}'.")


def extract_commercial_risk(payload, supplier):
    if not isinstance(payload, dict):
        raise ValueError("payment-terms-parser JSON must be an object.")
    actual = payload.get("supplier")
    if actual is not None and not _same_supplier(supplier, actual):
        raise ValueError(f"payment-terms-parser supplier mismatch: expected '{supplier}', found '{actual}'.")
    if "commercial_risk" in payload:
        return validate_score("commercial risk", payload["commercial_risk"])
    if "buyer_exposure" in payload:
        return validate_score("commercial risk", payload["buyer_exposure"])
    raise ValueError("payment-terms-parser JSON must include 'commercial_risk' or 'buyer_exposure'.")


def extract_vendor_risk(payload, supplier):
    for item in payload if isinstance(payload, list) else [payload]:
        if not isinstance(item, dict):
            continue
        name = item.get("vendor", item.get("supplier"))
        if name is not None and not _same_supplier(supplier, name):
            continue
        if "score" in item:
            return validate_score("vendor risk", item["score"])
    raise ValueError(f"vendor-risk JSON does not contain supplier '{supplier}'.")


def extract_compliance_incidents(payload, supplier):
    for item in payload if isinstance(payload, list) else [payload]:
        if not isinstance(item, dict):
            continue
        name = item.get("vendor", item.get("supplier"))
        if name is not None and not _same_supplier(supplier, name):
            continue
        inputs = item.get("inputs")
        if isinstance(inputs, dict) and "compliance_incidents" in inputs:
            return inputs["compliance_incidents"]
    return None


def score_from_tools(supplier, rfq_json, payment_json, vendor_risk_json, *, technical_compliance=None, category_profile=None, profile_file=None):
    rfq, payment, vendor = load_json(rfq_json), load_json(payment_json), load_json(vendor_risk_json)
    result = score_supplier(
        supplier, extract_rfq_score(rfq, supplier), extract_commercial_risk(payment, supplier), extract_vendor_risk(vendor, supplier),
        technical_compliance=technical_compliance, compliance_incidents=extract_compliance_incidents(vendor, supplier),
        category_profile=category_profile, profile_file=profile_file,
    )
    result["sources"] = {
        "rfqdiff": {"path": str(rfq_json), "tool": rfq.get("tool"), "version": rfq.get("version")},
        "payment_terms_parser": {"path": str(payment_json), "tool": payment.get("tool"), "version": payment.get("version")},
        "vendor_risk_engine": {"path": str(vendor_risk_json), "tool": vendor.get("tool", "vendor-risk-engine") if isinstance(vendor, dict) else "vendor-risk-engine", "version": vendor.get("version") if isinstance(vendor, dict) else None},
    }
    return result


def print_report(result):
    print(f"\nSUPPLIER SCORECARD v{VERSION}\n" + "-" * 76)
    print(f"Supplier             : {result['supplier']}")
    print(f"Category profile     : {result['category_profile']}")
    print(f"Scoring mode         : {result['scoring_mode']}")
    if result["inputs"]["technical_compliance"] is not None:
        print(f"Technical compliance : {result['inputs']['technical_compliance']:.2f} / 100")
    print(f"Composite score      : {result['score']:.2f} / 100")
    print(f"Score recommendation : {result['recommendation']}")
    print(f"Policy status        : {result['policy']['status']}")
    print(f"Final decision       : {result['final_decision']}")
    print(f"Auto eligible        : {'YES' if result['policy']['auto_eligible'] else 'NO'}")
    print(f"Decision reason      : {result['explanation']['summary']}")


def print_batch_report(results):
    ranked = rank_results(results)
    print(f"\nSUPPLIER SCORECARD v{VERSION} - PORTFOLIO\n" + "-" * 100)
    print(f"{'#':>3} {'Supplier':27} {'Score':>8} {'Score rec.':>12} {'Policy':>10} {'Final':>12}")
    for rank, result in enumerate(ranked, 1):
        print(f"{rank:>3} {result['supplier'][:27]:27} {result['score']:8.2f} {result['recommendation']:>12} {result['policy']['status']:>10} {result['final_decision']:>12}")
    eligible = [item for item in ranked if item["policy"]["auto_eligible"]]
    print(f"Auto-eligible supplier: {eligible[0]['supplier'] if eligible else 'none'}")
    print(f"Score leader          : {ranked[0]['supplier']}")
    print(f"Decision reason       : {explain_portfolio(ranked)['summary']}")


def print_profiles():
    print("CATEGORY PROFILES")
    for name in sorted(CATEGORY_PROFILES):
        profile = get_category_profile(name)
        w, p = profile["weights"], profile["policy"]
        print(f"{name:20} q={w['quotation']*100:5.1f}% c={w['commercial']*100:5.1f}% v={w['vendor_risk']*100:5.1f}% t={w['technical']*100:5.1f}% min-auto={p['minimum_auto_score']:5.1f}")


def build_parser():
    parser = argparse.ArgumentParser(description="Explainable, category-aware supplier scorecard.")
    parser.add_argument("supplier", nargs="?")
    parser.add_argument("--quotation-score", type=float)
    parser.add_argument("--commercial-risk", type=float)
    parser.add_argument("--vendor-risk", type=float)
    parser.add_argument("--technical-compliance", type=float)
    parser.add_argument("--csv", dest="csv_path")
    parser.add_argument("--rfq-json")
    parser.add_argument("--payment-json")
    parser.add_argument("--vendor-risk-json")
    parser.add_argument("--category-profile")
    parser.add_argument("--profile-file")
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def validate_cli_mode(parser, args):
    if args.list_profiles:
        return "profiles"
    if args.category_profile and args.profile_file:
        parser.error("use either --category-profile or --profile-file, not both.")
    resolve_profile(args.category_profile, profile_file=args.profile_file)
    connected = any((args.rfq_json, args.payment_json, args.vendor_risk_json))
    if args.csv_path:
        if args.supplier or connected:
            parser.error("--csv cannot be combined with single-supplier inputs.")
        return "csv"
    if connected:
        if not args.supplier or not all((args.rfq_json, args.payment_json, args.vendor_risk_json)):
            parser.error("connected mode requires supplier, --rfq-json, --payment-json and --vendor-risk-json")
        return "pipeline"
    if not args.supplier or any(value is None for value in (args.quotation_score, args.commercial_risk, args.vendor_risk)):
        parser.error("single-supplier mode requires supplier, --quotation-score, --commercial-risk and --vendor-risk")
    return "manual"


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        mode = validate_cli_mode(parser, args)
        if mode == "profiles":
            print_profiles(); return
        if mode == "csv":
            result = score_csv(args.csv_path, category_profile=args.category_profile, profile_file=args.profile_file)
        elif mode == "pipeline":
            result = score_from_tools(args.supplier, args.rfq_json, args.payment_json, args.vendor_risk_json, technical_compliance=args.technical_compliance, category_profile=args.category_profile, profile_file=args.profile_file)
        else:
            result = score_supplier(args.supplier, args.quotation_score, args.commercial_risk, args.vendor_risk, technical_compliance=args.technical_compliance, category_profile=args.category_profile, profile_file=args.profile_file)
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
