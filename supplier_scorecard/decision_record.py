"""Operational provenance wrapper for supplier-scorecard v1.0 results.

This module deliberately sits outside the deterministic scoring core. It may wrap
single-supplier or portfolio results, but it must never change their score,
recommendation, policy, or ranking semantics.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

DECISION_RECORD_SCHEMA = "supplier-scorecard.decision-record"
DECISION_RECORD_SCHEMA_VERSION = "1.0"
CANONICALIZATION = "json-sort-keys-compact-v1"
HASH_ALGORITHM = "sha256"
REVIEW_STATES = frozenset({"NOT_REQUIRED", "PENDING", "APPROVED_EXCEPTION", "REJECTED"})


def canonical_json(value: Any) -> str:
    """Return the stable JSON representation used for decision-record hashes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    """Hash a JSON-compatible value using the decision-record canonical form."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash exact file bytes with SHA-256."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(
    role: str,
    path: str | Path | None,
    *,
    tool: str | None = None,
    version: str | None = None,
    retained: bool | None = None,
) -> dict[str, Any]:
    """Create an explicit artifact-provenance entry.

    If ``retained`` is omitted, an existing file is considered retained. Missing,
    temporary, or intentionally discarded artifacts are represented explicitly
    with ``retained=False`` and no hash.
    """
    role = str(role).strip()
    if not role:
        raise ValueError("artifact role cannot be empty.")

    raw_path = None if path is None else str(path)
    file_path = None if path is None else Path(path)
    if retained is None:
        retained = bool(file_path and file_path.is_file())

    if retained and (file_path is None or not file_path.is_file()):
        raise ValueError(f"retained artifact does not exist: {raw_path}")

    return {
        "role": role,
        "path": raw_path,
        "tool": tool,
        "version": version,
        "sha256": sha256_file(file_path) if retained else None,
        "retained": bool(retained),
    }


def _single_review_required(result: Mapping[str, Any]) -> bool:
    policy = result.get("policy")
    if not isinstance(policy, Mapping):
        return False
    return policy.get("status") in {"REVIEW", "BLOCKED"}


def review_required(result: Mapping[str, Any]) -> bool:
    """Derive whether the operational decision needs human review.

    Single-supplier records follow the v1.0 policy status directly. Portfolio
    records require review only when the pipeline withheld an automatic supplier
    recommendation. A portfolio may contain individually reviewed suppliers while
    still having another policy-eligible automatic recommendation.
    """
    if result.get("tool") == "supplier-scorecard-portfolio" or isinstance(result.get("suppliers"), list):
        if result.get("recommended_supplier") is not None:
            return False
        return result.get("decision_status") == "NO AUTO-APPROVED SUPPLIER"
    return _single_review_required(result)


def initial_review(result: Mapping[str, Any]) -> dict[str, Any]:
    required = review_required(result)
    return {
        "required": required,
        "status": "PENDING" if required else "NOT_REQUIRED",
        "reviewer": None,
        "reviewed_at": None,
        "note": None,
    }


def _profile_snapshot(result: Mapping[str, Any]) -> dict[str, Any]:
    profile = result.get("profile")
    return deepcopy(profile) if isinstance(profile, Mapping) else {}


def _policy_snapshot(result: Mapping[str, Any]) -> dict[str, Any]:
    policy = result.get("policy")
    if isinstance(policy, Mapping):
        rules = policy.get("rules")
        if isinstance(rules, Mapping):
            return deepcopy(rules)
        if result.get("tool") == "supplier-scorecard-portfolio":
            return deepcopy(policy)
    profile = result.get("profile")
    if isinstance(profile, Mapping) and isinstance(profile.get("policy"), Mapping):
        return deepcopy(profile["policy"])
    return {}


def create_decision_record(
    result: Mapping[str, Any],
    *,
    artifacts: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap an existing v1.0 result in a tamper-evident operational record."""
    if not isinstance(result, Mapping):
        raise ValueError("result must be a mapping.")

    result_snapshot = deepcopy(dict(result))
    profile = _profile_snapshot(result_snapshot)
    policy = _policy_snapshot(result_snapshot)
    artifact_snapshots = [deepcopy(dict(item)) for item in (artifacts or [])]

    record = {
        "schema": DECISION_RECORD_SCHEMA,
        "schema_version": DECISION_RECORD_SCHEMA_VERSION,
        "result": result_snapshot,
        "provenance": {
            "scorecard": {
                "tool": result_snapshot.get("tool", "supplier-scorecard"),
                "version": result_snapshot.get("version"),
            },
            "profile": {"snapshot": profile, "sha256": sha256_json(profile)},
            "policy": {"snapshot": policy, "sha256": sha256_json(policy)},
            "artifacts": artifact_snapshots,
        },
        "review": initial_review(result_snapshot),
    }
    record["integrity"] = {
        "algorithm": HASH_ALGORITHM,
        "canonicalization": CANONICALIZATION,
        "payload_sha256": sha256_json(record),
    }
    return record


def refresh_integrity(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with a payload hash matching its current operational state."""
    updated = deepcopy(dict(record))
    updated.pop("integrity", None)
    updated["integrity"] = {
        "algorithm": HASH_ALGORITHM,
        "canonicalization": CANONICALIZATION,
        "payload_sha256": sha256_json(updated),
    }
    return updated


def verify_decision_record(record: Mapping[str, Any], *, verify_artifacts: bool = True) -> dict[str, Any]:
    """Verify schema, snapshot hashes, payload integrity and retained artifacts."""
    errors: list[str] = []
    if record.get("schema") != DECISION_RECORD_SCHEMA:
        errors.append("unexpected decision-record schema")
    if record.get("schema_version") != DECISION_RECORD_SCHEMA_VERSION:
        errors.append("unexpected decision-record schema version")

    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        errors.append("missing provenance object")
        provenance = {}

    for name in ("profile", "policy"):
        item = provenance.get(name)
        if not isinstance(item, Mapping):
            errors.append(f"missing {name} provenance")
            continue
        expected = item.get("sha256")
        actual = sha256_json(item.get("snapshot", {}))
        if expected != actual:
            errors.append(f"{name} snapshot hash mismatch")

    review = record.get("review")
    if not isinstance(review, Mapping) or review.get("status") not in REVIEW_STATES:
        errors.append("invalid review state")

    integrity = record.get("integrity")
    if not isinstance(integrity, Mapping):
        errors.append("missing integrity object")
    else:
        payload = deepcopy(dict(record))
        payload.pop("integrity", None)
        actual = sha256_json(payload)
        if integrity.get("payload_sha256") != actual:
            errors.append("decision payload hash mismatch")

    if verify_artifacts:
        artifacts = provenance.get("artifacts", []) if isinstance(provenance, Mapping) else []
        if not isinstance(artifacts, list):
            errors.append("artifacts provenance must be a list")
        else:
            for index, artifact in enumerate(artifacts):
                if not isinstance(artifact, Mapping):
                    errors.append(f"artifact {index} is not an object")
                    continue
                if not artifact.get("retained"):
                    continue
                path = artifact.get("path")
                if not path or not Path(path).is_file():
                    errors.append(f"retained artifact missing: {path}")
                    continue
                if artifact.get("sha256") != sha256_file(path):
                    errors.append(f"artifact hash mismatch: {path}")

    return {"valid": not errors, "errors": errors}
