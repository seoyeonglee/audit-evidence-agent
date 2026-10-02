from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from .schemas import RetrievedChunk
except ImportError:
    from schemas import RetrievedChunk


@dataclass
class Document:
    source_id: str
    document_type: str
    text: str


class VectorRetriever:
    """Small local vector index for a reproducible portfolio demo.

    TF-IDF is intentionally used instead of an external vector database so the
    repository runs without infrastructure or paid APIs. The interface mirrors
    the retrieve/top-k behavior used with production vector stores.
    """

    def __init__(self, documents: list[Document]):
        if not documents:
            raise ValueError("VectorRetriever requires at least one document.")
        self.documents = documents
        self._by_id = {doc.source_id: doc for doc in documents}
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        self.matrix = self.vectorizer.fit_transform(
            [doc.text for doc in documents]
        )

    def get(self, source_id: str) -> RetrievedChunk | None:
        doc = self._by_id.get(source_id)
        if not doc:
            return None
        return RetrievedChunk(
            source_id=doc.source_id,
            document_type=doc.document_type,
            text=doc.text,
            score=1.0,
        )

    def retrieve(
        self,
        query: str,
        k: int = 6,
        document_types: set[str] | None = None,
    ) -> list[RetrievedChunk]:
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix)[0]

        ranked: list[tuple[float, Document]] = []
        for score, doc in zip(scores, self.documents):
            if document_types and doc.document_type not in document_types:
                continue
            ranked.append((float(score), doc))
        ranked.sort(key=lambda item: item[0], reverse=True)

        return [
            RetrievedChunk(
                source_id=doc.source_id,
                document_type=doc.document_type,
                text=doc.text,
                score=round(score, 6),
            )
            for score, doc in ranked[:k]
        ]


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value or "section"


def _knowledge_documents(path: str | Path) -> list[Document]:
    root = Path(path)
    if not root.exists():
        return []

    documents: list[Document] = []
    for file_path in sorted(root.glob("*.md")):
        text = file_path.read_text(encoding="utf-8")
        sections = re.split(r"(?m)^##\s+", text)
        preamble = sections[0].strip()
        if preamble:
            documents.append(
                Document(
                    source_id=f"kb:{file_path.stem}:overview",
                    document_type="knowledge",
                    text=preamble,
                )
            )
        for section in sections[1:]:
            lines = section.strip().splitlines()
            if not lines:
                continue
            heading = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            documents.append(
                Document(
                    source_id=f"kb:{file_path.stem}:{_slug(heading)}",
                    document_type="knowledge",
                    text=f"{heading}\n{body}",
                )
            )
    return documents


def build_documents(
    controls: pd.DataFrame,
    evidence_index: pd.DataFrame,
    evidence_texts: dict[str, str],
    knowledge_base_dir: str | Path = "data/knowledge_base",
) -> list[Document]:
    documents: list[Document] = []

    for _, control in controls.iterrows():
        source_id = f"control:{control['control_id']}"
        documents.append(
            Document(
                source_id=source_id,
                document_type="control",
                text=(
                    f"Control {control['control_id']}: {control['title']}\n"
                    f"Requirement: {control['requirement']}\n"
                    f"Expected evidence: {control['required_evidence_type']}\n"
                    f"Target period: {control['target_period']}\n"
                    f"Keywords: {control['keywords']}"
                ),
            )
        )

    for _, row in evidence_index.iterrows():
        evidence_id = str(row["evidence_id"])
        documents.append(
            Document(
                source_id=f"evidence:{evidence_id}",
                document_type="evidence",
                text=(
                    f"Evidence {evidence_id}\n"
                    f"Type: {row['evidence_type']}\n"
                    f"Period: {row['period']}\n"
                    f"Owner: {row['owner']}\n"
                    f"{evidence_texts.get(evidence_id, '')}"
                ),
            )
        )

    documents.extend(_knowledge_documents(knowledge_base_dir))
    return documents
