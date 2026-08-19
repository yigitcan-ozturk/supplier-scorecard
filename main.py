import argparse
import csv
import json


VERSION = "0.1"

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
        "supplier": supplier,
        "score": total,
        "recommendation": recommendation(total),
        "components": components,
        "weighted": weighted,
        "inputs": {
            "quotation_score": float(quotation_score),
            "commercial_risk": float(commercial_risk),
            "vendor_risk": float(vendor_risk),
        },
    }


def rank_results(results):
    return sorted(results, key=lambda item: (-item["score"], item["supplier"].lower()))


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
        help="Supplier name for single-supplier scoring.",
    )
    parser.add_argument(
        "--quotation-score",
        type=float,
        help="Quotation/commercial comparison score (0-100, higher is better).",
    )
    parser.add_argument(
        "--commercial-risk",
        type=float,
        help="Payment/commercial risk score (0-100, higher is riskier).",
    )
    parser.add_argument(
        "--vendor-risk",
        type=float,
        help="Vendor risk score (0-100, higher is riskier).",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Score and rank a supplier portfolio from CSV.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Return structured JSON instead of text output.",
    )

    return parser


def validate_cli_mode(parser, args):
    if args.csv_path and args.supplier:
        parser.error("use either a supplier name or --csv, not both.")

    if args.csv_path:
        return

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


def main():
    parser = build_parser()
    args = parser.parse_args()
    validate_cli_mode(parser, args)

    try:
        if args.csv_path:
            results = score_csv(args.csv_path)
            if args.json:
                print_json(results)
            else:
                print_batch_report(results)
            return

        result = score_supplier(
            supplier=args.supplier,
            quotation_score=args.quotation_score,
            commercial_risk=args.commercial_risk,
            vendor_risk=args.vendor_risk,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    if args.json:
        print_json(result)
    else:
        print_report(result)


if __name__ == "__main__":
    main()
