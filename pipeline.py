import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from main import apply_policy, explain_portfolio, resolve_profile

PIPELINE_VERSION = "0.6"
REQUIRED_TOOLS = (
    "currency-normalizer",
    "rfqdiff",
    "payment-terms-parser",
    "vendor-risk-engine",
)
QUOTE_FIELDS = ("name", "currency", "price", "lead_time_weeks", "payment_days")
VENDOR_FIELDS = (
    "on_time_delivery",
    "defect_rate",
    "compliance_incidents",
    "dependency_share",
)


def load_input(path, *, profile_file=None):
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if profile_file is not None:
        payload.pop("category_profile", None)
        payload["profile_file"] = str(Path(profile_file).resolve())
    elif payload.get("profile_file"):
        custom = Path(payload["profile_file"])
        if not custom.is_absolute():
            custom = path.parent / custom
        payload["profile_file"] = str(custom.resolve())
    validate_input(payload)
    return payload


def _key(value):
    return str(value).strip().casefold()


def _validate_vendor(vendor, context="vendor_risk"):
    if not isinstance(vendor, dict):
        raise ValueError(f"{context} must be a JSON object.")
    missing = [name for name in VENDOR_FIELDS if name not in vendor]
    if missing:
        raise ValueError(f"{context} is missing: " + ", ".join(missing))


def input_mode(payload):
    return "portfolio" if "supplier_profiles" in payload else "single"


