"""Regression tests for runtime artifact checksum readiness."""

import hashlib
import json

from backend.app.services import stack_readiness


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_manifest(root, *, required_path: str, optional_path: str) -> None:
    manifest_path = root / "backend/config/active_stack_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "artifacts": [
                    {"repo_path": required_path, "required": True},
                    {"repo_path": optional_path, "required": False},
                ]
            }
        ),
        encoding="utf-8",
    )


def test_missing_optional_artifact_does_not_fail_core_checksum_gate(tmp_path, monkeypatch):
    required_path = "backend/models/core.joblib"
    optional_path = "backend/models/prithvi/weights.pt"
    required_payload = b"frozen-core-model"
    required_file = tmp_path / required_path
    required_file.parent.mkdir(parents=True)
    required_file.write_bytes(required_payload)
    _write_manifest(tmp_path, required_path=required_path, optional_path=optional_path)
    (tmp_path / "SHA256SUMS.txt").write_text(
        f"{_sha256(required_payload)}  {required_path}\n"
        f"{_sha256(b'optional-weights')}  {optional_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stack_readiness, "PROJECT_ROOT", tmp_path)

    assert stack_readiness._verify_declared_checksums() == []


def test_missing_required_artifact_still_fails_checksum_gate(tmp_path, monkeypatch):
    required_path = "backend/models/core.joblib"
    optional_path = "backend/models/prithvi/weights.pt"
    _write_manifest(tmp_path, required_path=required_path, optional_path=optional_path)
    (tmp_path / "SHA256SUMS.txt").write_text(
        f"{_sha256(b'frozen-core-model')}  {required_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stack_readiness, "PROJECT_ROOT", tmp_path)

    assert stack_readiness._verify_declared_checksums() == [required_path]


def test_corrupt_optional_artifact_is_reported_when_installed(tmp_path, monkeypatch):
    required_path = "backend/models/core.joblib"
    optional_path = "backend/models/prithvi/weights.pt"
    optional_file = tmp_path / optional_path
    optional_file.parent.mkdir(parents=True)
    optional_file.write_bytes(b"corrupt-weights")
    _write_manifest(tmp_path, required_path=required_path, optional_path=optional_path)
    (tmp_path / "SHA256SUMS.txt").write_text(
        f"{_sha256(b'expected-weights')}  {optional_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stack_readiness, "PROJECT_ROOT", tmp_path)

    assert stack_readiness._verify_declared_checksums() == [optional_path]


def test_text_artifact_checksum_accepts_lf_crlf_checkout_difference(tmp_path, monkeypatch):
    required_path = "backend/config/model_b.json"
    optional_path = "backend/models/prithvi/weights.pt"
    required_file = tmp_path / required_path
    required_file.parent.mkdir(parents=True)
    required_file.write_bytes(b'{\r\n  "state": "ACTIVE"\r\n}\r\n')
    _write_manifest(tmp_path, required_path=required_path, optional_path=optional_path)
    lf_payload = b'{\n  "state": "ACTIVE"\n}\n'
    (tmp_path / "SHA256SUMS.txt").write_text(
        f"{_sha256(lf_payload)}  {required_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stack_readiness, "PROJECT_ROOT", tmp_path)

    assert stack_readiness._verify_declared_checksums() == []


def test_binary_artifact_checksum_remains_byte_exact(tmp_path, monkeypatch):
    required_path = "backend/models/core.joblib"
    optional_path = "backend/models/prithvi/weights.pt"
    required_file = tmp_path / required_path
    required_file.parent.mkdir(parents=True)
    required_file.write_bytes(b"binary\r\npayload")
    _write_manifest(tmp_path, required_path=required_path, optional_path=optional_path)
    lf_hash = _sha256(b"binary\npayload")
    (tmp_path / "SHA256SUMS.txt").write_text(
        f"{lf_hash}  {required_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stack_readiness, "PROJECT_ROOT", tmp_path)

    assert stack_readiness._verify_declared_checksums() == [required_path]
