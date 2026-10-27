from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.topic2_showcase.contracts import (
    CbrneStats,
    DatasetStats,
    LifecycleCase,
    LifecycleCaseId,
)


class AssetStoreError(RuntimeError):
    """Base exception for controlled showcase asset failures."""


class AssetNotFound(AssetStoreError):
    """Raised when a requested allowlisted asset is unavailable."""


class InvalidAssetManifest(AssetStoreError):
    """Raised when the manifest or a referenced asset is invalid."""


class AssetStore:
    def __init__(self, asset_root: Path | str):
        self.asset_root = Path(asset_root).expanduser().resolve()
        self._stats_cache: dict[
            Path, tuple[int, int, DatasetStats]
        ] = {}

    def lifecycle_cases(self) -> list[LifecycleCase]:
        raw_cases = self._manifest().get("lifecycle_cases")
        if not isinstance(raw_cases, list):
            raise InvalidAssetManifest(
                "manifest.lifecycle_cases must be a list"
            )
        try:
            return [LifecycleCase.model_validate(case) for case in raw_cases]
        except ValidationError as exc:
            raise InvalidAssetManifest(
                f"invalid lifecycle case: {exc}"
            ) from exc

    def lifecycle_path(self, case_id: LifecycleCaseId | str) -> Path:
        case = next(
            (item for item in self.lifecycle_cases() if item.id == case_id),
            None,
        )
        if case is None:
            raise AssetNotFound(f"unknown lifecycle case: {case_id}")
        return self._resolve_manifest_file(case.file)

    def cbrne_stats(self) -> CbrneStats:
        datasets = self._manifest().get("datasets")
        if not isinstance(datasets, dict):
            raise InvalidAssetManifest("manifest.datasets must be an object")

        full_path = self._dataset_path(datasets, "full")
        filtered_path = self._dataset_path(datasets, "filtered")
        return CbrneStats(
            full=self._cached_stats(full_path),
            filtered=self._cached_stats(filtered_path),
        )

    def _manifest(self) -> dict[str, Any]:
        manifest_path = self.asset_root / "manifest.json"
        try:
            raw = manifest_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AssetNotFound(
                f"asset manifest unavailable: {manifest_path}"
            ) from exc
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidAssetManifest(
                f"invalid JSON in {manifest_path.name}: {exc}"
            ) from exc
        if not isinstance(manifest, dict):
            raise InvalidAssetManifest("asset manifest must be an object")
        return manifest

    def _dataset_path(
        self, datasets: dict[str, Any], dataset_id: str
    ) -> Path:
        relative_path = datasets.get(dataset_id)
        if not isinstance(relative_path, str) or not relative_path:
            raise InvalidAssetManifest(
                f"manifest.datasets.{dataset_id} must be a file path"
            )
        return self._resolve_manifest_file(relative_path)

    def _resolve_manifest_file(self, relative_path: str) -> Path:
        raw_path = Path(relative_path)
        if raw_path.is_absolute():
            raise InvalidAssetManifest(
                f"absolute asset paths are not allowed: {relative_path}"
            )

        candidate = (self.asset_root / raw_path).resolve()
        if candidate != self.asset_root and self.asset_root not in candidate.parents:
            raise InvalidAssetManifest(
                f"asset path escapes configured root: {relative_path}"
            )
        if not candidate.is_file():
            raise AssetNotFound(f"asset file unavailable: {relative_path}")
        return candidate

    def _cached_stats(self, path: Path) -> DatasetStats:
        stat = path.stat()
        cached = self._stats_cache.get(path)
        if cached is not None:
            cached_mtime, cached_size, cached_stats = cached
            if (
                cached_mtime == stat.st_mtime_ns
                and cached_size == stat.st_size
            ):
                return cached_stats

        stats = self._scan_jsonl(path)
        self._stats_cache[path] = (stat.st_mtime_ns, stat.st_size, stats)
        return stats

    def _scan_jsonl(self, path: Path) -> DatasetStats:
        labels: Counter[str] = Counter()
        l2_categories: Counter[str] = Counter()
        source_benchmarks: Counter[str] = Counter()
        seed_types: Counter[str] = Counter()
        total = 0

        try:
            with path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise InvalidAssetManifest(
                            f"invalid JSON in {path.name}:{line_number}"
                        ) from exc
                    if not isinstance(record, dict):
                        raise InvalidAssetManifest(
                            f"record must be an object in "
                            f"{path.name}:{line_number}"
                        )

                    total += 1
                    self._count(labels, record.get("label"))
                    self._count(
                        l2_categories,
                        record.get("harm_category_L2"),
                    )
                    self._count(
                        source_benchmarks,
                        record.get("source_benchmark"),
                    )
                    self._count(seed_types, record.get("seed_type"))
        except OSError as exc:
            raise AssetNotFound(f"unable to read asset: {path}") from exc

        return DatasetStats(
            total=total,
            labels=dict(labels),
            l2_categories=dict(l2_categories),
            source_benchmarks=dict(source_benchmarks),
            seed_types=dict(seed_types),
        )

    @staticmethod
    def _count(counter: Counter[str], value: Any) -> None:
        if isinstance(value, str) and value:
            counter[value] += 1
