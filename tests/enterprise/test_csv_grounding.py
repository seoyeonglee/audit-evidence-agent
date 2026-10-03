import pytest
from src.platform.extraction import extract, canonical_record
from src.platform.service import digest
from src.enterprise.nodes import retrieve, assess, validate_grounding


@pytest.mark.parametrize(
    "system",
    [
        '"production-admin"',
        '"production,admin"',
        '"production ""admin"""',
        '"production\nadmin"',
    ],
)
def test_csv_original_record_spans_and_physical_lines(system):
    content = f"field,value\nsystem,{system}\nperiod,2026-Q3\nreviewed_users,84\nexceptions,0\n"
    document = {
        "id": "csv",
        "filename": "quoted.csv",
        "media_type": "text/csv",
        "content": content,
        "digest": digest(content),
    }
    parsed = extract(document)
    document["extraction"] = parsed
    canonical = canonical_record([parsed], "2026-Q3")
    assert canonical["complete"] is True
    for fact in parsed["fields"].values():
        source = fact["source"]
        assert source["quote"] in content
        assert (
            source["line"] == content.count("\n", 0, content.index(source["quote"])) + 1
        )
    state = {
        "snapshot": {
            "title": "Access",
            "control_id": "AC-01",
            "canonical": canonical,
            "documents": [document],
        },
        "findings": [],
    }
    state.update(retrieve(state))
    state.update(assess(state))
    assert validate_grounding(state)["grounding"]["valid"] is True
