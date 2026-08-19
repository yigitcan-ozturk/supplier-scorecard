import argparse
import csv
import json
from pathlib import Path

VERSION = "0.5"
WEIGHTS = {"quotation": 0.50, "commercial": 0.20, "vendor_risk": 0.30}
CSV_COLUMNS = ("supplier", "quotation_score", "commercial_risk", "vendor_risk")


COMPONENT_LABELS = {
    "quotation": "quotation competitiveness",
    "commercial": "commercial/payment risk",
    "vendor_risk": "vendor risk",
}


def validate_score(name, value):
    value = float(value)
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100.")
    return value


def recommendation(score):
    if score >= 80:
        return "PREFERRED"
    if score >= 65:
        return "ACCEPTABLE"
    if score >= 50:
        return "REVIEW"
    return "HIGH RISK"


def _format_number(value):
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def explain_supplier(result):
    """Build deterministic, machine-readable reasons for one supplier score."""
    inputs = result["inputs"]
    components = result["components"]
    weighted = result["weighted"]

    strengths = []
    warnings = []

    quotation_score = inputs["quotation_score"]
    commercial_risk = inputs["commercial_risk"]
    vendor_risk = inputs["vendor_risk"]

    if quotation_score >= 85:
        strengths.append(
            f"Strong quotation competitiveness ({_format_number(quotation_score)}/100)."
        )
    elif quotation_score < 60:
        warnings.append(
            f"Weak quotation competitiveness ({_format_number(quotation_score)}/100)."
        )

    if commercial_risk <= 20:
        strengths.append(
            f"Low commercial/payment exposure ({_format_number(commercial_risk)}/100 risk)."
        )
    elif commercial_risk >= 60:
        warnings.append(
            f"High commercial/payment exposure ({_format_number(commercial_risk)}/100 risk)."
        )

    if vendor_risk <= 25:
        strengths.append(
            f"Low vendor risk ({_format_number(vendor_risk)}/100 risk)."
        )
    elif vendor_risk >= 50:
        warnings.append(
            f"Elevated vendor risk ({_format_number(vendor_risk)}/100 risk)."
        )

    primary_component = max(weighted, key=weighted.get)
    primary_driver = {
        "component": primary_component,
        "label": COMPONENT_LABELS[primary_component],
        "component_score": round(float(components[primary_component]), 2),
        "weighted_points": round(float(weighted[primary_component]), 2),
    }

    if strengths and warnings:
        summary = (
            f"{result['supplier']} is {result['recommendation']} at {result['score']:.2f}/100; "
            f"the decision combines {strengths[0].lower()} with {warnings[0].lower()}"
        )
    elif strengths:
        summary = (
            f"{result['supplier']} is {result['recommendation']} at {result['score']:.2f}/100, "
            f"supported by {strengths[0].lower()}"
        )
    elif warnings:
        summary = (
            f"{result['supplier']} is {result['recommendation']} at {result['score']:.2f}/100, "
            f"with {warnings[0].lower()}"
        )
    else:
        summary = (
            f"{result['supplier']} is {result['recommendation']} at {result['score']:.2f}/100 "
            "with no extreme component signal."
        )

    return {
        "summary": summary,
        "strengths": strengths,
        "warnings": warnings,
        "primary_driver": primary_driver,
    }


def _comparison_phrase(component, delta):
    magnitude = abs(float(delta))
    points = f"{magnitude:.2f} weighted points"
    if component == "quotation":
        return (
            f"stronger quotation score (+{points})"
            if delta > 0
            else f"weaker quotation score (-{points})"
        )
    if component == "commercial":
        return (
            f"lower commercial/payment risk (+{points})"
            if delta > 0
            else f"higher commercial/payment risk (-{points})"
        )
    return (
        f"lower vendor risk (+{points})"
        if delta > 0
        else f"higher vendor risk (-{points})"
    )


