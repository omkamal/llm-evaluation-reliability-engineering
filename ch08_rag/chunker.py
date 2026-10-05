"""Split a document into overlapping chunks of words (stdlib only)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    id: str          # "returns#1": document id, then position
    doc_id: str
    version: int     # the document version this text came from
    text: str


def chunk_doc(doc, size=48, overlap=12):
    """Windows of `size` words; each starts `size - overlap` on."""
    if not 0 <= overlap < size:
        raise ValueError("overlap must be smaller than the chunk size")
    words = doc.text.split()
    step = size - overlap
    chunks = []
    for n, start in enumerate(range(0, len(words), step)):
        window = words[start:start + size]
        chunks.append(Chunk(f"{doc.id}#{n}", doc.id, doc.version,
                            " ".join(window)))
        if start + size >= len(words):   # this window reached the end
            break
    return chunks


def chunk_all(docs, size=48, overlap=12):
    return [c for doc in docs for c in chunk_doc(doc, size, overlap)]
