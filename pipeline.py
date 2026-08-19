import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PIPELINE_VERSION = "0.1"
REQUIRED_TOOLS = (
    "currency-normalizer",
    "rfqdiff",
    "payment-terms-parser",
    "vendor-risk-engine",
)
QUOTE_FIELDS = (
    "name",
    "currency",
    "price",
    "lead_time_weeks",
    "payment_days",
)
VENDOR_FIELDS = (
    "on_time_delivery",
    "defect_rate",
    "compliance_incidents",
    "dependency_share",
)


def load_input(path):
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_input(payload)
    return payload


def validate_input(payload):
    if not isinstance(payload, dict):
        raise ValueError("pipeline input must be a JSON object.")

    required = ("supplier", "target_currency", "quotes", "payment_terms", "vendor_risk")
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError("pipeline input is missing: " + ", ".join(missing))

    supplier = str(payload["supplier"]).strip()
    if not supplier:
        raise ValueError("supplier cannot be empty.")

    target_currency = str(payload["target_currency"]).strip().upper()
    if len(target_currency) != 3:
        raise ValueError("target_currency must be a 3-letter currency code.")

    quotes = payload["quotes"]
    if not isinstance(quotes, list) or len(quotes) < 2:
        raise ValueError("quotes must contain at least two supplier quotations.")

    supplier_found = False
    for index, quote in enumerate(quotes, start=1):
        if not isinstance(quote, dict):
            raise ValueError(f"quote {index} must be a JSON object.")
        missing_quote = [name for name in QUOTE_FIELDS if name not in quote]
        if missing_quote:
            raise ValueError(
                f"quote {index} is missing: " + ", ".join(missing_quote)
            )
        if str(quote["name"]).strip().casefold() == supplier.casefold():
            supplier_found = True

    if not supplier_found:
        raise ValueError(f"quotes do not contain target supplier '{supplier}'.")

    if not str(payload["payment_terms"]).strip():
        raise ValueError("payment_terms cannot be empty.")

    vendor = payload["vendor_risk"]
    if not isinstance(vendor, dict):
        raise ValueError("vendor_risk must be a JSON object.")
    missing_vendor = [name for name in VENDOR_FIELDS if name not in vendor]
    if missing_vendor:
        raise ValueError("vendor_risk is missing: " + ", ".join(missing_vendor))


def resolve_tools(tools_root):
    root = Path(tools_root).resolve()
    tools = {}

    for name in REQUIRED_TOOLS:
        path = root / name / "main.py"
        if not path.is_file():
            raise ValueError(
                f"missing tool '{name}': expected {path}. "
                "Clone the procurement-tooling repositories side-by-side "
                "or pass --tools-root."
            )
        tools[name] = path

    return tools


def run_command(command, *, capture_json=False):
    process = subprocess.run(
        [str(part) for part in command],
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "unknown error"
        raise RuntimeError(f"command failed: {' '.join(map(str, command))}\n{detail}")

    if capture_json:
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "command did not return valid JSON: " + " ".join(map(str, command))
            ) from exc

    return process.stdout