def explain_portfolio(results):
    """Explain why the top-ranked supplier leads the runner-up."""
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
            "summary": (
                f"{winner['supplier']} is the only evaluated supplier at "
                f"{winner['score']:.2f}/100."
            ),
        }

    runner_up = ranked[1]
    gap = round(float(winner["score"]) - float(runner_up["score"]), 2)
    deltas = {
        component: round(
            float(winner["weighted"][component])
            - float(runner_up["weighted"][component]),
            2,
        )
        for component in WEIGHTS
    }

    advantages = [
        {
            "component": component,
            "weighted_point_delta": delta,
            "reason": _comparison_phrase(component, delta),
        }
        for component, delta in sorted(
            deltas.items(), key=lambda item: abs(item[1]), reverse=True
        )
        if delta > 0.05
    ]
    tradeoffs = [
        {
            "component": component,
            "weighted_point_delta": delta,
            "reason": _comparison_phrase(component, delta),
        }
        for component, delta in sorted(
            deltas.items(), key=lambda item: abs(item[1]), reverse=True
        )
        if delta < -0.05
    ]

    if advantages:
        summary = (
            f"{winner['supplier']} ranks first by {gap:.2f} points over "
            f"{runner_up['supplier']}, mainly due to {advantages[0]['reason']}."
        )
    else:
        summary = (
            f"{winner['supplier']} ranks first by {gap:.2f} points over "
            f"{runner_up['supplier']} through small combined advantages."
        )

    if tradeoffs:
        summary = summary[:-1] + f", despite {tradeoffs[0]['reason']}."

    return {
        "winner": winner["supplier"],
        "runner_up": runner_up["supplier"],
        "score_gap": gap,
        "advantages": advantages,
        "tradeoffs": tradeoffs,
        "summary": summary,
    }


def score_supplier(supplier, quotation_score, commercial_risk, vendor_risk):
    supplier = str(supplier).strip()
    if not supplier:
        raise ValueError("supplier name cannot be empty.")
    quotation_score = validate_score("quotation score", quotation_score)
    commercial_risk = validate_score("commercial risk", commercial_risk)
    vendor_risk = validate_score("vendor risk", vendor_risk)

    components = {
        "quotation": quotation_score,
        "commercial": 100.0 - commercial_risk,
        "vendor_risk": 100.0 - vendor_risk,
    }
    weighted = {
        name: round(components[name] * WEIGHTS[name], 2)
        for name in WEIGHTS
    }
    total = round(sum(weighted.values()), 2)
    result = {
        "tool": "supplier-scorecard",
        "version": VERSION,
        "supplier": supplier,
        "score": total,
        "recommendation": recommendation(total),
        "components": components,
        "weighted": weighted,
        "weights": WEIGHTS,
        "inputs": {
            "quotation_score": quotation_score,
            "commercial_risk": commercial_risk,
            "vendor_risk": vendor_risk,
        },
    }
    result["explanation"] = explain_supplier(result)
    return result


def rank_results(results):
    return sorted(
        results,
        key=lambda item: (-float(item["score"]), str(item["supplier"]).casefold()),
    )


def score_csv(path):
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
        raise ValueError(
            f"{source} supplier mismatch: expected '{expected}', found '{actual}'."
        )


def extract_rfq_score(payload, supplier):
    if not isinstance(payload, dict):
        raise ValueError("rfqdiff JSON must be an object.")
    suppliers = payload.get("suppliers")
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
        value = payload["commercial_risk"]
    elif "buyer_exposure" in payload:
        value = payload["buyer_exposure"]
    else:
        raise ValueError(
            "payment-terms-parser JSON must include 'commercial_risk' or 'buyer_exposure'."
        )
    return validate_score("commercial risk", value)


def extract_vendor_risk(payload, supplier):
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get("vendor", item.get("supplier"))
            if name is not None and _same_supplier(supplier, name):
                if "score" not in item:
                    raise ValueError(
                        f"vendor-risk entry for '{supplier}' is missing 'score'."
                    )
                return validate_score("vendor risk", item["score"])
        raise ValueError(f"vendor-risk JSON does not contain supplier '{supplier}'.")
    if not isinstance(payload, dict):
        raise ValueError("vendor-risk-engine JSON must be an object or list.")
    _validate_source_supplier(
        "vendor-risk-engine",
        supplier,
        payload.get("vendor", payload.get("supplier")),
    )
    if "score" not in payload:
        raise ValueError("vendor-risk-engine JSON must include 'score'.")
    return validate_score("vendor risk", payload["score"])


def score_from_tools(supplier, rfq_json, payment_json, vendor_risk_json):
    rfq_payload = load_json(rfq_json)
    payment_payload = load_json(payment_json)
    vendor_payload = load_json(vendor_risk_json)
    result = score_supplier(
        supplier,
        extract_rfq_score(rfq_payload, supplier),
        extract_commercial_risk(payment_payload, supplier),
        extract_vendor_risk(vendor_payload, supplier),
    )
    result["sources"] = {
        "rfqdiff": {
            "path": str(rfq_json),
            "tool": rfq_payload.get("tool") if isinstance(rfq_payload, dict) else None,
            "version": rfq_payload.get("version") if isinstance(rfq_payload, dict) else None,
        },
        "payment_terms_parser": {
            "path": str(payment_json),
            "tool": payment_payload.get("tool") if isinstance(payment_payload, dict) else None,
            "version": payment_payload.get("version") if isinstance(payment_payload, dict) else None,
        },
        "vendor_risk_engine": {
            "path": str(vendor_risk_json),
            "tool": (
                (vendor_payload.get("tool") or "vendor-risk-engine")
                if isinstance(vendor_payload, dict)
                else "vendor-risk-engine"
            ),
            "version": vendor_payload.get("version") if isinstance(vendor_payload, dict) else None,
        },
    }
    return result


