"""Versioned topic3 risk Benchmark asset series: registry, version resolution and
same-version evaluation results.

This module is the domain source of truth for which topic3 risk asset is
current, how an explicit asset version is resolved, and which evaluation runs
belong to the selected asset. Version-specific import code (v6 today) only
registers assets here.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BenchmarkAsset,
    BenchmarkAssetSeries,
    BenchmarkAssetVersion,
    utc_now,
)
from app.services.benchmark_topic3_risk_identity import (
    SERIES_ID,
    read_json_object,
    sha256_file,
)
from app.services.benchmark_topic3_risk_metrics import (
    PRIMARY_METRICS,
    model_display_name,
    primary_metric_values,
    supporting_metrics,
)


SERIES_NAME = "课题三风险分级分类 Benchmark"
SOURCE_MODE = "prerun_snapshot"
BENCHMARK_TYPE = "risk_content_generation"
RESULT_SOURCE = "topic3_prerun"
EVAL_MODE = "imported_result"

# Assets imported before the series existed carry no series_id in their manifest.
LEGACY_V6_RELEASE_KIND = "official_v6_benchmark"
LEGACY_V6_ASSET_ID = "Risk_Hierarchical_Classification_Benchmark_v6"
LEGACY_V6_ASSET_VERSION = "v6"
# Manifest ``files`` keys of the content file that ``asset_sha256`` hashes.
# Published v7+ assets declare ``content_csv``. Historical v6 manifests declare
# ``v6_csv`` and still register through the same check. ``content_csv`` wins
# when both are present so a v7 CSV is not disguised as the v6 key.
CONTENT_FILE_KEYS = ("content_csv", "v6_csv")
CONTENT_FILE_KEY = "v6_csv"

AssetStatus = Literal["current", "historical", "unregistered"]


class BenchmarkTopic3RiskSeriesError(RuntimeError):
    """Raised when a topic3 risk asset version cannot be registered or resolved."""


class BenchmarkTopic3RiskSeriesNotFoundError(BenchmarkTopic3RiskSeriesError):
    """Raised when the requested topic3 risk asset version does not exist."""


@dataclass(frozen=True)
class ResolvedTopic3RiskAsset:
    asset: BenchmarkAsset
    asset_version: str | None
    asset_sha256: str
    asset_status: AssetStatus

    def identity(self) -> dict[str, Any]:
        return {
            "series_id": SERIES_ID,
            "asset_id": self.asset.asset_id,
            "asset_version": self.asset_version,
            "asset_sha256": self.asset_sha256,
            "asset_status": self.asset_status,
        }


def is_series_manifest(manifest: dict[str, Any]) -> bool:
    if manifest.get("benchmark_type") != BENCHMARK_TYPE:
        return False
    return (
        manifest.get("series_id") == SERIES_ID
        or manifest.get("release_kind") == LEGACY_V6_RELEASE_KIND
    )


def is_legacy_v6_manifest(manifest: dict[str, Any]) -> bool:
    return (
        manifest.get("benchmark_type") == BENCHMARK_TYPE
        and manifest.get("release_kind") == LEGACY_V6_RELEASE_KIND
    )


def normalize_asset_version(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip().lower()


def loads_json_object(value: str | None) -> dict[str, Any]:
    """Lenient JSON object parse: anything but a JSON object yields ``{}``."""
    try:
        payload = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_json_object(path: Path, display_name: str) -> dict[str, Any]:
    return read_json_object(path, display_name, BenchmarkTopic3RiskSeriesError)


def _io_path(path: Path) -> Path:
    """Return a Windows extended path so valid long run ids remain readable."""

    if os.name != "nt":
        return path
    resolved = str(path.resolve())
    if resolved.startswith("\\\\?\\"):
        return Path(resolved)
    if resolved.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + resolved[2:])
    return Path("\\\\?\\" + resolved)


def manifest_sha256(asset: BenchmarkAsset) -> str:
    """Content hash the asset manifest claims; not trusted for registered assets."""
    return str(loads_json_object(asset.manifest_json).get("asset_sha256") or "")


def _declared_content_file(files: Any) -> str | None:
    if not isinstance(files, dict):
        return None
    for key in CONTENT_FILE_KEYS:
        name = files.get(key)
        if isinstance(name, str) and name.strip():
            return name
    return None


def _verified_content_sha256(asset: BenchmarkAsset) -> str:
    """Hash of the asset's declared content file, which must equal its claimed hash."""
    manifest = loads_json_object(asset.manifest_json)
    claimed = str(manifest.get("asset_sha256") or "")
    files = manifest.get("files")
    content_name = _declared_content_file(files)
    if not claimed or content_name is None:
        raise BenchmarkTopic3RiskSeriesError(
            f"asset declares no content file and hash: {asset.asset_id}"
        )
    content_path = Path(asset.artifact_dir) / content_name
    try:
        actual = sha256_file(content_path)
    except OSError as exc:
        raise BenchmarkTopic3RiskSeriesError(
            f"asset content file is unreadable: {content_path}"
        ) from exc
    if actual != claimed:
        raise BenchmarkTopic3RiskSeriesError(
            f"asset content file {content_name} does not match its asset_sha256: "
            f"{asset.asset_id}"
        )
    return actual


