from src.retrieval import Document, VectorRetriever


def scoped_sources(snapshot):
    rows = []
    for document in snapshot["documents"]:
        extraction = document.get("extraction") or {}
        for field, fact in extraction.get("fields", {}).items():
            source = fact["source"]
            rows.append(
                {
                    "source_id": f"{document['id']}:{field}",
                    "kind": "evidence",
                    "field": field,
                    "value": fact["value"],
                    "document_id": document["id"],
                    "filename": document["filename"],
                    "digest": source["digest"],
                    "line": source["line"],
                    "quote": source["quote"],
                }
            )
    if not rows:
        return []
    index = VectorRetriever(
        [Document(r["source_id"], "evidence", r["quote"]) for r in rows]
    )
    query = (
        snapshot.get("control_definition", {}).get("requirement", "")
        + " "
        + f"{snapshot['title']} system period reviewed users exceptions {snapshot['control_id']}"
    )
    ranked = index.retrieve(query, k=6)
    by_id = {r["source_id"]: r for r in rows}
    return [{**by_id[r.source_id], "score": r.score} for r in ranked]
