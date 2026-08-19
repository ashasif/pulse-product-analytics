"""Integrity-controlled access to frozen Phase 5 and Phase 6 evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_PHASE6_FINAL_RESULTS_SHA256 = (
    "ec1eadb21395b8dfda95399766e1993781c95b9621d8c6d500c9a0a1f429737e"
)

PHASE5_DECISIONS_PATH = Path(
    "outputs/phase5/portfolio/phase5_experiment_decisions.json"
)

PHASE6_MANIFEST_PATH = Path(
    "outputs/phase6/portfolio/phase6_manifest.json"
)


class EvidenceIntegrityError(RuntimeError):
    """Raised when frozen portfolio evidence violates its contract."""


def repository_root() -> Path:
    """Return the repository root independently of the process cwd."""

    return Path(__file__).resolve().parents[2]


def resolve_repo_path(
    relative_path: str | Path,
    *,
    repo_root: Path | None = None,
) -> Path:
    """Resolve a repository-relative path without permitting escape."""

    root = (
        repository_root()
        if repo_root is None
        else Path(repo_root).resolve()
    )

    supplied = Path(relative_path)

    if supplied.is_absolute():
        raise EvidenceIntegrityError(
            "Evidence paths must be repository-relative."
        )

    candidate = (root / supplied).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise EvidenceIntegrityError(
            "Evidence path escapes the repository root."
        ) from exc

    return candidate


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file."""

    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_json_evidence(
    relative_path: str | Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Load a repository-relative UTF-8 JSON evidence artifact."""

    path = resolve_repo_path(
        relative_path,
        repo_root=repo_root,
    )

    if not path.is_file():
        raise EvidenceIntegrityError(
            f"Evidence file not found: {relative_path}"
        )

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceIntegrityError(
            f"Evidence file is not valid UTF-8 JSON: {relative_path}"
        ) from exc

    if not isinstance(payload, dict):
        raise EvidenceIntegrityError(
            f"Evidence root must be an object: {relative_path}"
        )

    return payload


def load_phase5_evidence(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Load the frozen Phase 5 experiment-decision evidence."""

    payload = load_json_evidence(
        PHASE5_DECISIONS_PATH,
        repo_root=repo_root,
    )

    if payload.get("phase") != 5:
        raise EvidenceIntegrityError(
            "Phase 5 evidence has an unexpected phase identifier."
        )

    if payload.get("synthetic_data") is not True:
        raise EvidenceIntegrityError(
            "Phase 5 evidence must remain marked as synthetic."
        )

    decisions = payload.get("decisions")

    if not isinstance(decisions, list):
        raise EvidenceIntegrityError(
            "Phase 5 evidence decisions must be a list."
        )

    return payload


def load_phase6_evidence(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Load Phase 6 manifest and verify the frozen final-results hash."""

    manifest = load_json_evidence(
        PHASE6_MANIFEST_PATH,
        repo_root=repo_root,
    )

    if manifest.get("phase") != 6:
        raise EvidenceIntegrityError(
            "Phase 6 evidence has an unexpected phase identifier."
        )

    if manifest.get("selected_model") != "behavioural_logistic":
        raise EvidenceIntegrityError(
            "Phase 6 selected model no longer matches the locked contract."
        )

    if manifest.get("calibration") != "uncalibrated":
        raise EvidenceIntegrityError(
            "Phase 6 calibration no longer matches the locked contract."
        )

    frozen = manifest.get("frozen_results")

    if not isinstance(frozen, dict):
        raise EvidenceIntegrityError(
            "Phase 6 frozen-results metadata is missing."
        )

    manifest_sha = frozen.get("sha256")

    if manifest_sha != EXPECTED_PHASE6_FINAL_RESULTS_SHA256:
        raise EvidenceIntegrityError(
            "Phase 6 manifest SHA-256 does not match the locked digest."
        )

    frozen_path = frozen.get("path")

    if not isinstance(frozen_path, str) or not frozen_path:
        raise EvidenceIntegrityError(
            "Phase 6 frozen-results path is invalid."
        )

    final_results_path = resolve_repo_path(
        frozen_path,
        repo_root=repo_root,
    )

    if not final_results_path.is_file():
        raise EvidenceIntegrityError(
            "Phase 6 frozen final-results file is missing."
        )

    actual_sha = sha256_file(final_results_path)

    if actual_sha != EXPECTED_PHASE6_FINAL_RESULTS_SHA256:
        raise EvidenceIntegrityError(
            "Phase 6 frozen final-results SHA-256 verification failed."
        )

    if frozen.get("status") != "OPEN AND FROZEN":
        raise EvidenceIntegrityError(
            "Phase 6 final holdout is no longer marked OPEN AND FROZEN."
        )

    return {
        "manifest": manifest,
        "verified_final_results_sha256": actual_sha,
    }


def load_portfolio_evidence(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Load integrity-checked frozen evidence used by the UI."""

    return {
        "phase5": load_phase5_evidence(
            repo_root=repo_root,
        ),
        "phase6": load_phase6_evidence(
            repo_root=repo_root,
        ),
    }