async def register_asset_version(
    db: AsyncSession,
    *,
    asset: BenchmarkAsset,
    asset_version: str,
    make_current: bool,
) -> BenchmarkAssetVersion:
    """Register ``asset`` as ``asset_version`` of the series without committing.

    The caller owns the transaction so that a publish can switch the asset and
    its same-version results atomically. Re-registering the same asset with the
    same version and content hash is idempotent.
    """
    version = normalize_asset_version(asset_version)
    if not version:
        raise BenchmarkTopic3RiskSeriesError("asset_version must not be empty")
    content_sha256 = _verified_content_sha256(asset)

    existing = await db.get(BenchmarkAssetVersion, asset.asset_id)
    if existing is not None:
        if (
            existing.series_id != SERIES_ID
            or existing.asset_version != version
            or existing.content_sha256 != content_sha256
        ):
            raise BenchmarkTopic3RiskSeriesError(
                f"asset is already registered with a different identity: {asset.asset_id}"
            )
        row = existing
    else:
        if await _version_row(db, version) is not None:
            raise BenchmarkTopic3RiskSeriesError(
                f"asset version already registered: {version}"
            )
        row = BenchmarkAssetVersion(
            asset_id=asset.asset_id,
            series_id=SERIES_ID,
            asset_version=version,
            content_sha256=content_sha256,
            registered_at=utc_now(),
        )
        db.add(row)

    series = await _get_or_create_series(db)
    if make_current or not series.current_asset_id:
        series.current_asset_id = asset.asset_id
        series.updated_at = utc_now()
    await db.flush()
    return row


async def register_legacy_v6_if_unclaimed(db: AsyncSession, asset: BenchmarkAsset) -> bool:
    """Register a v6 asset as the series' v6 version unless another asset holds it."""
    if await db.get(BenchmarkAssetVersion, asset.asset_id) is not None:
        return False
    if await _version_row(db, LEGACY_V6_ASSET_VERSION) is not None:
        return False
    await register_asset_version(
        db, asset=asset, asset_version=LEGACY_V6_ASSET_VERSION, make_current=False
    )
    return True


async def ensure_series_registered(db: AsyncSession) -> None:
    """Idempotently register an already-imported v6 asset for existing databases.

    Prefers the canonical v6 asset id, else the earliest imported v6 asset. The
    v6 asset only becomes current when the series has no current version.
    """
    registered = await _version_row(db, LEGACY_V6_ASSET_VERSION)
    if registered is not None:
        series = await _get_or_create_series(db)
        if series.current_asset_id:
            return
        series.current_asset_id = registered.asset_id
        series.updated_at = utc_now()
    else:
        candidates = [
            asset
            for asset in (
                await db.execute(
                    select(BenchmarkAsset)
                    .where(BenchmarkAsset.source_mode == SOURCE_MODE)
                    .order_by(BenchmarkAsset.id)
                )
            ).scalars()
            if is_legacy_v6_manifest(loads_json_object(asset.manifest_json))
        ]
        if not candidates:
            return
        candidates.sort(key=lambda asset: asset.asset_id != LEGACY_V6_ASSET_ID)
        await register_legacy_v6_if_unclaimed(db, candidates[0])
    await db.commit()


async def resolve_asset(
    db: AsyncSession,
    *,
    asset_version: str | None = None,
    asset_id: str | None = None,
) -> ResolvedTopic3RiskAsset:
    """Benchmark version resolution: unspecified -> current asset; explicit -> that asset."""
    version = normalize_asset_version(asset_version)
    explicit_asset_id = asset_id.strip() if asset_id and asset_id.strip() else None
    series = await db.get(BenchmarkAssetSeries, SERIES_ID)
    if series is None or not series.current_asset_id:
        series = await _register_on_demand(db)

    if explicit_asset_id:
        row = await db.get(BenchmarkAssetVersion, explicit_asset_id)
        if row is None or row.series_id != SERIES_ID:
            raise BenchmarkTopic3RiskSeriesNotFoundError(
                f"asset is not a registered topic3 risk benchmark version: {explicit_asset_id}"
            )
        if version and row.asset_version != version:
            raise BenchmarkTopic3RiskSeriesError(
                "asset_id and asset_version refer to different assets"
            )
    elif version:
        row = await _version_row(db, version)
        if row is None:
            raise BenchmarkTopic3RiskSeriesNotFoundError(
                f"topic3 risk benchmark asset version not found: {version}"
            )
    else:
        current_id = series.current_asset_id if series is not None else None
        row = await db.get(BenchmarkAssetVersion, current_id) if current_id else None
        if row is None:
            raise BenchmarkTopic3RiskSeriesNotFoundError(
                "no current topic3 risk benchmark asset"
            )

    asset = await _get_asset(db, row.asset_id)
    if asset is None:
        raise BenchmarkTopic3RiskSeriesNotFoundError(f"asset not found: {row.asset_id}")
    if manifest_sha256(asset) != row.content_sha256:
        raise BenchmarkTopic3RiskSeriesError(
            f"asset content hash no longer matches its registered version: {row.asset_id}"
        )
    return ResolvedTopic3RiskAsset(
        asset=asset,
        asset_version=row.asset_version,
        asset_sha256=row.content_sha256,
        asset_status=_status(series, row.asset_id),
    )


