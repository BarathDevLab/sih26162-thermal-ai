"""Cross-platform hashing helpers for packaged runtime artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Set, Tuple


# Git may materialize these files with LF or CRLF depending on checkout settings.
# Binary model/data artifacts must always remain byte-for-byte identical.
_TEXT_ARTIFACT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
_VARIANT_CACHE: Dict[str, Tuple[int, int, Set[str]]] = {}


def checksum_matches(path: Path, expected: str) -> bool:
    """Match an exact binary hash or a newline-only text checkout variant."""
    return expected.lower() in sha256_variants(path)


def sha256_variants(path: Path) -> Set[str]:
    """Return acceptable hashes without weakening binary artifact integrity."""
    stat = path.stat()
    key = str(path.resolve())
    signature = (stat.st_size, stat.st_mtime_ns)
    cached = _VARIANT_CACHE.get(key)
    if cached and cached[:2] == signature:
        return cached[2]

    payload = path.read_bytes()
    variants = {_digest(payload)}
    if path.suffix.lower() in _TEXT_ARTIFACT_SUFFIXES:
        lf_payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        variants.add(_digest(lf_payload))
        variants.add(_digest(lf_payload.replace(b"\n", b"\r\n")))

    _VARIANT_CACHE[key] = (stat.st_size, stat.st_mtime_ns, variants)
    return variants


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
