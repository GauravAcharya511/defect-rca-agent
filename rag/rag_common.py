"""Shared pieces for the retrieval layer: DB connection, chunking, embedding backends."""
import hashlib
import os
import re

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

DSN = os.getenv("PG_DSN", "postgresql://rca:rca@localhost:5433/rca")
DIM = 384
MAX_CHUNK_CHARS = 700  # MiniLM truncates at 256 word-pieces (~1,000 chars); stay well under


def connect():
    conn = psycopg.connect(DSN)
    register_vector(conn)
    return conn


def chunk_text(text: str) -> list[str]:
    """Split a narrative on sentence boundaries into chunks of <= MAX_CHUNK_CHARS."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for s in sentences:
        while len(s) > MAX_CHUNK_CHARS:  # a single run-on "sentence"
            if current:
                chunks.append(current)
                current = ""
            chunks.append(s[:MAX_CHUNK_CHARS])
            s = s[MAX_CHUNK_CHARS:]
        if current and len(current) + 1 + len(s) > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = s
        else:
            current = f"{current} {s}".strip()
    if current:
        chunks.append(current)
    return chunks


def source_hash(description: str, component_groups: list[str]) -> str:
    return hashlib.sha256(f"{description}|{','.join(sorted(component_groups))}".encode()).hexdigest()


class HashingBackend:
    """Lexical baseline: signed feature hashing of word tokens. No model download needed."""
    name = "hashing-bow-384"

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), DIM), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:8], "little")
                out[i, h % DIM] += 1.0 if (h >> 63) & 1 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class MiniLMBackend:
    """Semantic embeddings: sentence-transformers/all-MiniLM-L6-v2 (384-d), normalized."""
    name = "all-MiniLM-L6-v2"

    def __init__(self, batch_size: int = 64):
        from sentence_transformers import SentenceTransformer  # heavy import, only when used
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.batch_size = batch_size

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                 show_progress_bar=False, convert_to_numpy=True).astype(np.float32)


def get_backend(name: str):
    if name == "minilm":
        return MiniLMBackend()
    if name == "hash":
        return HashingBackend()
    raise ValueError(f"unknown backend {name!r} (use 'minilm' or 'hash')")
