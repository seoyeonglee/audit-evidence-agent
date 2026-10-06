from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

DATA = Path(__file__).resolve().parents[2] / "data" / "cloud"
router = APIRouter(prefix="/api/cloud-assurance", tags=["Cloud Assurance"])


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(min_length=1, max_length=80)
    region: str = Field(min_length=1, max_length=80)
    resource: str = Field(min_length=1, max_length=200)
    collected_at: date
    source: str = Field(min_length=1, max_length=200)
    data: dict[str, Any]


class Bundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: date
    account_id: str = Field(min_length=1, max_length=80)
    region: str = Field(min_length=1, max_length=80)
    evidence: dict[
        Literal[
            "iam", "s3", "trail", "kms", "incident", "backup", "vendor", "residency"
        ],
        Evidence,
    ]


def catalog():
    return json.loads((DATA / "catalog.json").read_text())


def read_path(data, path):
    for part in path.split("."):
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


def evaluate(bundle: Bundle):
    controls = catalog()["controls"]
    results = []
    for control in controls:
        evidence = bundle.evidence.get(control["evidence_key"])
        status, reason, checks, digest = (
            "missing",
            "Required evidence was not supplied.",
            [],
            None,
        )
        if evidence is not None:
            encoded = json.dumps(
                evidence.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            digest = hashlib.sha256(encoded.encode()).hexdigest()
            age = (bundle.as_of - evidence.collected_at).days
            if evidence.account_id != bundle.account_id or evidence.region not in (
                (bundle.region, "global")
                if control["evidence_key"] == "iam"
                else (bundle.region,)
            ):
                status, reason = (
                    "out_of_scope",
                    "Evidence account or region does not match the declared assessment scope.",
                )
            elif age < 0:
                status, reason = (
                    "invalid",
                    "Collection date is after the assessment date.",
                )
            elif age > control["max_age_days"]:
                status, reason = (
                    "stale",
                    f"Evidence is {age} days old; the demo policy allows {control['max_age_days']} days.",
                )
            elif control["checks"]:
                for rule in control["checks"]:
                    actual = read_path(evidence.data, rule["path"])
                    expected = rule["expected"]
                    valid_type = type(actual) is type(expected)
                    checks.append(
                        {
                            "path": rule["path"],
                            "actual": actual,
                            "expected": expected,
                            "status": "missing"
                            if not valid_type
                            else ("match" if actual == expected else "gap"),
                        }
                    )
                # A known failure remains actionable even if a different required field is absent.
                if any(c["status"] == "gap" for c in checks):
                    status, reason = (
                        "gap",
                        "One or more observed settings do not meet this project baseline.",
                    )
                elif any(c["status"] == "missing" for c in checks):
                    status, reason = (
                        "missing",
                        "Required settings are absent or have an invalid type.",
                    )
                else:
                    status, reason = (
                        "ready_for_review",
                        "Listed configuration checks match; human scope and operating-effectiveness review is still required.",
                    )
            elif not evidence.data:
                status, reason = (
                    "missing",
                    "Evidence record contains no review material.",
                )
            else:
                status, reason = (
                    "manual_review",
                    "Document presence alone cannot establish control effectiveness.",
                )
        actions = {
            "missing": "Collect complete, correctly typed evidence for the declared resource and period.",
            "stale": "Refresh the collection and verify changes since the previous snapshot.",
            "invalid": "Correct the collection metadata and independently verify its provenance.",
            "out_of_scope": "Collect evidence for the assessment account and region.",
            "gap": control["remediation"],
            "manual_review": control["review_procedure"],
            "ready_for_review": control["review_procedure"],
        }
        results.append(
            {
                **control,
                "status": status,
                "reason": reason,
                "checks_observed": checks,
                "evidence_sha256": digest,
                "evidence": evidence.model_dump(mode="json") if evidence else None,
                "next_action": actions[status],
                "review_required": True,
            }
        )
    return {
        "schema_version": "1.0",
        "catalog_version": catalog()["version"],
        "as_of": bundle.as_of.isoformat(),
        "account_id": bundle.account_id,
        "region": bundle.region,
        "scope": "One submitted resource snapshot per control; not account-wide coverage.",
        "decision": "readiness_only",
        "summary": dict(Counter(r["status"] for r in results)),
        "results": results,
    }


@router.get("/catalog")
def get_catalog():
    return catalog()


@router.get("/sample")
def get_sample():
    return json.loads((DATA / "sample.json").read_text())


@router.post("/assess")
async def assess(request: Request):
    # Bound raw bytes before JSON parsing; no storage, cloud credentials or network calls.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 100_000:
            raise HTTPException(422, "Evidence bundle exceeds the 100 KB limit.")
    try:
        bundle = Bundle.model_validate_json(bytes(body))
        json.dumps(bundle.model_dump(), default=str, allow_nan=False)
    except (ValidationError, ValueError):
        raise HTTPException(
            422, "Invalid bundle. Check dates, scope, evidence keys and metadata."
        ) from None
    return evaluate(bundle)
