"""Offline structured extraction. Scores are rule completeness, not model probability."""

import csv
from datetime import date
import io
import json
import re

FIELDS = {
    "system",
    "period",
    "reviewed_users",
    "exceptions",
    "owner",
    "vendor",
    "review_date",
}
INSTRUCTIONS = re.compile(
    r"ignore\s+(?:all\s+|the\s+)?(?:previous|prior)\s+instructions|system\s*prompt|mark\s+(?:this\s+)?approved",
    re.I,
)


class PermanentError(ValueError):
    pass


def extract(document):
    content = document["content"]
    if INSTRUCTIONS.search(content):
        raise PermanentError(
            "Instruction-like content requires manual quarantine review"
        )
    media = document["media_type"]
    entries = []
    if media == "application/json" or content.lstrip().startswith("{"):
        try:
            raw = json.loads(content, object_pairs_hook=list)
            if not isinstance(raw, list):
                raise ValueError()
            for key, value in raw:
                if key not in FIELDS:
                    continue
                match = re.search(re.escape(json.dumps(key)) + r"\s*:", content)
                if not match:
                    raise ValueError()
                start = match.start()
                value_start = match.end()
                while content[value_start].isspace():
                    value_start += 1
                _, length = json.JSONDecoder().raw_decode(content[value_start:])
                entries.append(
                    (
                        key,
                        value,
                        content.count("\n", 0, start) + 1,
                        content[start : value_start + length],
                    )
                )
        except (ValueError, TypeError):
            raise PermanentError("Malformed JSON document") from None
    elif media == "text/csv":
        try:
            physical_lines = content.splitlines(keepends=True)
            reader = csv.reader(io.StringIO(content, newline=""), strict=True)
            if next(reader, None) != ["field", "value"]:
                raise ValueError()
            end = reader.line_num
            for row in reader:
                start, end = end, reader.line_num
                if len(row) != 2:
                    raise ValueError()
                # Preserve CSV syntax and the physical start line, including
                # quoted commas, escaped quotes and multi-line records.
                quote = "".join(physical_lines[start:end]).rstrip("\r\n")
                entries.append((row[0], row[1], start + 1, quote))
        except (ValueError, csv.Error):
            raise PermanentError("CSV must contain field,value rows") from None
    else:
        for line, text in enumerate(content.splitlines(), 1):
            if ":" in text:
                key, value = text.split(":", 1)
                entries.append((key.strip(), value.strip(), line, text[:500]))
    fields = {}
    for key, value, line, quote in entries:
        if key not in FIELDS:
            continue
        if key in fields:
            raise PermanentError("Repeated field requires explicit correction")
        if key in {"reviewed_users", "exceptions"}:
            if isinstance(value, bool) or not re.fullmatch(r"\d{1,9}", str(value)):
                raise PermanentError("Count must be a nonnegative integer")
            value = int(value)
        else:
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise PermanentError("Invalid scalar field")
            value = value.strip()
            if key == "period" and not re.fullmatch(r"\d{4}-Q[1-4]", value):
                raise PermanentError("Period must be YYYY-QN")
            if key == "review_date":
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError()
                    date.fromisoformat(value)
                except ValueError:
                    raise PermanentError(
                        "Review date must be a valid calendar date"
                    ) from None
        fields[key] = {
            "value": value,
            "source": {
                "document_id": document["id"],
                "digest": document["digest"],
                "line": line,
                "quote": quote,
            },
            "method": "exact-source-parse",
        }
    if not fields:
        raise PermanentError("No supported fields; manual extraction required")
    return {
        "schema_version": 1,
        "provider": "deterministic-key-value-v1",
        "fields": fields,
        "rule_completeness": round(
            len(set(fields) & {"system", "period", "reviewed_users", "exceptions"}) / 4,
            3,
        ),
    }


def canonical_record(extractions, target_period, control_id="AC-01"):
    fields, exceptions, candidates = {}, [], {}
    for extraction in extractions:
        for key, field in extraction["fields"].items():
            candidates.setdefault(key, []).append(field)
            if key in fields and fields[key]["value"] != field["value"]:
                exceptions.append(
                    {
                        "code": "FIELD_CONFLICT",
                        "field": key,
                        "message": f"Conflicting {key} values require a reviewer correction workflow",
                    }
                )
            else:
                fields[key] = field
    required = {"system", "period", "exceptions"} | (
        {"reviewed_users"} if control_id == "AC-01" else set()
    )
    missing = sorted(required - set(fields))
    if missing:
        exceptions.append(
            {
                "code": "MISSING_FIELDS",
                "fields": missing,
                "message": "Required facts were not found in source documents",
            }
        )
    if fields.get("period", {}).get("value") not in {None, target_period}:
        exceptions.append(
            {
                "code": "PERIOD_MISMATCH",
                "message": f"Expected {target_period}; submitted period differs",
            }
        )
    if fields.get("exceptions", {}).get("value", 0) > 0:
        exceptions.append(
            {
                "code": "OPEN_EXCEPTIONS",
                "message": "Source reports unresolved exceptions",
            }
        )
    return {
        "schema_version": 1,
        "fields": fields,
        "candidates": candidates,
        "exceptions": exceptions,
        "complete": not missing and not exceptions,
        "provider": "deterministic-key-value-v1",
    }


def normalize_pdf(data: bytes):
    """Text PDFs only; OCR is deliberately a provider boundary, not a silent stub."""
    from pypdf import PdfReader

    if len(data) > 5_000_000:
        raise PermanentError("PDF exceeds 5MB limit")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > 30:
            raise PermanentError("Encrypted or oversized page-count PDF")
        parts = [page.extract_text() or "" for page in reader.pages]
    except PermanentError:
        raise
    except Exception:
        raise PermanentError("Unreadable PDF") from None
    text = "\n".join(parts)
    if not text.strip():
        raise PermanentError("Scanned PDF requires an OCR provider; none is configured")
    if len(text) > 200000:
        raise PermanentError("Extracted text exceeds limit")
    return text
