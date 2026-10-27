"""Benchmark management import, publish and same-version run append (#151, #152, #153)."""

import hashlib
import json
import secrets
import shutil
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.core.config import get_settings
from app.core.response import ok
from app.db.models import BenchmarkDelivery
from app.db.session import get_db
from app.schemas.benchmark import (
    BenchmarkDeliveryResponse,
    BenchmarkEvaluationAppendResponse,
)
from app.services.benchmark_topic3_risk_delivery_package import SAFE_ID_DESCRIPTION, is_safe_id
from app.services.benchmark_topic3_risk_delivery_publish import (
    BenchmarkDeliveryPublishFailed,
    PublishOutcome,
    publish_delivery,
)
from app.services.benchmark_topic3_risk_delivery_service import (
    BenchmarkDeliveryConflictError,
    BenchmarkDeliveryTooLargeError,
    DeliveryStatus,
    ReceiveOutcome,
    get_delivery,
    receive_delivery,
)
from app.services.benchmark_topic3_risk_evaluation_append import (
    BenchmarkEvaluationAppendConflictError,
    BenchmarkEvaluationAppendError,
    BenchmarkEvaluationAppendFailed,
    BenchmarkEvaluationAppendNotFoundError,
    append_evaluation_runs,
    append_staging_root,
)
from app.services.benchmark_topic3_risk_series_service import (
    BenchmarkTopic3RiskSeriesError,
    BenchmarkTopic3RiskSeriesNotFoundError,
)


ADMIN_TOKEN_HEADER = "X-Benchmark-Admin-Token"
_UPLOAD_FIELDS = frozenset({"file", "delivery_id"})
# Allowance for multipart boundaries and the delivery_id field on top of the package.
_MULTIPART_OVERHEAD_BYTES = 64 * 1024
_MAX_FIELD_BYTES = 1024
_CHUNK_SIZE = 1024 * 1024
_APPEND_FIELDS = frozenset({"file"})
_OUTCOME_HTTP_STATUS = {
    ReceiveOutcome.VALIDATED: 201,
    ReceiveOutcome.EXISTING: 200,
    ReceiveOutcome.IN_PROGRESS: 202,
}

router = APIRouter(prefix="/api/admin/benchmark", tags=["benchmark-admin"])


def require_benchmark_admin(
    token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
) -> str:
    """Returns the uploader identity: the configured admin label."""
    settings = get_settings()
    configured = settings.benchmark_admin_token
    expected = configured.get_secret_value().strip() if configured is not None else ""
    if not expected:
        raise HTTPException(status_code=503, detail="benchmark admin credential is not configured")
    if not token:
        raise HTTPException(status_code=401, detail="benchmark admin credential required")
    if not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=403, detail="invalid benchmark admin credential")
    return settings.benchmark_admin_label


class _UploadTooLarge(MultiPartException):
    pass


class _UploadFormParser(MultiPartParser):
    """Multipart parser that refuses oversized non-file fields."""

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is None and (
            len(self._current_part.data) + end - start > _MAX_FIELD_BYTES
        ):
            raise _UploadTooLarge(f"form fields are limited to {_MAX_FIELD_BYTES} bytes")
        super().on_part_data(data, start, end)


async def _limited(stream: AsyncGenerator[bytes, None], limit: int) -> AsyncGenerator[bytes, None]:
    received = 0
    async for chunk in stream:
        received += len(chunk)
        if received > limit:
            raise _UploadTooLarge(f"request body exceeds its {limit}-byte limit")
        yield chunk


async def _parse_multipart_form(
    request: Request,
    *,
    allowed_fields: frozenset[str],
    package_label: str,
    unexpected_hint: str,
):
    """Parse an authenticated multipart upload before any part reaches the service."""
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise HTTPException(
            status_code=415, detail=f"upload the {package_label} as multipart/form-data"
        )
    content_length = request.headers.get("content-length", "")
    if not content_length.isdigit():
        raise HTTPException(status_code=411, detail="the upload needs a Content-Length header")
    max_bytes = get_settings().benchmark_delivery_max_package_bytes
    if int(content_length) > max_bytes + _MULTIPART_OVERHEAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"{package_label} exceeds the {max_bytes}-byte limit"
        )

    parser = _UploadFormParser(
        request.headers,
        _limited(request.stream(), int(content_length)),
        max_files=1,
        max_fields=len(allowed_fields),
    )
    try:
        form = await parser.parse()
    except _UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail=exc.message) from exc
    except MultiPartException as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    unexpected = sorted(set(form.keys()) - allowed_fields)
    if unexpected:
        await form.close()
        raise HTTPException(
            status_code=422,
            detail=f"unsupported upload fields {unexpected}; {unexpected_hint}",
        )
    return form