def validate_input(payload):
    if not isinstance(payload, dict):
        raise ValueError("pipeline input must be a JSON object.")
    missing = [name for name in ("target_currency", "quotes") if name not in payload]
    if missing:
        raise ValueError("pipeline input is missing: " + ", ".join(missing))
    resolve_profile(
        payload.get("category_profile"),
        policy=payload.get("policy"),
        profile_file=payload.get("profile_file"),
    )
    currency = str(payload["target_currency"]).strip().upper()
    if len(currency) != 3:
        raise ValueError("target_currency must be a 3-letter currency code.")
    quotes = payload["quotes"]
    if not isinstance(quotes, list) or len(quotes) < 2:
        raise ValueError("quotes must contain at least two supplier quotations.")
    quote_names = {}
    for index, quote in enumerate(quotes, start=1):
        if not isinstance(quote, dict):
            raise ValueError(f"quote {index} must be a JSON object.")
        missing = [name for name in QUOTE_FIELDS if name not in quote]
        if missing:
            raise ValueError(f"quote {index} is missing: " + ", ".join(missing))
        name = str(quote["name"]).strip()
        if not name:
            raise ValueError(f"quote {index} supplier name cannot be empty.")
        key = _key(name)
        if key in quote_names:
            raise ValueError(f"duplicate quotation supplier: '{name}'.")
        quote_names[key] = name

    if input_mode(payload) == "single":
        missing = [name for name in ("supplier", "payment_terms", "vendor_risk") if name not in payload]
        if missing:
            raise ValueError("pipeline input is missing: " + ", ".join(missing))
        supplier = str(payload["supplier"]).strip()
        if not supplier:
            raise ValueError("supplier cannot be empty.")
        if _key(supplier) not in quote_names:
            raise ValueError(f"quotes do not contain target supplier '{supplier}'.")
        if not str(payload["payment_terms"]).strip():
            raise ValueError("payment_terms cannot be empty.")
        _validate_vendor(payload["vendor_risk"])
        return

    if any(name in payload for name in ("supplier", "payment_terms", "vendor_risk")):
        raise ValueError("portfolio mode uses supplier_profiles; do not combine it with single-supplier fields.")
    profiles = payload.get("supplier_profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("supplier_profiles must be a non-empty list.")
    seen = {}
    for index, profile in enumerate(profiles, start=1):
        if not isinstance(profile, dict):
            raise ValueError(f"supplier profile {index} must be a JSON object.")
        missing = [name for name in ("supplier", "payment_terms", "vendor_risk") if name not in profile]
        if missing:
            raise ValueError(f"supplier profile {index} is missing: " + ", ".join(missing))
        supplier = str(profile["supplier"]).strip()
        key = _key(supplier)
        if not supplier:
            raise ValueError(f"supplier profile {index} name cannot be empty.")
        if key in seen:
            raise ValueError(f"duplicate supplier profile: '{supplier}'.")
        if key not in quote_names:
            raise ValueError(f"supplier profile '{supplier}' has no matching quotation.")
        if not str(profile["payment_terms"]).strip():
            raise ValueError(f"payment_terms cannot be empty for '{supplier}'.")
        _validate_vendor(profile["vendor_risk"], f"vendor_risk for '{supplier}'")
        seen[key] = supplier
    missing_profiles = [name for key, name in quote_names.items() if key not in seen]
    if missing_profiles:
        raise ValueError("missing supplier profile(s) for quotation supplier(s): " + ", ".join(missing_profiles))


def resolve_tools(tools_root):
    root = Path(tools_root).resolve()
    tools = {}
    for name in REQUIRED_TOOLS:
        path = root / name / "main.py"
        if not path.is_file():
            raise ValueError(
                f"missing tool '{name}': expected {path}. Clone the procurement-tooling "
                "repositories side-by-side or pass --tools-root."
            )
        tools[name] = path
    return tools


def run_command(command, *, capture_json=False):
    process = subprocess.run([str(part) for part in command], capture_output=True, text=True, check=False)
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "unknown error"
        raise RuntimeError(f"command failed: {' '.join(map(str, command))}\n{detail}")
    if not capture_json:
        return process.stdout
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("command did not return valid JSON: " + " ".join(map(str, command))) from exc


def write_json(payload, path):
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _safe_dir(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-.") or "supplier"


def _prepare_rfq(payload, tools, work_dir):
    normalized = []
    for index, quote in enumerate(payload["quotes"], start=1):
        raw = work_dir / f"quote-{index}-raw.json"
        out = work_dir / f"quote-{index}-normalized.json"
        write_json(quote, raw)
        run_command([
            sys.executable,
            tools["currency-normalizer"],
            "--quote",
            raw,
            "--target-currency",
            str(payload["target_currency"]).upper(),
            "--output",
            out,
        ])
        normalized.append(out)
    rfq = work_dir / "rfq.json"
    run_command([sys.executable, tools["rfqdiff"], *normalized, "--output", rfq])
    return rfq


def _run_supplier(profile, tools, scorecard_main, rfq_path, supplier_dir, *, resolved_profile):
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
    payment = json.loads(payment_path.read_text(encoding="utf-8"))
    commercial_risk = float(payment.get("commercial_risk", payment.get("buyer_exposure")))
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

    command = [
        sys.executable,
        scorecard_main,
        supplier,
        "--rfq-json",
        rfq_path,
        "--payment-json",
        payment_path,
        "--vendor-risk-json",
        vendor_path,
    ]
    source = resolved_profile["source"]
    if source["type"] == "file":
        command += ["--profile-file", source["path"]]
    else:
        command += ["--category-profile", resolved_profile["name"]]
    command.append("--json")
    result = run_command(command, capture_json=True)
    result = apply_policy(
        result,
        compliance_incidents=vendor["compliance_incidents"],
        policy=resolved_profile["policy"],
    )
    return result, payment_path, vendor_path


def _rank(results):
    ranked = sorted(results, key=lambda item: (-float(item["score"]), str(item["supplier"]).casefold()))
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked


def _policy_selection(ranked):
    leader = ranked[0]
    eligible = [item for item in ranked if item["policy"]["auto_eligible"]]
    recommended = eligible[0] if eligible else None
    excluded = [
        {
            "supplier": item["supplier"],
            "score": item["score"],
            "policy_status": item["policy"]["status"],
            "final_decision": item["final_decision"],
            "reasons": [trigger["reason"] for trigger in item["policy"]["triggers"]],
        }
        for item in ranked if not item["policy"]["auto_eligible"]
    ]
    if recommended is None:
        summary = "No supplier is auto-eligible after score and policy gates; automatic recommendation is withheld."
    elif recommended["supplier"] == leader["supplier"]:
        summary = f"{recommended['supplier']} is the highest-scoring supplier and passes all automatic policy gates."
    else:
        reason = leader["policy"]["triggers"][0]["reason"] if leader["policy"]["triggers"] else f"its score recommendation is {leader['recommendation']}."
        summary = (
            f"{leader['supplier']} is the score leader at {leader['score']:.2f}/100 but is not auto-eligible because "
            f"{reason[0].lower() + reason[1:]} {recommended['supplier']} is the highest-scoring supplier that passes all automatic gates."
        )
    return {
        "top_scoring_supplier": leader["supplier"],
        "recommended_supplier": recommended["supplier"] if recommended else None,
        "status": "AUTO-RECOMMENDED" if recommended else "NO AUTO-APPROVED SUPPLIER",
        "summary": summary,
        "excluded_from_auto_recommendation": excluded,
    }


def run_pipeline(payload, tools, scorecard_main, work_dir):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    resolved = resolve_profile(
        payload.get("category_profile"),
        policy=payload.get("policy"),
        profile_file=payload.get("profile_file"),
    )
    target_currency = str(payload["target_currency"]).upper()
    rfq_path = _prepare_rfq(payload, tools, work_dir)

    if input_mode(payload) == "single":
        profile = {
            "supplier": payload["supplier"],
            "payment_terms": payload["payment_terms"],
            "vendor_risk": payload["vendor_risk"],
        }
        result, payment, vendor = _run_supplier(
            profile,
            tools,
            scorecard_main,
            rfq_path,
            work_dir,
            resolved_profile=resolved,
        )
        result["orchestration"] = {
            "tool": "supplier-scorecard-pipeline",
            "version": PIPELINE_VERSION,
            "mode": "single",
            "target_currency": target_currency,
            "category_profile": resolved["name"],
            "profile_source": resolved["source"],
            "artifacts": {"rfq": str(rfq_path), "payment": str(payment), "vendor_risk": str(vendor)},
        }
        return result

    results, artifact_map, used = [], {}, set()
    supplier_root = work_dir / "suppliers"
    for index, profile in enumerate(payload["supplier_profiles"], start=1):
        supplier = str(profile["supplier"]).strip()
        dirname = _safe_dir(supplier)
        if dirname.casefold() in used:
            dirname = f"{dirname}-{index}"
        used.add(dirname.casefold())
        result, payment, vendor = _run_supplier(
            profile,
            tools,
            scorecard_main,
            rfq_path,
            supplier_root / dirname,
            resolved_profile=resolved,
        )
        results.append(result)
        artifact_map[supplier] = {"payment": str(payment), "vendor_risk": str(vendor)}

    ranked = _rank(results)
    policy_decision = _policy_selection(ranked)
    return {
        "tool": "supplier-scorecard-portfolio",
        "version": "0.5",
        "category_profile": resolved["name"],
        "profile": {
            "name": resolved["name"],
            "description": resolved["description"],
            "weights": resolved["weights"],
            "policy": resolved["policy"],
            "source": resolved["source"],
        },
        "recommended_supplier": policy_decision["recommended_supplier"],
        "top_scoring_supplier": policy_decision["top_scoring_supplier"],
        "decision_status": policy_decision["status"],
        "supplier_count": len(ranked),
        "target_currency": target_currency,
        "policy": resolved["policy"],
        "suppliers": ranked,
        "explanation": explain_portfolio(ranked),
        "policy_decision": policy_decision,
        "orchestration": {
            "tool": "supplier-scorecard-pipeline",
            "version": PIPELINE_VERSION,
            "mode": "portfolio",
            "target_currency": target_currency,
            "category_profile": resolved["name"],
            "profile_source": resolved["source"],
            "artifacts": {"rfq": str(rfq_path), "supplier_outputs": artifact_map},
        },
    }


def print_result(result):
    orchestration = result["orchestration"]
    if orchestration["mode"] == "portfolio":
        print(f"\nPROCUREMENT PORTFOLIO PIPELINE v{PIPELINE_VERSION}")
        print("-" * 116)
        print(f"{'#':>3} {'Supplier':28} {'Score':>8} {'Score rec.':>12} {'Policy':>10} {'Final':>12}")
        print("-" * 116)
        for item in result["suppliers"]:
            print(
                f"{item['rank']:>3} {item['supplier'][:28]:28} {item['score']:8.2f} "
                f"{item['recommendation']:>12} {item['policy']['status']:>10} {item['final_decision']:>12}"
            )
        print("-" * 116)
        print(f"Category profile     : {result['category_profile']}")
        print(f"Top-scoring supplier : {result['top_scoring_supplier']}")
        print(f"Recommended supplier : {result['recommended_supplier'] or 'none'}")
        print(f"Decision status      : {result['decision_status']}")
        print(f"Policy decision      : {result['policy_decision']['summary']}")
        return
    print(f"\nPROCUREMENT DECISION PIPELINE v{PIPELINE_VERSION}")
    print("-" * 76)
    print(f"Supplier             : {result['supplier']}")
    print(f"Category profile     : {result['category_profile']}")
    print(f"Composite score      : {result['score']:.2f} / 100")
    print(f"Policy status        : {result['policy']['status']}")
    print(f"Final decision       : {result['final_decision']}")
    print(f"Decision reason      : {result['explanation']['summary']}")


def build_parser():
    parser = argparse.ArgumentParser(description="Run the complete procurement decision pipeline from one JSON input.")
    parser.add_argument("input", help="Unified procurement pipeline JSON input.")
    parser.add_argument("--profile-file", help="Override the input profile with a custom profile JSON file.")
    parser.add_argument("--tools-root")
    parser.add_argument("--work-dir")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def _mark_temporary(result):
    if result["orchestration"]["mode"] == "portfolio":
        result["orchestration"]["artifacts"] = {"rfq": "temporary", "supplier_outputs": "temporary"}
    else:
        result["orchestration"]["artifacts"] = {"rfq": "temporary", "payment": "temporary", "vendor_risk": "temporary"}


def main():
    parser = build_parser()
    args = parser.parse_args()
    scorecard_dir = Path(__file__).resolve().parent
    tools_root = Path(args.tools_root).resolve() if args.tools_root else scorecard_dir.parent
    try:
        payload = load_input(args.input, profile_file=args.profile_file)
        tools = resolve_tools(tools_root)
        if args.work_dir:
            result = run_pipeline(payload, tools, scorecard_dir / "main.py", args.work_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="supplier-scorecard-") as temp_dir:
                result = run_pipeline(payload, tools, scorecard_dir / "main.py", temp_dir)
                _mark_temporary(result)
        if args.output:
            write_json(result, args.output)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False)) if args.json else print_result(result)


if __name__ == "__main__":
    main()
