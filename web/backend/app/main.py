import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_indicators import router as indicators_router
from app.api.routes_data_input import router as data_input_router
from app.api.routes_benchmark import router as benchmark_router
from app.api.routes_benchmark_admin import router as benchmark_admin_router
from app.api.routes_mining_inputs import router as mining_inputs_router
from app.api.routes_mining_tasks import router as mining_tasks_router
from app.api.routes_output_eval import router as output_eval_router
from app.api.routes_output_guardrail import router as output_guardrail_router
from app.api.routes_governance import router as governance_router
from app.core.config import get_settings
from app.core.response import ERR_UNKNOWN, ERR_VALIDATION, code_for_http_status, fail, ok
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.migrations import MIGRATED_TABLES, apply_migrations
from app.db.schema_patches import ensure_mining_task_history_columns
from app.db.session import AsyncSessionLocal, engine
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_topic3_cultural_asset_service import (
    BenchmarkTopic3CulturalAssetService,
)
from app.services.benchmark_topic3_risk_series_service import (
    ensure_series_registered as ensure_topic3_risk_series_registered,
)
from app.services.data_input_value_qa_builtin import ensure_preferred_value_qa_assets
from app.services.governance_session_service import GovernancePlanningContextError


logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        legacy_tables = [
            table for table in Base.metadata.sorted_tables if table.name not in MIGRATED_TABLES
        ]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=legacy_tables))
        await ensure_mining_task_history_columns(conn)
        await apply_migrations(conn)
    async with AsyncSessionLocal() as session:
        await BenchmarkAssetRegistryService().ensure_prerun_assets_registered(session)
        # Release snapshots contain no cross-topic datasets. Explicitly configure
        # their locations before enabling startup imports.
        if settings.topic3_risk_benchmark_default_final_dir.strip():
            try:
                await ensure_topic3_risk_series_registered(session)
            except Exception:
                await session.rollback()
                logger.exception("Failed to register configured topic3 risk assets")
        await ensure_preferred_value_qa_assets(session)
        if settings.cultural_corpus_runs_dir.strip():
            try:
                await BenchmarkTopic3CulturalAssetService().ensure_default_asset(session)
            except Exception:
                await session.rollback()
                logger.exception("Failed to register configured topic3 cultural assets")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mining_inputs_router)
app.include_router(mining_tasks_router)
app.include_router(indicators_router)
app.include_router(data_input_router)
app.include_router(benchmark_router)
app.include_router(benchmark_admin_router)
app.include_router(output_eval_router)
app.include_router(output_guardrail_router)
app.include_router(governance_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=fail(ERR_VALIDATION, "参数校验失败"),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, list):
        msg = "参数校验失败"
    else:
        msg = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(code_for_http_status(exc.status_code), msg),
    )


@app.exception_handler(GovernancePlanningContextError)
async def governance_planning_context_exception_handler(
    request: Request, exc: GovernancePlanningContextError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "code": ERR_VALIDATION,
            "data": {"error_code": exc.code},
            "msg": str(exc),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content=fail(ERR_UNKNOWN, "服务器内部错误"),
    )


@app.get("/health")
async def health_check():
    return ok({"status": "ok"})