def print_explanation(explanation, indent=""):
    print(f"{indent}Decision reason      : {explanation['summary']}")
    if explanation["strengths"]:
        print(f"{indent}Strengths            :")
        for item in explanation["strengths"]:
            print(f"{indent}  + {item}")
    if explanation["warnings"]:
        print(f"{indent}Warnings             :")
        for item in explanation["warnings"]:
            print(f"{indent}  - {item}")


def print_report(result):
    print()
    print(f"SUPPLIER SCORECARD v{VERSION}")
    print("-" * 72)
    print(f"Supplier             : {result['supplier']}")
    print(f"Composite score      : {result['score']:.2f} / 100")
    print(f"Recommendation       : {result['recommendation']}")
    if "sources" in result:
        print("Pipeline inputs      : connected")
    print()
    print_explanation(result["explanation"])


def print_batch_report(results):
    ranked = rank_results(results)
    portfolio_explanation = explain_portfolio(ranked)
    print()
    print(f"SUPPLIER SCORECARD v{VERSION} - PORTFOLIO")
    print("-" * 82)
    print(f"{'#':>3} {'Supplier':30} {'Score':>8} {'Recommendation':>18}")
    print("-" * 82)
    for rank, result in enumerate(ranked, start=1):
        print(
            f"{rank:>3} {result['supplier'][:30]:30} "
            f"{result['score']:8.2f} {result['recommendation']:>18}"
        )
    print("-" * 82)
    print(f"Recommended supplier : {ranked[0]['supplier']}")
    print(f"Decision reason      : {portfolio_explanation['summary']}")


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Combine quotation, commercial-risk and vendor-risk signals into an "
            "explainable supplier scorecard."
        )
    )
    parser.add_argument("supplier", nargs="?")
    parser.add_argument("--quotation-score", type=float)
    parser.add_argument("--commercial-risk", type=float)
    parser.add_argument("--vendor-risk", type=float)
    parser.add_argument("--csv", dest="csv_path")
    parser.add_argument("--rfq-json")
    parser.add_argument("--payment-json")
    parser.add_argument("--vendor-risk-json")
    parser.add_argument("--json", action="store_true")
    return parser


def validate_cli_mode(parser, args):
    pipeline_values = (args.rfq_json, args.payment_json, args.vendor_risk_json)
    pipeline_requested = any(value is not None for value in pipeline_values)
    if args.csv_path:
        if args.supplier or pipeline_requested or any(
            value is not None
            for value in (
                args.quotation_score,
                args.commercial_risk,
                args.vendor_risk,
            )
        ):
            parser.error("--csv cannot be combined with single-supplier inputs.")
        return "csv"
    if pipeline_requested:
        if not args.supplier:
            parser.error("pipeline mode requires a supplier name.")
        if not all(value is not None for value in pipeline_values):
            parser.error(
                "pipeline mode requires: --rfq-json, --payment-json, --vendor-risk-json"
            )
        if any(
            value is not None
            for value in (
                args.quotation_score,
                args.commercial_risk,
                args.vendor_risk,
            )
        ):
            parser.error("pipeline mode cannot be combined with manual score inputs.")
        return "pipeline"
    if not args.supplier:
        parser.error("supplier name is required unless --csv is used.")
    if any(
        value is None
        for value in (
            args.quotation_score,
            args.commercial_risk,
            args.vendor_risk,
        )
    ):
        parser.error(
            "single-supplier mode requires: --quotation-score, --commercial-risk, --vendor-risk"
        )
    return "manual"


def main():
    parser = build_parser()
    args = parser.parse_args()
    mode = validate_cli_mode(parser, args)
    try:
        if mode == "csv":
            result = score_csv(args.csv_path)
        elif mode == "pipeline":
            result = score_from_tools(
                args.supplier,
                args.rfq_json,
                args.payment_json,
                args.vendor_risk_json,
            )
        else:
            result = score_supplier(
                args.supplier,
                args.quotation_score,
                args.commercial_risk,
                args.vendor_risk,
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
