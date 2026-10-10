"""Opt-in learned embeddings, isolated from the default offline deterministic index.

FABRIC_EMBEDDING_BACKEND=hash (default) or sentence-transformers.
For learned embeddings, install `.[semantic]` and configure an available model.
No automatic model downloading unless FABRIC_ALLOW_MODEL_DOWNLOAD=1.
"""
from __future__ import annotations
from functools import lru_cache
import os
from .core import vector


@lru_cache(maxsize=2)
def _encoder(model_name: str, allow_download: bool):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError('For local semantic embeddings: pip install -e ".[semantic]"') from exc
    return SentenceTransformer(model_name, local_files_only=not allow_download)


def embed(text: str) -> list[float]:
    backend = os.environ.get("FABRIC_EMBEDDING_BACKEND", "hash")
    if backend == "hash":
        return vector(text)
    if backend == "sentence-transformers":
        model = os.environ.get("FABRIC_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        allow_download = os.environ.get("FABRIC_ALLOW_MODEL_DOWNLOAD") == "1"
        result = _encoder(model,allow_download).encode(text, normalize_embeddings=True)
        return result.tolist()
    raise ValueError("unknown embedding backend; choose hash or sentence-transformers")