async def _register_on_demand(db: AsyncSession) -> BenchmarkAssetSeries | None:
    """Retry startup registration so a failed or late v6 registration surfaces here."""
    try:
        await ensure_series_registered(db)
    except BenchmarkTopic3RiskSeriesError as exc:
        await db.rollback()
        raise BenchmarkTopic3RiskSeriesError(
            f"topic3 risk benchmark asset could not be registered: {exc}"
        ) from exc
    return await db.get(BenchmarkAssetSeries, SERIES_ID)


async def describe_asset(db: AsyncSession, asset: BenchmarkAsset) -> ResolvedTopic3RiskAsset:
    """Identity of an asset addressed by id through a legacy per-asset endpoint."""
    row = await db.get(BenchmarkAssetVersion, asset.asset_id)
    if row is None or row.series_id != SERIES_ID:
        return ResolvedTopic3RiskAsset(
            asset=asset,
            asset_version=None,
            asset_sha256=manifest_sha256(asset),
            asset_status="unregistered",
        )
    return await resolve_asset(db, asset_id=asset.asset_id)


async def get_series_asset(db: AsyncSession, asset_id: str) -> ResolvedTopic3RiskAsset:
    """Look up a series asset by id, including unregistered legacy v6 imports."""
    asset = await _get_asset(db, asset_id)
    if asset is None:
        raise BenchmarkTopic3RiskSeriesNotFoundError("asset not found")
    if await db.get(BenchmarkAssetVersion, asset_id) is None and not is_series_manifest(
        loads_json_object(asset.manifest_json)
    ):
        raise BenchmarkTopic3RiskSeriesError(
            "asset is not a topic3 risk benchmark series asset"
        )
    return await describe_asset(db, asset)


