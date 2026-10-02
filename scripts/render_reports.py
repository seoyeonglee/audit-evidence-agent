"""Render exact measured values from JSON, never invented dashboard figures."""

import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
b = json.loads((root / "docs/reports/benchmark.json").read_text())
e = json.loads((root / "docs/reports/evaluation.json").read_text())
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "text.color": "#dce5f1",
        "axes.labelcolor": "#adbad0",
        "xtick.color": "#adbad0",
        "ytick.color": "#adbad0",
        "axes.edgecolor": "#324158",
        "axes.facecolor": "#142136",
        "figure.facecolor": "#0b121e",
        "font.size": 11,
    }
)
fig, ax = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [1, 1.1]})
values = [b["read_p50_ms"], b["read_p95_ms"], b["read_p99_ms"]]
ax[0].barh(
    ["p50", "p95", "p99"], values, color=["#8ee1bc", "#8badde", "#e6b68d"], height=0.52
)
ax[0].set_xlim(0, max(values) * 1.35)
for i, v in enumerate(values):
    ax[0].text(
        v + max(values) * 0.025, i, f"{v:.2f} ms", va="center", fontweight="bold"
    )
ax[0].set_title(
    "Record-read latency / actual ASGI requests", loc="left", pad=20, fontsize=13
)
ax[0].set_xlabel(
    f"{b['read_requests']} requests · {b['read_concurrency']} concurrent clients · {b['read_errors']} errors"
)
ax[0].invert_yaxis()
ax[1].barh(
    ["Exception recall", "Quarantine recall", "Field exact match"],
    [
        e["exception_recall"] * 100,
        e["quarantine_recall"] * 100,
        e["field_exact_match"] * 100,
    ],
    height=0.52,
    color="#8ee1bc",
)
ax[1].set_xlim(0, 125)
ax[1].set_xticks([0, 25, 50, 75, 100])
ax[1].set_xlabel("Offline structured fixtures / rules, not an LLM benchmark")
for i, value in enumerate(
    [e["exception_recall"], e["quarantine_recall"], e["field_exact_match"]]
):
    ax[1].text(
        value * 100 + 3, i, f"{value * 100:.1f}%", va="center", fontweight="bold"
    )
ax[1].set_title(
    f"{e['cases']} synthetic cases / {e['expected_fields']} labeled fields",
    loc="left",
    pad=20,
    fontsize=13,
)
ax[1].invert_yaxis()
for a in ax:
    a.spines[["top", "right"]].set_visible(False)
    a.grid(axis="x", alpha=0.13)
    a.set_axisbelow(True)
fig.suptitle(
    "Measured engineering evidence",
    x=0.045,
    ha="left",
    fontsize=22,
    fontweight="bold",
    y=0.98,
)
fig.text(
    0.045,
    0.018,
    f"{b['record_count']} canonical records · {b['document_jobs']:,} persisted jobs · SQLite WAL · single local host · measured {b['measured_at'][:10]}",
    fontsize=10,
    color="#8ea3c3",
)
fig.tight_layout(rect=[0.02, 0.08, 0.99, 0.90])
fig.savefig(root / "docs/reports/measurement-chart.png", dpi=150)
