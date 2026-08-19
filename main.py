import argparse
import csv
import json
from pathlib import Path


VERSION = "0.3"

WEIGHTS = {
    "quotation": 0.50,
    "commercial": 0.20,
    "vendor_risk": 0.30,
}

CSV_COLUMNS = (
    "supplier",
    "quotation_score",
    "commercial_risk",
    "vendor_risk",
)


def validate_score(name, value):
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100.")


def recommendation(score):
    if score >= 80:
        return "PREFERRED"
    if score >= 65:
        return "ACCEPTABLE"
    if score >= 50:
        return "REVIEW"
    return "HIGH RISK"


def score_supplier(supplier, quotation_score, commercial_risk, vendor_risk):
    supplier = str(supplier).strip()
    if not supplier:
        raise ValueError("supplier name cannot be empty.")

    validate_score("quotation score", quotation_score)
    validate_score("commercial risk", commercial_risk)
    validate_score("vendor risk", vendor_risk)

    commercial_score = 100.0 - commercial_risk
    vendor_score = 100.0 - vendor_risk

    components = {
        "quotation": float(quotation_score),
        "commercial": commercial_score,
        "vendor_risk": vendor_score,
    }

    weighted = {
        name: round(components[name] * WEIGHTS[name], 2)
        for name in WEIGHTS
    }

    total = round(sum(weighted.values()), 2)

    return {
        "tool": "supplier-scorecard",
        "version": VERSION,
        "supplier": supplier,
        "score": total,
        "recommendation": recommendation(total),
        "components": components,
        "weighted": weighted,
        "weights": WEIGHTS,
        "inputs": {
            "quotation_score": float(quotation_score),
            "commercial_risk": float(commercial_risk),
            "vendor_risk": float(vendor_risk),
        },
    }


def rank_results(results):
    return sorted(
        results,
        key=lambda item: (-item["score"], item["supplier"].lower()),
    )


def score_csv(path):
    results = []

    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError("CSV file must include a header row.")

        missing = [name for name in CSV_COLUMNS if name not in reader.fieldnames]
        if missing:
            raise ValueError(
                "CSV is missing required column(s): " + ", ".join(missing)
            )

        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue

            try:
                result = score_supplier(
                    supplier=row["supplier"],
                    quotation_score=float(row["quotation_score"]),
                    commercial_risk=float(row["commercial_risk"]),
                    vendor_risk=float(row["vendor_risk"]),
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"CSV row {row_number}: {exc}") from exc

            results.append(result)

    if not results:
        raise ValueError("CSV file contains no supplier rows.")

    return rank_results(results)


def load_json(path):
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _same_supplier(expected, actual):
    return str(expected).strip().casefold() == str(actual).strip().casefold()


