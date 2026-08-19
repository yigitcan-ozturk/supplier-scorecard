import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


PIPELINE_VERSION = "0.2"
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


def _normalize_name(value):
    return str(value).strip().casefold()


def _validate_quotes(payload):
    target_currency = str(payload.get("target_currency", "")).strip().upper()
    if len(target_currency) != 3:
        raise ValueError("target_currency must be a 3-letter currency code.")

    quotes = payload.get("quotes")
    if not isinstance(quotes, list) or len(quotes) < 2:
        raise ValueError("quotes must contain at least two supplier quotations.")

    quote_names = {}
    for index, quote in enumerate(quotes, start=1):
        if not isinstance(quote, dict):
            raise ValueError(f"quote {index} must be a JSON object.")
        missing_quote = [name for name in QUOTE_FIELDS if name not in quote]
        if missing_quote:
            raise ValueError(f"quote {index} is missing: " + ", ".join(missing_quote))
        name = str(quote["name"]).strip()
        if not name:
            raise ValueError(f"quote {index} supplier name cannot be empty.")
        key = _normalize_name(name)
        if key in quote_names:
            raise ValueError(f"duplicate quotation supplier: '{name}'.")
        quote_names[key] = name

    return target_currency, quote_names


def _validate_vendor_risk(vendor, context="vendor_risk"):
    if not isinstance(vendor, dict):
        raise ValueError(f"{context} must be a JSON object.")
    missing_vendor = [name for name in VENDOR_FIELDS if name not in vendor]
    if missing_vendor:
        raise ValueError(f"{context} is missing: " + ", ".join(missing_vendor))


def input_mode(payload):
    return "portfolio" if "supplier_profiles" in payload else "single"


def validate_input(payload):
    if not isinstance(payload, dict):
        raise ValueError("pipeline input must be a JSON object.")

    if "target_currency" not in payload or "quotes" not in payload:
        missing = [name for name in ("target_currency", "quotes") if name not in payload]
        raise ValueError("pipeline input is missing: " + ", ".join(missing))

    _, quote_names = _validate_quotes(payload)
    mode = input_mode(payload)

    if mode == "single":
        required = ("supplier", "payment_terms", "vendor_risk")
        missing = [name for name in required if name not in payload]
        if missing:
            raise ValueError("pipeline input is missing: " + ", ".join(missing))
        supplier = str(payload["supplier"]).strip()
        if not supplier:
            raise ValueError("supplier cannot be empty.")
        if _normalize_name(supplier) not in quote_names:
            raise ValueError(f"quotes do not contain target supplier '{supplier}'.")
        if not str(payload["payment_terms"]).strip():
            raise ValueError("payment_terms cannot be empty.")
        _validate_vendor_risk(payload["vendor_risk"])
        return

    if any(name in payload for name in ("supplier", "payment_terms", "vendor_risk")):
        raise ValueError(
            "portfolio mode uses supplier_profiles; do not combine it with single-supplier fields."
        )

    profiles = payload["supplier_profiles"]
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("supplier_profiles must be a non-empty list.")

    profile_names = {}
    for index, profile in enumerate(profiles, start=1):
        if not isinstance(profile, dict):
            raise ValueError(f"supplier profile {index} must be a JSON object.")
        missing = [name for name in ("supplier", "payment_terms", "vendor_risk") if name not in profile]
        if missing:
            raise ValueError(f"supplier profile {index} is missing: " + ", ".join(missing))
        supplier = str(profile["supplier"]).strip()
        if not supplier:
            raise ValueError(f"supplier profile {index} name cannot be empty.")
        key = _normalize_name(supplier)
        if key in profile_names:
            raise ValueError(f"duplicate supplier profile: '{supplier}'.")
        profile_names[key] = supplier
        if key not in quote_names:
            raise ValueError(f"supplier profile '{supplier}' has no matching quotation.")
        if not str(profile["payment_terms"]).strip():
            raise ValueError(f"payment_terms cannot be empty for '{supplier}'.")
        _validate_vendor_risk(profile["vendor_risk"], context=f"vendor_risk for '{supplier}'")

    missing_profiles = [display_name for key, display_name in quote_names.items() if key not in profile_names]
    if missing_profiles:
        raise ValueError(
            "missing supplier profile(s) for quotation supplier(s): " + ", ".join(missing_profiles)
        )