async def list_versions(
    db: AsyncSession,
    *,
    summarize: Callable[[ResolvedTopic3RiskAsset], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    series = await db.get(BenchmarkAssetSeries, SERIES_ID)
    rows = (
        await db.execute(
            select(BenchmarkAssetVersion)
            .where(BenchmarkAssetVersion.series_id == SERIES_ID)
            .order_by(BenchmarkAssetVersion.registered_at, BenchmarkAssetVersion.asset_id)
        )
    ).scalars()
    versions = []
    for row in rows:
        asset = await _get_asset(db, row.asset_id)
        if asset is None:
            continue
        resolved = ResolvedTopic3RiskAsset(
            asset=asset,
            asset_version=row.asset_version,
            asset_sha256=row.content_sha256,
            asset_status=_status(series, row.asset_id),
        )
        versions.append(
            {
                **asset_overview(resolved, summarize=summarize),
                "registered_at": row.registered_at,
            }
        )
    return {
        "series_id": SERIES_ID,
        "series_name": SERIES_NAME,
        "current_asset_id": series.current_asset_id if series is not None else None,
        "versions": versions,
    }


def asset_overview(
    resolved: ResolvedTopic3RiskAsset,
    *,
    summarize: Callable[[ResolvedTopic3RiskAsset], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = loads_json_object(resolved.asset.manifest_json)
    sample_count = manifest.get("sample_count")
    overview = {
        **resolved.identity(),
        "series_name": SERIES_NAME,
        "name": resolved.asset.name,
        "sample_count": sample_count if isinstance(sample_count, int) else None,
        "evaluation_status": str(manifest.get("evaluation_status") or "evaluation_pending"),
    }
    if summarize is not None:
        overview.update(summarize(resolved))
    return overview


def build_evaluation_summary(asset: BenchmarkAsset, *, asset_sha256: str) -> dict[str, Any]:
    """Same-version evaluator results for ``asset`` with content hash ``asset_sha256``.

    A run is returned only if its own evaluation manifest declares this
    asset's id and content hash; the asset manifest's run list alone is not
    trusted.
    """
    manifest = loads_json_object(asset.manifest_json)
    artifact_dir = _io_path(Path(asset.artifact_dir))
    results = []
    excluded_run_ids = []
    for entry in manifest.get("evaluation_results", []):
        if not isinstance(entry, dict):
            continue
        if not _run_belongs_to_asset(artifact_dir, entry, asset.asset_id, asset_sha256):
            excluded_run_ids.append(str(entry.get("run_id") or ""))
            continue
        metrics_path = artifact_dir / str(entry.get("metrics_path") or "")
        if not metrics_path.is_file():
            continue
        metrics = load_json_object(metrics_path, "metrics.json").get("metrics")
        if not isinstance(metrics, dict):
            continue
        results.append(
            {
                **entry,
                "display_name": model_display_name(entry),
                "primary_metrics": primary_metric_values(metrics),
                "supporting_metrics": supporting_metrics(metrics),
                "per_category_metrics": metrics.get("per_category_metrics") or {},
            }
        )
    return {
        "available": bool(results),
        "asset_id": asset.asset_id,
        "asset_name": asset.name,
        "eval_mode": EVAL_MODE if results else "unavailable",
        "result_source": RESULT_SOURCE if results else "unavailable",
        "status": manifest.get("evaluation_status") or "evaluation_pending",
        "source_label": "课题三预跑导入结果" if results else "评测结果待导入",
        "primary_metrics": PRIMARY_METRICS,
        "results": results,
        "comparison": _same_version_comparison(results),
        "excluded_run_ids": excluded_run_ids,
        "live_eval": {
            "enabled": False,
            "status": "reserved_or_disabled",
        },
    }


def _same_version_comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Primary vs baseline from the same asset hash; never borrows another version."""
    primary = next((item for item in results if item.get("role") == "primary"), None)
    baseline = next((item for item in results if item.get("role") == "baseline"), None)
    if not results:
        message = "暂无同版本评测结果"
    elif primary is None:
        message = "暂无主评估器结果"
    elif baseline is None:
        message = "暂无同版本基线"
    else:
        message = ""
    available = primary is not None and baseline is not None
    return {
        "available": available,
        "same_version": available,
        "primary": _comparison_side(primary),
        "baseline": _comparison_side(baseline),
        "message": message,
    }


def _comparison_side(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {
        "run_id": entry.get("run_id"),
        "model_id": entry.get("model_id"),
        "display_name": entry.get("display_name") or model_display_name(entry),
        "primary_metrics": entry.get("primary_metrics") or {},
        "supporting_metrics": entry.get("supporting_metrics") or {},
    }


def build_resolved_evaluation_summary(resolved: ResolvedTopic3RiskAsset) -> dict[str, Any]:
    return {
        **build_evaluation_summary(resolved.asset, asset_sha256=resolved.asset_sha256),
        **resolved.identity(),
    }


def _run_belongs_to_asset(
    artifact_dir: Path,
    entry: dict[str, Any],
    asset_id: str,
    asset_sha256: str,
) -> bool:
    if not asset_sha256:
        return False
    run_id = str(entry.get("run_id") or "")
    manifest_rel = entry.get("manifest_path") or f"evaluations/{run_id}/evaluation_manifest.json"
    try:
        run_manifest = loads_json_object(
            (artifact_dir / str(manifest_rel)).read_text(encoding="utf-8")
        )
    except OSError:
        return False
    return (
        str(run_manifest.get("asset_id") or "") == asset_id
        and str(run_manifest.get("asset_sha256") or "") == asset_sha256
    )


def _status(series: BenchmarkAssetSeries | None, asset_id: str) -> AssetStatus:
    if series is not None and series.current_asset_id == asset_id:
        return "current"
    return "historical"


async def _get_or_create_series(db: AsyncSession) -> BenchmarkAssetSeries:
    series = await db.get(BenchmarkAssetSeries, SERIES_ID)
    if series is None:
        series = BenchmarkAssetSeries(
            series_id=SERIES_ID,
            name=SERIES_NAME,
            current_asset_id=None,
            updated_at=utc_now(),
        )
        db.add(series)
    return series


async def _version_row(db: AsyncSession, asset_version: str) -> BenchmarkAssetVersion | None:
    return (
        await db.execute(
            select(BenchmarkAssetVersion).where(
                BenchmarkAssetVersion.series_id == SERIES_ID,
                BenchmarkAssetVersion.asset_version == asset_version,
            )
        )
    ).scalar_one_or_none()


async def _get_asset(db: AsyncSession, asset_id: str) -> BenchmarkAsset | None:
    return (
        await db.execute(select(BenchmarkAsset).where(BenchmarkAsset.asset_id == asset_id))
    ).scalar_one_or_none()
