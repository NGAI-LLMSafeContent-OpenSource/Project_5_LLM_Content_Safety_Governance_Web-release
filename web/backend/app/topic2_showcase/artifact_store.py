from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any

from pydantic import ValidationError

from app.topic2_showcase.contracts import (
    PrerunMetadata,
    PrerunSummary,
    Readiness,
)


class ArtifactStoreError(RuntimeError):
    """Base exception for controlled pre-run artifact failures."""


class ArtifactNotFound(ArtifactStoreError):
    """Raised when a configured pre-run artifact is unavailable."""


class InvalidArtifact(ArtifactStoreError):
    """Raised when a pre-run artifact violates its contract."""


class ArtifactStore:
    def __init__(self, asset_root: Path | str):
        self.asset_root = Path(asset_root).expanduser().resolve()
        self.prerun_root = (self.asset_root / "prerun").resolve()

    def readiness(self) -> Readiness:
        try:
            self.active_summary()
        except ArtifactNotFound:
            return "missing"
        except InvalidArtifact:
            return "invalid"
        return "ready"

    def active_summary(self) -> PrerunSummary:
        run_dir = self._active_run_dir()
        metadata = self._metadata(run_dir)
        report_path = self._run_file(
            run_dir,
            metadata.report_file,
            "report_file",
        )
        lifecycle_path = self._run_file(
            run_dir,
            metadata.lifecycle_file,
            "lifecycle_file",
        )

        try:
            report = report_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ArtifactNotFound(
                f"report_file unavailable: {metadata.report_file}"
            ) from exc

        lifecycle = self._read_lifecycle(lifecycle_path)
        return PrerunSummary(
            metadata=metadata,
            report=report,
            lifecycle=lifecycle,
        )

    def _active_run_dir(self) -> Path:
        manifest = self._read_json_object(
            self.asset_root / "manifest.json",
            missing_message="showcase manifest unavailable",
            invalid_message="showcase manifest is invalid",
        )
        run_id = manifest.get("active_prerun")
        if not isinstance(run_id, str) or not run_id:
            raise ArtifactNotFound("manifest.active_prerun is not configured")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
            raise InvalidArtifact("active_prerun contains an invalid run id")

        run_dir = (self.prerun_root / run_id).resolve()
        if (
            run_dir == self.prerun_root
            or self.prerun_root not in run_dir.parents
        ):
            raise InvalidArtifact("active_prerun escapes prerun root")
        if not run_dir.is_dir():
            raise ArtifactNotFound(
                f"active_prerun directory unavailable: {run_id}"
            )
        return run_dir

    def _metadata(self, run_dir: Path) -> PrerunMetadata:
        metadata_path = run_dir / "run.json"
        raw_metadata = self._read_json_object(
            metadata_path,
            missing_message="run.json unavailable",
            invalid_message="run.json is invalid",
        )
        try:
            metadata = PrerunMetadata.model_validate(raw_metadata)
        except ValidationError as exc:
            raise InvalidArtifact(f"invalid run metadata: {exc}") from exc
        if metadata.run_id != run_dir.name:
            raise InvalidArtifact(
                "run metadata id does not match active_prerun"
            )
        return metadata

    def _run_file(
        self,
        run_dir: Path,
        configured_path: str,
        field_name: str,
    ) -> Path:
        if not isinstance(configured_path, str) or not configured_path:
            raise InvalidArtifact(f"{field_name} must be a file path")
        windows_path = PureWindowsPath(configured_path)
        posix_path = PurePosixPath(configured_path.replace("\\", "/"))
        if (
            windows_path.is_absolute()
            or posix_path.is_absolute()
            or ".." in posix_path.parts
        ):
            raise InvalidArtifact(f"{field_name} escapes active run")

        candidate = (run_dir / Path(configured_path)).resolve()
        if candidate == run_dir or run_dir not in candidate.parents:
            raise InvalidArtifact(f"{field_name} escapes active run")
        if not candidate.is_file():
            raise ArtifactNotFound(
                f"{field_name} unavailable: {configured_path}"
            )
        return candidate

    def _read_lifecycle(self, path: Path) -> list[dict[str, Any]]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ArtifactNotFound(
                f"lifecycle_file unavailable: {path.name}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise InvalidArtifact("lifecycle_file contains invalid JSON") from exc

        if not isinstance(value, list) or not all(
            isinstance(item, dict) for item in value
        ):
            raise InvalidArtifact(
                "lifecycle_file must contain an array of objects"
            )
        return value

    @staticmethod
    def _read_json_object(
        path: Path,
        *,
        missing_message: str,
        invalid_message: str,
    ) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ArtifactNotFound(missing_message) from exc
        except json.JSONDecodeError as exc:
            raise InvalidArtifact(invalid_message) from exc
        if not isinstance(value, dict):
            raise InvalidArtifact(invalid_message)
        return value