def write_json(payload, path):
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_pipeline(payload, tools, scorecard_main, work_dir):
    supplier = str(payload["supplier"]).strip()
    target_currency = str(payload["target_currency"]).upper()
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    normalized_quote_paths = []
    for index, quote in enumerate(payload["quotes"], start=1):
        raw_path = work_dir / f"quote-{index}-raw.json"
        normalized_path = work_dir / f"quote-{index}-normalized.json"
        write_json(quote, raw_path)

        run_command(
            [
                sys.executable,
                tools["currency-normalizer"],
                "--quote",
                raw_path,
                "--target-currency",
                target_currency,
                "--output",
                normalized_path,
            ]
        )
        normalized_quote_paths.append(normalized_path)

    rfq_path = work_dir / "rfq.json"
    run_command(
        [
            sys.executable,
            tools["rfqdiff"],
            *normalized_quote_paths,
            "--output",
            rfq_path,
        ]
    )

    payment_path = work_dir / "payment.json"
    run_command(
        [
            sys.executable,
            tools["payment-terms-parser"],
            str(payload["payment_terms"]),
            "--supplier",
            supplier,
            "--output",
            payment_path,
        ]
    )

    payment_payload = json.loads(payment_path.read_text(encoding="utf-8"))
    commercial_risk = float(
        payment_payload.get("commercial_risk", payment_payload.get("buyer_exposure"))
    )

    vendor = payload["vendor_risk"]
    vendor_payload = run_command(
        [
            sys.executable,
            tools["vendor-risk-engine"],
            supplier,
            "--on-time-delivery",
            vendor["on_time_delivery"],
            "--defect-rate",
            vendor["defect_rate"],
            "--prepayment-exposure",
            commercial_risk,
            "--compliance-incidents",
            vendor["compliance_incidents"],
            "--dependency-share",
            vendor["dependency_share"],
            "--json",
        ],
        capture_json=True,
    )
    vendor_path = work_dir / "vendor-risk.json"
    write_json(vendor_payload, vendor_path)

    result = run_command(
        [
            sys.executable,
            scorecard_main,
            supplier,
            "--rfq-json",
            rfq_path,
            "--payment-json",
            payment_path,
            "--vendor-risk-json",
            vendor_path,
            "--json",
        ],
        capture_json=True,
    )

    result["orchestration"] = {
        "tool": "supplier-scorecard-pipeline",
        "version": PIPELINE_VERSION,
        "target_currency": target_currency,
        "artifacts": {
            "rfq": str(rfq_path),
            "payment": str(payment_path),
            "vendor_risk": str(vendor_path),
        },
    }
    return result


def print_result(result):
    print()
    print(f"PROCUREMENT DECISION PIPELINE v{PIPELINE_VERSION}")
    print("-" * 58)
    print(f"Supplier             : {result['supplier']}")
    print(f"Composite score      : {result['score']:.2f} / 100")
    print(f"Recommendation       : {result['recommendation']}")
    print(f"Target currency      : {result['orchestration']['target_currency']}")
    print()
    print("Pipeline")
    print("-" * 58)
    print("currency-normalizer  : completed")
    print("rfqdiff              : completed")
    print("payment-terms-parser : completed")
    print("vendor-risk-engine   : completed")
    print("supplier-scorecard   : completed")


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete procurement decision pipeline from one JSON input."
        )
    )
    parser.add_argument("input", help="Unified procurement pipeline JSON input.")
    parser.add_argument(
        "--tools-root",
        help=(
            "Directory containing currency-normalizer, rfqdiff, "
            "payment-terms-parser and vendor-risk-engine repositories. "
            "Defaults to the parent directory of supplier-scorecard."
        ),
    )
    parser.add_argument(
        "--work-dir",
        help="Keep intermediate pipeline JSON artifacts in this directory.",
    )
    parser.add_argument(
        "--output",
        help="Write the final supplier-scorecard JSON result to this file.",
    )
    parser.add_argument("--json", action="store_true", help="Print final JSON.")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    scorecard_dir = Path(__file__).resolve().parent
    tools_root = Path(args.tools_root).resolve() if args.tools_root else scorecard_dir.parent
    scorecard_main = scorecard_dir / "main.py"

    try:
        payload = load_input(args.input)
        tools = resolve_tools(tools_root)

        if args.work_dir:
            result = run_pipeline(payload, tools, scorecard_main, args.work_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="supplier-scorecard-") as temp_dir:
                result = run_pipeline(payload, tools, scorecard_main, temp_dir)
                result["orchestration"]["artifacts"] = {
                    "rfq": "temporary",
                    "payment": "temporary",
                    "vendor_risk": "temporary",
                }

        if args.output:
            write_json(result, args.output)

    except (OSError, json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_result(result)


if __name__ == "__main__":
    main()
