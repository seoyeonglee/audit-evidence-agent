from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_controls(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path).fillna("")
    required = {
        "control_id",
        "title",
        "requirement",
        "required_evidence_type",
        "target_period",
        "keywords",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Controls file missing columns: {sorted(missing)}")
    return df


def load_evidence_index(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path).fillna("")
    required = {
        "evidence_id",
        "filename",
        "evidence_type",
        "period",
        "owner",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Evidence index missing columns: {sorted(missing)}")
    return df


def load_evidence_texts(
    index_df: pd.DataFrame, evidence_dir: str | Path
) -> dict[str, str]:
    evidence_dir = Path(evidence_dir)
    texts: dict[str, str] = {}

    for row in index_df.itertuples(index=False):
        path = evidence_dir / str(row.filename)
        texts[str(row.evidence_id)] = path.read_text(
            encoding="utf-8"
        )

    return texts