def resolve_tools(tools_root):
    root = Path(tools_root).resolve()
    tools = {}
    for name in REQUIRED_TOOLS:
        path = root / name / "main.py"
        if not path.is_file():
            raise ValueError(
                f"missing tool '{name}': expected {path}. "
                "Clone the procurement-tooling repositories side-by-side or pass --tools-root."
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


def _safe_dir_name(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-.")
    return value or "supplier"


def _normalize_quotes(payload, tools, work_dir):
    target_currency = str(payload["target_currency"]).upper()
    normalized_quote_paths = []
    for index, quote in enumerate(payload["quotes"], start=1):
        raw_path = work_dir / f"quote-{index}-raw.json"
        normalized_path = work_dir / f"quote-{index}-normalized.json"
        write_json(quote, raw_path)
        run_command([
            sys.executable,
            tools["currency-normalizer"],
            "--quote",
            raw_path,
            "--target-currency",
            target_currency,
            "--output",
            normalized_path,
        ])
        normalized_quote_paths.append(normalized_path)
    return normalized_quote_paths


def _run_rfq(normalized_quote_paths, tools, work_dir):
    rfq_path = work_dir / "rfq.json"
    run_command([
        sys.executable,
        tools["rfqdiff"],
        *normalized_quote_paths,
        "--output",
        rfq_path,
    ])
    return rfq_path


def _run_supplier_score(profile, tools, scorecard_main, rfq_path, supplier_dir):
    supplier = str(profile["supplier"]).strip()
    supplier_dir.mkdir(parents=True, exist_ok=True)

    payment_path = supplier_dir / "payment.json"
    run_command([
        sys.executable,
        tools["payment-terms-parser"],
        str(profile["payment_terms"]),
        "--supplier",
        supplier,
        "--output",
        payment_path,
    ])
    payment_payload = json.loads(payment_path.read_text(encoding="utf-8"))
    commercial_risk = float(
        payment_payload.get("commercial_risk", payment_payload.get("buyer_exposure"))
    )

    vendor = profile["vendor_risk"]
    vendor_payload = run_command([
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
    ], capture_json=True)
    vendor_path = supplier_dir / "vendor-risk.json"
    write_json(vendor_payload, vendor_path)

    result = run_command([
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
    ], capture_json=True)
    return result, payment_path, vendor_path


def _rank_portfolio(results):
    ranked = sorted(
        results,
        key=lambda item: (-float(item["score"]), str(item["supplier"]).casefold()),
    )
    for rank, result in enumerate(ranked, start=1):
        result["rank"] = rank
    return ranked


def run_pipeline(payload, tools, scorecard_main, work_dir):
    target_currency = str(payload["target_currency"]).upper()
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    normalized_quote_paths = _normalize_quotes(payload, tools, work_dir)
    rfq_path = _run_rfq(normalized_quote_paths, tools, work_dir)

    if input_mode(payload) == "single":
        profile = {
            "supplier": payload["supplier"],
            "payment_terms": payload["payment_terms"],
            "vendor_risk": payload["vendor_risk"],
        }
        result, payment_path, vendor_path = _run_supplier_score(
            profile, tools, scorecard_main, rfq_path, work_dir
        )
        result["orchestration"] = {
            "tool": "supplier-scorecard-pipeline",
            "version": PIPELINE_VERSION,
            "mode": "single",
            "target_currency": target_currency,
            "artifacts": {
                "rfq": str(rfq_path),
                "payment": str(payment_path),
                "vendor_risk": str(vendor_path),
            },
        }
        return result

    results = []
    artifact_map = {}
    suppliers_root = work_dir / "suppliers"
    used_dirs = set()
    for index, profile in enumerate(payload["supplier_profiles"], start=1):
        supplier = str(profile["supplier"]).strip()
        dirname = _safe_dir_name(supplier)
        if dirname.casefold() in used_dirs:
            dirname = f"{dirname}-{index}"
        used_dirs.add(dirname.casefold())
        supplier_dir = suppliers_root / dirname
        result, payment_path, vendor_path = _run_supplier_score(
            profile, tools, scorecard_main, rfq_path, supplier_dir
        )
        results.append(result)
        artifact_map[supplier] = {
            "payment": str(payment_path),
            "vendor_risk": str(vendor_path),
        }

    ranked = _rank_portfolio(results)
    return {
        "tool": "supplier-scorecard-portfolio",
        "version": "0.1",
        "recommended_supplier": ranked[0]["supplier"],
        "supplier_count": len(ranked),
        "target_currency": target_currency,
        "suppliers": ranked,
        "orchestration": {
            "tool": "supplier-scorecard-pipeline",
            "version": PIPELINE_VERSION,
            "mode": "portfolio",
            "target_currency": target_currency,
            "artifacts": {
                "rfq": str(rfq_path),
                "supplier_outputs": artifact_map,
            },
        },
    }


def print_result(result):
    orchestration = result["orchestration"]
    if orchestration.get("mode") == "portfolio":
        print()
        print(f"PROCUREMENT PORTFOLIO PIPELINE v{PIPELINE_VERSION}")
        print("-" * 84)
        print(f"{'#':>3} {'Supplier':30} {'Score':>8} {'Recommendation':>18}")
        print("-" * 84)
        for item in result["suppliers"]:
            print(
                f"{item['rank']:>3} {item['supplier'][:30]:30} "
                f"{item['score']:8.2f} {item['recommendation']:>18}"
            )
        print("-" * 84)
        print(f"Recommended supplier : {result['recommended_supplier']}")
        print(f"Suppliers evaluated  : {result['supplier_count']}")
        print(f"Target currency      : {result['target_currency']}")
        return

    print()
    print(f"PROCUREMENT DECISION PIPELINE v{PIPELINE_VERSION}")
    print("-" * 58)
    print(f"Supplier             : {result['supplier']}")
    print(f"Composite score      : {result['score']:.2f} / 100")
    print(f"Recommendation       : {result['recommendation']}")
    print(f"Target currency      : {orchestration['target_currency']}")
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
        description="Run the complete procurement decision pipeline from one JSON input."
    )
    parser.add_argument("input", help="Unified procurement pipeline JSON input.")
    parser.add_argument(
        "--tools-root",
        help=(
            "Directory containing currency-normalizer, rfqdiff, payment-terms-parser "
            "and vendor-risk-engine repositories. Defaults to the parent directory "
            "of supplier-scorecard."
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


def _mark_temporary_artifacts(result):
    if result["orchestration"].get("mode") == "portfolio":
        result["orchestration"]["artifacts"] = {
            "rfq": "temporary",
            "supplier_outputs": "temporary",
        }
    else:
        result["orchestration"]["artifacts"] = {
            "rfq": "temporary",
            "payment": "temporary",
            "vendor_risk": "temporary",
        }


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
                _mark_temporary_artifacts(result)

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
