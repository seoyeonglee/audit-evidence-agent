def markdown_report(report):
    lines = [
        "# Audit evidence review",
        f"Run: {report['run_id']}",
        f"Control: {report['control_id']}",
        f"Snapshot version: {report['snapshot_version']}",
        f"Provider: {report['provider']}",
        "",
        f"Decision: {report['review']['decision']}",
        f"Reviewer: {report['review']['reviewer']}",
        f"Feedback: {report['review']['feedback']}",
        "",
        "## Exact source excerpts",
    ]
    for source in report["sources"]:
        lines.extend(
            [
                f"- {source['filename']} / line {source['line']} / {source['digest']}",
                f"> {source['quote']}",
            ]
        )
    lines.extend(["", report["notice"]])
    return "\n".join(lines)
