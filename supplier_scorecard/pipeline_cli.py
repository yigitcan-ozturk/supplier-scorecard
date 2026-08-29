"""Installed CLI entry point for the supplier-scorecard orchestration pipeline.

The installed CLI extends the legacy source-level pipeline with optional Phase 2
operational decision-record output while preserving the deterministic v1.0 result.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pipeline

from .decision_record import artifact_record, create_decision_record


def build_parser():
    parser = pipeline.build_parser()
    parser.add_argument(
        "--decision-record",
        help="Write an opt-in tamper-evident decision record JSON to this path.",
    )
    return parser


def _read_json(path):
    if path in (None, "temporary"):
        return {}
    candidate = Path(path)
    if not candidate.is_file():
        return {}
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_version(result, source_name, *, path=None):
    sources = result.get("sources") if isinstance(result, dict) else None
    source = sources.get(source_name) if isinstance(sources, dict) else None
    if isinstance(source, dict) and source.get("version"):
        return source["version"]

    payload = _read_json(path)
    if payload.get("version"):
        return payload["version"]

    meta = payload.get("meta")
    if isinstance(meta, dict):
        if meta.get("engine_version"):
            return meta["engine_version"]
        if meta.get("model_version"):
            return meta["model_version"]

    normalization = payload.get("normalization")
    if isinstance(normalization, dict) and normalization.get("version"):
        return normalization["version"]

    return None


def _representative_supplier_result(result):
    if not isinstance(result, dict):
        return {}
    if isinstance(result.get("suppliers"), list) and result["suppliers"]:
        return result["suppliers"][0]
    return result


def _currency_normalizer_records(rfq):
    if rfq in (None, "temporary"):
        return []
    rfq_path = Path(rfq)
    if not rfq_path.is_file():
        return []

    records = []
    for index, path in enumerate(sorted(rfq_path.parent.glob("quote-*-normalized.json")), 1):
        records.append(
            artifact_record(
                f"currency-normalizer-output:{index}",
                path,
                tool="currency-normalizer",
                version=_source_version({}, "currency_normalizer", path=path),
            )
        )
    return records


def _artifact_records(result, *, input_path, profile_file=None):
    records = [
        artifact_record(
            "pipeline-input",
            input_path,
            tool="supplier-scorecard-pipeline",
            version=pipeline.PIPELINE_VERSION,
        )
    ]
    if profile_file:
        records.append(artifact_record("profile-file", profile_file))

    orchestration = result.get("orchestration", {})
    artifacts = orchestration.get("artifacts", {})
    representative = _representative_supplier_result(result)

    rfq = artifacts.get("rfq") if isinstance(artifacts, dict) else None
    records.extend(_currency_normalizer_records(rfq))
    records.append(
        artifact_record(
            "rfqdiff-output",
            rfq,
            tool="rfqdiff",
            version=_source_version(representative, "rfqdiff", path=rfq),
            retained=rfq not in (None, "temporary"),
        )
    )

    if orchestration.get("mode") == "single":
        payment = artifacts.get("payment") if isinstance(artifacts, dict) else None
        vendor = artifacts.get("vendor_risk") if isinstance(artifacts, dict) else None
        records.extend(
            [
                artifact_record(
                    "payment-terms-output",
                    payment,
                    tool="payment-terms-parser",
                    version=_source_version(result, "payment_terms_parser", path=payment),
                    retained=payment not in (None, "temporary"),
                ),
                artifact_record(
                    "vendor-risk-output",
                    vendor,
                    tool="vendor-risk-engine",
                    version=_source_version(result, "vendor_risk_engine", path=vendor),
                    retained=vendor not in (None, "temporary"),
                ),
            ]
        )
        return records

    supplier_outputs = artifacts.get("supplier_outputs") if isinstance(artifacts, dict) else None
    if supplier_outputs == "temporary" or not isinstance(supplier_outputs, dict):
        records.extend(
            [
                artifact_record("payment-terms-outputs", "temporary", tool="payment-terms-parser", retained=False),
                artifact_record("vendor-risk-outputs", "temporary", tool="vendor-risk-engine", retained=False),
            ]
        )
        return records

    supplier_results = {
        str(item.get("supplier")): item
        for item in result.get("suppliers", [])
        if isinstance(item, dict) and item.get("supplier") is not None
    }
    for supplier in sorted(supplier_outputs, key=str.casefold):
        paths = supplier_outputs[supplier]
        if not isinstance(paths, dict):
            continue
        supplier_result = supplier_results.get(str(supplier), {})
        payment = paths.get("payment")
        vendor = paths.get("vendor_risk")
        records.extend(
            [
                artifact_record(
                    f"payment-terms-output:{supplier}",
                    payment,
                    tool="payment-terms-parser",
                    version=_source_version(supplier_result, "payment_terms_parser", path=payment),
                    retained=payment not in (None, "temporary"),
                ),
                artifact_record(
                    f"vendor-risk-output:{supplier}",
                    vendor,
                    tool="vendor-risk-engine",
                    version=_source_version(supplier_result, "vendor_risk_engine", path=vendor),
                    retained=vendor not in (None, "temporary"),
                ),
            ]
        )
    return records


def main():
    parser = build_parser()
    args = parser.parse_args()
    scorecard_dir = Path(pipeline.__file__).resolve().parent
    tools_root = Path(args.tools_root).resolve() if args.tools_root else scorecard_dir.parent

    try:
        payload = pipeline.load_input(args.input, profile_file=args.profile_file)
        tools = pipeline.resolve_tools(tools_root)
        if args.work_dir:
            result = pipeline.run_pipeline(payload, tools, scorecard_dir / "main.py", args.work_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="supplier-scorecard-") as temp:
                result = pipeline.run_pipeline(payload, tools, scorecard_dir / "main.py", temp)
                pipeline._temporary_artifacts(result)

        if args.output:
            pipeline.write_json(result, args.output)

        if args.decision_record:
            records = _artifact_records(
                result,
                input_path=args.input,
                profile_file=payload.get("profile_file"),
            )
            decision_record = create_decision_record(result, artifacts=records)
            pipeline.write_json(decision_record, args.decision_record)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False), end="")
    else:
        pipeline.print_result(result)


if __name__ == "__main__":
    main()