async def _stage_upload(upload: UploadFile, target: Path, max_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as sink:
        while chunk := await upload.read(_CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"evaluation run package exceeds the {max_bytes}-byte limit",
                )
            digest.update(chunk)
            sink.write(chunk)
    if size == 0:
        raise HTTPException(status_code=422, detail="evaluation run package is empty")
    return digest.hexdigest(), size


# The body is parsed by hand after authentication so that unauthenticated or
# oversized uploads are refused before the multipart body is read.
@router.post("/deliveries")
async def upload_benchmark_delivery(
    request: Request,
    uploaded_by: str = Depends(require_benchmark_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await _parse_multipart_form(
        request,
        allowed_fields=_UPLOAD_FIELDS,
        package_label="delivery package",
        unexpected_hint="send only file and delivery_id",
    )
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(
                status_code=422, detail="file must be the delivery package uploaded as a file"
            )
        delivery_id = form.get("delivery_id")
        if not is_safe_id(delivery_id):
            raise HTTPException(
                status_code=422, detail=f"delivery_id must be {SAFE_ID_DESCRIPTION}"
            )
        try:
            row, outcome = await receive_delivery(
                db, delivery_id=delivery_id, upload=upload, uploaded_by=uploaded_by
            )
        except BenchmarkDeliveryTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except BenchmarkDeliveryConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        await form.close()
    msg = (
        "benchmark delivery failed validation"
        if row.status == DeliveryStatus.VALIDATION_FAILED
        else "success"
    )
    return JSONResponse(
        status_code=_OUTCOME_HTTP_STATUS[outcome], content=ok(_delivery_data(row), msg=msg)
    )


@router.get("/deliveries/{delivery_id}")
async def read_benchmark_delivery(
    delivery_id: str,
    _: str = Depends(require_benchmark_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await get_delivery(db, delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="benchmark delivery not found")
    return ok(_delivery_data(row))


@router.post("/deliveries/{delivery_id}/publish")
async def publish_benchmark_delivery(
    delivery_id: str,
    _: str = Depends(require_benchmark_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        row, outcome = await publish_delivery(db, delivery_id)
    except BenchmarkDeliveryPublishFailed as exc:
        raise HTTPException(status_code=500, detail="benchmark delivery publish failed") from exc
    if outcome is PublishOutcome.NOT_FOUND or row is None:
        raise HTTPException(status_code=404, detail="benchmark delivery not found")
    if outcome is PublishOutcome.NOT_PUBLISHABLE:
        raise HTTPException(
            status_code=409, detail="only a publishable benchmark delivery can be published"
        )
    if outcome is PublishOutcome.MAPPING_REJECTED:
        raise HTTPException(
            status_code=409,
            detail="benchmark delivery cannot be published because its records do not map uniquely",
        )
    if outcome is PublishOutcome.REJECTED:
        raise HTTPException(status_code=409, detail="benchmark delivery cannot be published")
    if outcome is PublishOutcome.IN_PROGRESS:
        return JSONResponse(
            status_code=202,
            content=ok(_delivery_data(row), msg="benchmark delivery publish is in progress"),
        )
    return ok(_delivery_data(row))


@router.post("/assets/{asset_id}/evaluations")
async def append_benchmark_evaluation_runs(
    asset_id: str,
    request: Request,
    uploaded_by: str = Depends(require_benchmark_admin),
    db: AsyncSession = Depends(get_db),
):
    """Append evaluation runs bound to an existing asset's registered content hash."""
    form = await _parse_multipart_form(
        request,
        allowed_fields=_APPEND_FIELDS,
        package_label="evaluation run package",
        unexpected_hint="send only file",
    )
    attempt_id = uuid.uuid4().hex
    upload_dir = append_staging_root() / "uploads" / attempt_id
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(
                status_code=422, detail="file must be the evaluation run package"
            )
        package_path = upload_dir / "package.zip"
        package_sha256, _ = await _stage_upload(
            upload, package_path, get_settings().benchmark_delivery_max_package_bytes
        )
        try:
            result = await append_evaluation_runs(
                db,
                asset_id=asset_id,
                package_path=package_path,
                package_sha256=package_sha256,
                uploaded_by=uploaded_by,
            )
        except BenchmarkEvaluationAppendConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except BenchmarkEvaluationAppendNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BenchmarkEvaluationAppendError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except BenchmarkEvaluationAppendFailed as exc:
            raise HTTPException(status_code=500, detail="evaluation run append failed") from exc
        except BenchmarkTopic3RiskSeriesNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BenchmarkTopic3RiskSeriesError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await form.close()
        shutil.rmtree(upload_dir, ignore_errors=True)
    response = BenchmarkEvaluationAppendResponse(**result)
    return ok(response.model_dump(mode="json"))


def _delivery_data(row: BenchmarkDelivery) -> dict:
    return BenchmarkDeliveryResponse(
        delivery_id=row.delivery_id,
        status=row.status,
        provider=row.provider,
        series_id=row.series_id,
        asset_id=row.asset_id,
        asset_version=row.asset_version,
        package_sha256=row.package_sha256,
        package_size=row.package_size,
        uploaded_by=row.uploaded_by,
        received_at=row.received_at,
        validated_at=row.validated_at,
        updated_at=row.updated_at,
        report=json.loads(row.report_json or "{}"),
    ).model_dump(mode="json")
