from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.topic2_showcase.asset_store import (
    AssetNotFound,
    AssetStore,
    InvalidAssetManifest,
)
from app.topic2_showcase.artifact_store import (
    ArtifactNotFound,
    ArtifactStore,
    InvalidArtifact,
)
from app.topic2_showcase.config import ShowcaseSettings
from app.topic2_showcase.contracts import (
    CbrneStats,
    PrerunReportResponse,
    PrerunResponse,
    Readiness,
    ShowcaseMode,
    ShowcaseOverview,
    ShowcaseStatusResponse,
)
from app.topic2_showcase.dynbench_client import DynBenchClient, DynBenchHealth

STATIC_DIR = Path(__file__).resolve().parent / "static"
WORKFLOW_STEPS = ["SeedBank", "初测", "改写", "复测", "动态池", "报告"]
LIFECYCLE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}


class ShowcaseService:
    def __init__(
        self,
        settings: ShowcaseSettings,
        *,
        dynbench_client: DynBenchClient | None = None,
    ) -> None:
        self.settings = settings
        self.asset_store = AssetStore(settings.asset_root)
        self.artifact_store = ArtifactStore(settings.asset_root)
        self.dynbench_client = dynbench_client or DynBenchClient.from_settings(
            settings
        )

    def static_readiness(self) -> Readiness:
        try:
            self.asset_store.cbrne_stats()
            self.asset_store.lifecycle_cases()
        except AssetNotFound:
            return "missing"
        except InvalidAssetManifest:
            return "invalid"
        return "ready"

    def dynbench_health(self) -> DynBenchHealth:
        return self.dynbench_client.check_health()

    def build_status(self) -> ShowcaseStatusResponse:
        dynbench_health = self.dynbench_health()
        static_assets = self.static_readiness()
        prerun = self.artifact_store.readiness()
        mode = select_showcase_mode(
            dynbench=dynbench_health.readiness,
            prerun=prerun,
            static_assets=static_assets,
        )
        return ShowcaseStatusResponse(
            static_assets=static_assets,
            prerun=prerun,
            dynbench=dynbench_health.readiness,
            mode=mode,
            dynbench_webui_url=dynbench_health.webui_url,
        )

    def build_overview(self) -> ShowcaseOverview:
        status = self.build_status()
        stats = self.asset_store.cbrne_stats()
        lifecycle_cases = self.asset_store.lifecycle_cases()
        lifecycle_case_total = sum(case.case_count for case in lifecycle_cases)
        return ShowcaseOverview(
            title=self.settings.showcase_title,
            cbrne_full_total=stats.full.total,
            cbrne_filtered_total=stats.filtered.total,
            lifecycle_case_total=lifecycle_case_total,
            lifecycle_cases=lifecycle_cases,
            workflow=list(WORKFLOW_STEPS),
            status=status,
        )

    def cbrne_stats(self) -> CbrneStats:
        return self.asset_store.cbrne_stats()

    def prerun_payload(self) -> PrerunResponse:
        summary = self.artifact_store.active_summary()
        return PrerunResponse(
            metadata=summary.metadata,
            lifecycle=summary.lifecycle,
        )

    def prerun_report(self) -> str:
        return self.artifact_store.active_summary().report


def select_showcase_mode(
    *,
    dynbench: Readiness,
    prerun: Readiness,
    static_assets: Readiness,
) -> ShowcaseMode:
    dynbench_ready = dynbench == "ready"
    prerun_ready = prerun == "ready"
    static_ready = static_assets == "ready"
    if dynbench_ready and prerun_ready and static_ready:
        return "dynamic"
    if prerun_ready and static_ready:
        return "prerun"
    return "static-only"


def resolve_static_file(relative_path: str) -> Path:
    candidate = (STATIC_DIR / relative_path).resolve()
    if candidate != STATIC_DIR and STATIC_DIR not in candidate.parents:
        raise HTTPException(status_code=404, detail="Not found")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return candidate


def create_app(
    settings: ShowcaseSettings | None = None,
    *,
    dynbench_client: DynBenchClient | None = None,
) -> FastAPI:
    resolved_settings = settings or ShowcaseSettings()
    service = ShowcaseService(
        resolved_settings,
        dynbench_client=dynbench_client,
    )
    app = FastAPI(title=resolved_settings.showcase_title)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            media_type="text/html",
        )

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse(
            {"status": "ok", "service": "topic2-showcase"},
        )

    @app.get("/api/status", response_model=ShowcaseStatusResponse)
    def status() -> ShowcaseStatusResponse:
        return service.build_status()

    @app.get("/api/overview", response_model=ShowcaseOverview)
    def overview() -> ShowcaseOverview:
        try:
            return service.build_overview()
        except (AssetNotFound, InvalidAssetManifest) as exc:
            raise HTTPException(status_code=503, detail="assets unavailable") from exc

    @app.get("/api/cbrne/stats", response_model=CbrneStats)
    def cbrne_stats() -> CbrneStats:
        try:
            return service.cbrne_stats()
        except AssetNotFound as exc:
            raise HTTPException(status_code=404, detail="assets unavailable") from exc
        except InvalidAssetManifest as exc:
            raise HTTPException(status_code=503, detail="assets invalid") from exc

    @app.get("/api/prerun", response_model=PrerunResponse)
    def prerun() -> PrerunResponse:
        try:
            return service.prerun_payload()
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=404, detail="prerun unavailable") from exc
        except InvalidArtifact as exc:
            raise HTTPException(status_code=503, detail="prerun invalid") from exc

    @app.get("/api/prerun/report", response_model=PrerunReportResponse)
    def prerun_report() -> PrerunReportResponse:
        try:
            return PrerunReportResponse(report=service.prerun_report())
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=404, detail="prerun unavailable") from exc
        except InvalidArtifact as exc:
            raise HTTPException(status_code=503, detail="prerun invalid") from exc

    @app.get("/lifecycle/{case_id}")
    def lifecycle(case_id: str) -> FileResponse:
        try:
            path = service.asset_store.lifecycle_path(case_id)
        except AssetNotFound as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        except InvalidAssetManifest as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        return FileResponse(
            path,
            media_type="text/html",
            headers=LIFECYCLE_HEADERS,
        )

    @app.get("/static/{asset_path:path}")
    def static_assets(asset_path: str) -> FileResponse:
        path = resolve_static_file(asset_path)
        media_type = "text/css" if path.suffix == ".css" else None
        if path.suffix == ".js":
            media_type = "application/javascript"
        return FileResponse(path, media_type=media_type)

    return app


def __getattr__(name: str):
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