def _validate_source_supplier(source, expected, actual):
    if actual is None:
        return

    if not _same_supplier(expected, actual):
        raise ValueError(
            f"{source} supplier mismatch: expected '{expected}', "
            f"found '{actual}'."
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
                raise ValueError(
                    f"rfqdiff entry for '{supplier}' is missing 'score'."
                )
            score = float(item["score"])
            validate_score("quotation score", score)
            return score

    raise ValueError(f"rfqdiff JSON does not contain supplier '{supplier}'.")


def extract_commercial_risk(payload, supplier):
    if not isinstance(payload, dict):
        raise ValueError("payment-terms-parser JSON must be an object.")

    _validate_source_supplier(
        "payment-terms-parser",
        supplier,
        payload.get("supplier"),
    )

    if "commercial_risk" in payload:
        value = float(payload["commercial_risk"])
    elif "buyer_exposure" in payload:
        value = float(payload["buyer_exposure"])
    else:
        raise ValueError(
            "payment-terms-parser JSON must include "
            "'commercial_risk' or 'buyer_exposure'."
        )

    validate_score("commercial risk", value)
    return value


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
                value = float(item["score"])
                validate_score("vendor risk", value)
                return value

        raise ValueError(
            f"vendor-risk JSON does not contain supplier '{supplier}'."
        )

    if not isinstance(payload, dict):
        raise ValueError(
            "vendor-risk-engine JSON must be an object or list."
        )

    _validate_source_supplier(
        "vendor-risk-engine",
        supplier,
        payload.get("vendor", payload.get("supplier")),
    )

    if "score" not in payload:
        raise ValueError("vendor-risk-engine JSON must include 'score'.")

    value = float(payload["score"])
    validate_score("vendor risk", value)
    return value


def score_from_tools(
    supplier,
    rfq_json,
    payment_json,
    vendor_risk_json,
):
    rfq_payload = load_json(rfq_json)
    payment_payload = load_json(payment_json)
    vendor_payload = load_json(vendor_risk_json)

    quotation_score = extract_rfq_score(rfq_payload, supplier)
    commercial_risk = extract_commercial_risk(payment_payload, supplier)
    vendor_risk = extract_vendor_risk(vendor_payload, supplier)

    result = score_supplier(
        supplier=supplier,
        quotation_score=quotation_score,
        commercial_risk=commercial_risk,
        vendor_risk=vendor_risk,
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


def print_report(result):
    print()
    print(f"SUPPLIER SCORECARD v{VERSION}")
    print("-" * 54)
    print(f"Supplier             : {result['supplier']}")
    print(f"Composite score      : {result['score']:.2f} / 100")
    print(f"Recommendation       : {result['recommendation']}")
    print()
    print("Score breakdown")
    print("-" * 54)

    labels = {
        "quotation": "Quotation score",
        "commercial": "Commercial score",
        "vendor_risk": "Vendor-risk score",
    }

    for name in WEIGHTS:
        component = result["components"][name]
        weighted = result["weighted"][name]
        weight_percent = int(WEIGHTS[name] * 100)
        print(
            f"{labels[name]:19}: {component:6.2f} / 100 "
            f"x {weight_percent:>2}% = {weighted:6.2f}"
        )

    if "sources" in result:
        print()
        print("Pipeline inputs")
        print("-" * 54)
        print("rfqdiff             : connected")
        print("payment-terms-parser: connected")
        print("vendor-risk-engine  : connected")


def print_batch_report(results):
    print()
    print(f"SUPPLIER SCORECARD v{VERSION} - PORTFOLIO")
    print("-" * 82)
    print(f"{'#':>3} {'Supplier':30} {'Score':>8} {'Recommendation':>18}")
    print("-" * 82)

    for rank, result in enumerate(results, start=1):
        print(
            f"{rank:>3} {result['supplier'][:30]:30} "
            f"{result['score']:8.2f} "
            f"{result['recommendation']:>18}"
        )

    print("-" * 82)
    print(f"Suppliers scored     : {len(results)}")
    print(f"Recommended supplier : {results[0]['supplier']}")


def print_json(payload):
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Combine quotation, commercial-risk and vendor-risk signals "
            "into a transparent composite supplier scorecard."
        )
    )

    parser.add_argument(
        "supplier",
        nargs="?",
        help="Supplier name for single-supplier or pipeline scoring.",
    )
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
    pipeline_values = {
        "--rfq-json": args.rfq_json,
        "--payment-json": args.payment_json,
        "--vendor-risk-json": args.vendor_risk_json,
    }
    pipeline_requested = any(value is not None for value in pipeline_values.values())

    if args.csv_path and (args.supplier or pipeline_requested):
        parser.error("--csv cannot be combined with a supplier name or pipeline JSON.")

    if args.csv_path:
        if any(
            value is not None
            for value in (args.quotation_score, args.commercial_risk, args.vendor_risk)
        ):
            parser.error("--csv cannot be combined with manual score inputs.")
        return "csv"

    if pipeline_requested:
        if not args.supplier:
            parser.error("pipeline mode requires a supplier name.")

        missing = [flag for flag, value in pipeline_values.items() if value is None]
        if missing:
            parser.error("pipeline mode requires: " + ", ".join(missing))

        if any(
            value is not None
            for value in (args.quotation_score, args.commercial_risk, args.vendor_risk)
        ):
            parser.error("pipeline mode cannot be combined with manual score inputs.")

        return "pipeline"

    if not args.supplier:
        parser.error("supplier name is required unless --csv is used.")

    required = {
        "--quotation-score": args.quotation_score,
        "--commercial-risk": args.commercial_risk,
        "--vendor-risk": args.vendor_risk,
    }

    missing = [flag for flag, value in required.items() if value is None]
    if missing:
        parser.error("single-supplier mode requires: " + ", ".join(missing))

    return "manual"


def main():
    parser = build_parser()
    args = parser.parse_args()
    mode = validate_cli_mode(parser, args)

    try:
        if mode == "csv":
            results = score_csv(args.csv_path)
            if args.json:
                print_json(results)
            else:
                print_batch_report(results)
            return

        if mode == "pipeline":
            result = score_from_tools(
                supplier=args.supplier,
                rfq_json=args.rfq_json,
                payment_json=args.payment_json,
                vendor_risk_json=args.vendor_risk_json,
            )
        else:
            result = score_supplier(
                supplier=args.supplier,
                quotation_score=args.quotation_score,
                commercial_risk=args.commercial_risk,
                vendor_risk=args.vendor_risk,
            )

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    if args.json:
        print_json(result)
    else:
        print_report(result)


if __name__ == "__main__":
    main()
