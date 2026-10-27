import asyncio
import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkAsset
from app.schemas.data_input import (
    IntegrationEndpoint,
    Topic2HealthResponse,
    Topic2KeywordFinding,
    Topic2KeywordPrediction,
    Topic2KeywordPredictResponse,
    Topic2PrerunSampleRow,
    Topic2PrerunSamplesResponse,
    Topic2RiskScanItem,
    Topic2RiskScanTaskResponse,
)
from app.services.benchmark_asset_registry_service import BenchmarkAssetRegistryService
from app.services.benchmark_topic2_prerun_sample_service import (
    BenchmarkTopic2PrerunSampleError,
    BenchmarkTopic2PrerunSampleService,
)
from app.services.input_risk_detection_service import (
    InputRiskDetection,
    InputRiskDetectionError,
    InputRiskHealth,
    InputRiskHit,
    METHOD_ACTIVATION_PROBE,
    METHOD_KEYWORD,
    check_input_risk_health,
    detect_input_risk,
    resolve_input_risk_method,
)

TOPIC2_KEYWORD_ENDPOINTS = [
    IntegrationEndpoint(
        method="GET",
        path="/health",
        purpose="检查课题二 FilterGuard 输入风险识别服务是否可达。",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/predict/keyword",
        purpose="使用 keyword 方法对输入语料片段进行异常识别，返回命中词、分数和异常判断。",
    ),
]

TOPIC2_ACTIVATION_PROBE_ENDPOINTS = [
    IntegrationEndpoint(
        method="GET",
        path="/healthz",
        purpose="检查课题二 Activation Probe（neuron / same_l1）远程服务是否就绪。",
    ),
    IntegrationEndpoint(
        method="GET",
        path="/v1/info",
        purpose="读取 Activation Probe 状态与方法列表（新版）；兼容旧版方法名、模型与最大 batch 信息。",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/v1/moderate",
        purpose="批量识别输入语料，返回 unsafe、predicted_l1_id 与明文 harm_category_L1。",
    ),
]

TOPIC2_ENDPOINTS = TOPIC2_KEYWORD_ENDPOINTS

TOPIC2_PRERUN_ENDPOINTS = [
    IntegrationEndpoint(
        method="GET",
        path="/api/benchmark/assets",
        purpose="读取课题五 Benchmark 资产注册表中的正式预跑快照。",
    ),
    IntegrationEndpoint(
        method="GET",
        path="/api/benchmark/assets/{asset_id}/topic2-prerun/samples",
        purpose="读取课题二正式配对预跑结果、L1/L2 标签和评测器判定。",
    ),
]

TOPIC2_TASK_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
_topic2_risk_scan_tasks: dict[str, Topic2RiskScanTaskResponse] = {}
_topic2_risk_scan_cancel_requested: set[str] = set()


def _endpoints_for_method(method: str) -> list[IntegrationEndpoint]:
    if method == METHOD_ACTIVATION_PROBE:
        return TOPIC2_ACTIVATION_PROBE_ENDPOINTS
    return TOPIC2_KEYWORD_ENDPOINTS


def _unavailable_payload(base_url: str, method: str, reason: str = "") -> dict[str, Any]:
    if method == METHOD_ACTIVATION_PROBE:
        blocking_reason = reason or "课题二 Activation Probe 服务不可达，或 /healthz 未就绪。"
        next_action = (
            "请确认 AutoDL 上 Activation Probe 服务 Running，并检查 "
            "TOPIC2_ACTIVATION_PROBE_BASE_URL 是否指向正确入口。"
        )
        if reason:
            next_action += (
                " 若本地直连固定远端入口超时，请设置 "
                "TOPIC2_ACTIVATION_PROBE_PROXY_URL=http://127.0.0.1:7897 后重启平台。"
            )
        return {
            "connected": False,
            "service": "Project 2 Activation Probe",
            "base_url": base_url,
            "method": method,
            "source": "topic2_activation_probe",
            "message": (
                f"无法连接课题二 Activation Probe 服务（{base_url}）。"
                "当前不会静默展示模拟识别结果，请确认远程 neuron 服务 Running 后重试。"
            ),
            "fallback": False,
            "blocking_reason": blocking_reason,
            "next_action": next_action,
            "endpoints": TOPIC2_ACTIVATION_PROBE_ENDPOINTS,
        }

    return {
        "connected": False,
        "service": "Project 2 FilterGuard",
        "base_url": base_url,
        "method": method,
        "source": "topic2_filterguard",
        "message": (
            f"无法连接课题二 FilterGuard 输入风险识别服务（{base_url}）。"
            "当前不会静默展示模拟识别结果，请先启动 Project_2_Anomaly_Data_Identification 后重试。"
        ),
        "fallback": False,
        "blocking_reason": "课题二 FilterGuard 服务不可达，或 keyword 方法尚未启动。",
        "next_action": (
            "推荐在 WSL Ubuntu / POSIX shell 中从课题五根目录执行 "
            "node scripts/start-platform.mjs 统一启动；排障时可在 "
            "Project_2_Anomaly_Data_Identification 目录执行 "
            "filterguard serve --methods keyword --host 0.0.0.0 --port 6211。"
        ),
        "endpoints": TOPIC2_KEYWORD_ENDPOINTS,
    }


async def check_topic2_filterguard_health(method: str | None = None) -> Topic2HealthResponse:
    """Input-side health view: the shared domain facts plus the page copy."""

    health = await check_input_risk_health(method)
    if not health.connected:
        return _disconnected_health_response(health)
    if health.method == METHOD_ACTIVATION_PROBE:
        return Topic2HealthResponse(
            connected=True,
            service="Project 2 Activation Probe",
            base_url=health.base_url,
            method=METHOD_ACTIVATION_PROBE,
            source="topic2_activation_probe",
            message=f"已连接课题二 Activation Probe（{health.detail}）。",
            next_action="可以启动批量输入风险识别任务；输入文本不会写入上游日志，也不会在响应中回显。",
            endpoints=TOPIC2_ACTIVATION_PROBE_ENDPOINTS,
        )
    return Topic2HealthResponse(
        connected=True,
        base_url=health.base_url,
        method=health.method,
        message="已连接课题二 FilterGuard 输入风险识别服务。",
        next_action="可以启动批量输入风险识别任务。",
        endpoints=TOPIC2_KEYWORD_ENDPOINTS,
    )


def _disconnected_health_response(health: InputRiskHealth) -> Topic2HealthResponse:
    """Restore the input-side copy for a disconnected shared health fact."""

    if health.method == METHOD_KEYWORD and health.failure_kind == "method_missing":
        offered = "、".join(health.offered_methods) or "未上报方法"
        return Topic2HealthResponse(
            connected=False,
            base_url=health.base_url,
            method=health.method,
            message=f"课题二 FilterGuard 已响应，但未加载 {health.method} 方法。",
            fallback=False,
            blocking_reason=(
                f"课题二 FilterGuard 已响应，但上游只加载了 {offered}，"
                f"未加载 {health.method} 方法。"
            ),
            next_action=(
                "推荐通过 node scripts/start-platform.mjs 统一启动；"
                f"排障时请确认课题二 FilterGuard 已启用 {health.method} 方法。"
            ),
            endpoints=TOPIC2_KEYWORD_ENDPOINTS,
        )
    return Topic2HealthResponse(
        **_unavailable_payload(health.base_url, health.method, health.reason)
    )


async def run_topic2_keyword_detection(
    texts: list[str] | None = None,
    *,
    scan_items: list[Topic2RiskScanItem] | None = None,
    method: str | None = None,
) -> Topic2KeywordPredictResponse:
    """Input-side detection view over the shared domain service.

    The shared service owns the upstream call and normalization; this module only
    maps the neutral facts back to the ``Topic2KeywordPrediction`` presentation.
    Empty input is an explicit failure, never a fabricated success.
    """

    resolved = resolve_input_risk_method(method)
    prepared_items = _prepare_scan_items(texts=texts, scan_items=scan_items)
    try:
        detection = await detect_input_risk(
            [item.text for item in prepared_items], method=resolved
        )
    except InputRiskDetectionError as exc:
        return Topic2KeywordPredictResponse(
            **_no_samples_payload(resolved, exc.code)
        )
    if resolved == METHOD_ACTIVATION_PROBE:
        return _activation_probe_response(detection, prepared_items)
    return _keyword_response(detection, prepared_items)


def _keyword_response(
    detection: InputRiskDetection,
    prepared_items: list[Topic2RiskScanItem],
) -> Topic2KeywordPredictResponse:
    if not detection.connected:
        return Topic2KeywordPredictResponse(
            **_unavailable_payload(detection.base_url, METHOD_KEYWORD, detection.reason)
        )
    predictions = [
        _keyword_prediction(hit, prepared_items[hit.index])
        for hit in detection.items
        if 0 <= hit.index < len(prepared_items)
    ]
    abnormal_count = sum(1 for item in predictions if item.is_abnormal)
    return Topic2KeywordPredictResponse(
        connected=True,
        base_url=detection.base_url,
        method=detection.method,
        message="已获取课题二 FilterGuard keyword 异常识别结果。",
        next_action="识别结果已同步到输入模块风险评估、归因和修正预览。",
        endpoints=TOPIC2_KEYWORD_ENDPOINTS,
        total=len(predictions),
        abnormal_count=abnormal_count,
        normal_count=len(predictions) - abnormal_count,
        predictions=predictions,
    )


def _activation_probe_response(
    detection: InputRiskDetection,
    prepared_items: list[Topic2RiskScanItem],
) -> Topic2KeywordPredictResponse:
    if not detection.connected:
        return Topic2KeywordPredictResponse(
            **_unavailable_payload(
                detection.base_url, METHOD_ACTIVATION_PROBE, detection.reason
            )
        )
    predictions = [
        _activation_probe_prediction(hit, prepared_items[hit.index])
        for hit in detection.items
        if 0 <= hit.index < len(prepared_items)
    ]
    abnormal_count = sum(1 for item in predictions if item.is_abnormal)
    return Topic2KeywordPredictResponse(
        connected=True,
        service="Project 2 Activation Probe",
        base_url=detection.base_url,
        method=METHOD_ACTIVATION_PROBE,
        source="topic2_activation_probe",
        message=f"已获取课题二 Activation Probe 识别结果（上游 {detection.method}）。",
        next_action="识别结果已同步到输入模块风险评估、归因和修正预览；L1 来自 predicted same_l1。",
        endpoints=TOPIC2_ACTIVATION_PROBE_ENDPOINTS,
        total=len(predictions),
        abnormal_count=abnormal_count,
        normal_count=len(predictions) - abnormal_count,
        predictions=predictions,
    )


# Neutral detection error codes → the input surface's own Chinese copy.
_INPUT_RISK_ERROR_COPY = {
    "empty_texts": "未提供待检测文本，未调用在线检测。",
}


def _no_samples_payload(method: str, error_code: str = "") -> dict[str, Any]:
    """Explicit local failure for an empty request; nothing was detected.

    The shared detection service reports only a neutral ``error_code``; the
    Chinese no-sample copy shown on the input surface is composed here.
    """

    reason = _INPUT_RISK_ERROR_COPY.get(error_code, _INPUT_RISK_ERROR_COPY["empty_texts"])
    payload = _unavailable_payload("", method, reason)
    payload["message"] = reason
    payload["blocking_reason"] = reason
    payload["next_action"] = "请先选择或上传至少一条待检测语料，再发起在线识别。"
    return payload


async def start_topic2_risk_scan_task(
    items: list[Topic2RiskScanItem] | None = None,
    *,
    method: str | None = None,
) -> Topic2RiskScanTaskResponse:
    resolved = resolve_input_risk_method(method)
    task_id = f"topic2-risk-scan-{uuid.uuid4().hex[:12]}"
    task = Topic2RiskScanTaskResponse(
        task_id=task_id,
        status="queued",
        progress=0,
        message=f"已创建课题二输入风险识别任务（method={resolved}）。",
        cancellable=True,
        method=resolved,
    )
    _topic2_risk_scan_tasks[task_id] = task
    asyncio.create_task(_run_topic2_risk_scan_task(task_id, items or [], resolved))
    return task


async def get_topic2_risk_scan_task(task_id: str) -> Topic2RiskScanTaskResponse | None:
    return _topic2_risk_scan_tasks.get(task_id)


async def cancel_topic2_risk_scan_task(task_id: str) -> Topic2RiskScanTaskResponse | None:
    task = _topic2_risk_scan_tasks.get(task_id)
    if task is None:
        return None
    if task.status in TOPIC2_TASK_TERMINAL_STATUSES:
        return task
    _topic2_risk_scan_cancel_requested.add(task_id)
    _set_topic2_task_state(
        task_id,
        status="cancel_requested",
        progress=task.progress,
        message="已请求取消课题二输入风险识别任务；若上游调用已发出，将在返回后停止同步结果。",
        cancellable=False,
    )
    return _topic2_risk_scan_tasks.get(task_id)


async def load_topic2_prerun_samples(
    db: AsyncSession,
    *,
    asset_id: str | None = None,
    limit: int = 20,
) -> Topic2PrerunSamplesResponse:
    registry_service = BenchmarkAssetRegistryService()
    asset = await _resolve_topic2_prerun_asset(db, registry_service, asset_id=asset_id)
    if asset is None:
        return Topic2PrerunSamplesResponse(
            connected=False,
            message="未找到已导入的课题二正式预跑评测资产。",
            blocking_reason="Benchmark 资产注册表中暂无课题二正式预跑快照。",
            next_action="请先在 Benchmark 资产管理中导入课题二正式预跑快照包，再回到输入风险评估页载入平台资产。",
            endpoints=TOPIC2_PRERUN_ENDPOINTS,
        )

    try:
        payload = await BenchmarkTopic2PrerunSampleService().list_pairs(
            db,
            asset_id=asset.asset_id,
            limit=limit,
            offset=0,
        )
    except BenchmarkTopic2PrerunSampleError as exc:
        return Topic2PrerunSamplesResponse(
            connected=False,
            message="课题二正式预跑评测资产无法读取。",
            blocking_reason=str(exc),
            next_action="请检查该资产是否包含 manifest、report、results、dynbench 四类文件，以及简单/困难配对字段。",
            endpoints=TOPIC2_PRERUN_ENDPOINTS,
            asset_id=asset.asset_id,
            asset_name=asset.name,
        )

    rows = _topic2_prerun_rows(payload.get("pairs", []))
    l1_labels = _unique_strings(row.harm_category_l1 for row in rows if row.harm_category_l1)
    return Topic2PrerunSamplesResponse(
        connected=True,
        message=f"已载入课题二正式预跑资产：{asset.name}",
        next_action="评估、归因和修正数据来自课题二正式预跑评测资产，不依赖临时数据。",
        endpoints=TOPIC2_PRERUN_ENDPOINTS,
        asset_id=asset.asset_id,
        asset_name=asset.name,
        total=len(rows),
        pair_count=int(payload.get("total") or 0),
        moderators=[str(item) for item in payload.get("moderators", [])],
        l1_labels=l1_labels,
        rows=rows,
    )


def _keyword_prediction(
    hit: InputRiskHit,
    source_item: Topic2RiskScanItem,
) -> Topic2KeywordPrediction:
    """Present one neutral keyword hit as the input-side prediction DTO."""

    text = source_item.text
    hits = list(hit.hits)
    status = _status_from_result(hit.score, hit.threshold, hit.unsafe)
    findings = [
        Topic2KeywordFinding(
            keyword=hit_word,
            evidence=_evidence_for_hit(text, hit_word),
            risk_type=_risk_type_from_hit(hit_word),
        )
        for hit_word in hits
    ]
    return Topic2KeywordPrediction(
        id=f"P2-KW-{hit.index + 1:03d}",
        text=text,
        source_index=hit.index,
        lineage_node_id=source_item.lineage_node_id,
        lineage_node_label=source_item.lineage_node_label,
        risk_category_l1=source_item.risk_category_l1,
        risk_category_l2=source_item.risk_category_l2,
        detect_method=METHOD_KEYWORD,
        action=_action_from_keyword(hit.unsafe, hits),
        score=hit.score,
        threshold=hit.threshold,
        prediction=1 if hit.unsafe else 0,
        is_abnormal=hit.unsafe,
        status=status,
        suggestion=_suggestion_from_result(
            hit.unsafe,
            hits,
            source_item,
            findings=findings,
        ),
        evidence_chain=_evidence_chain_from_result(
            source_item, findings, status, hit.score
        ),
        findings=findings,
    )


def _activation_probe_prediction(
    hit: InputRiskHit,
    source_item: Topic2RiskScanItem,
) -> Topic2KeywordPrediction:
    """Present one neutral Activation Probe hit as the input-side prediction DTO."""

    is_abnormal = hit.unsafe
    status = "异常" if is_abnormal else "安全"
    predicted_l1_id = hit.predicted_l1_id
    harm_l1_display = hit.harm_category_l1
    risk_category_l1 = harm_l1_display or source_item.risk_category_l1
    findings: list[Topic2KeywordFinding] = []
    if predicted_l1_id or harm_l1_display:
        findings.append(
            Topic2KeywordFinding(
                keyword=predicted_l1_id or harm_l1_display,
                evidence=harm_l1_display or predicted_l1_id,
                risk_type="activation_probe_predicted_l1",
            )
        )
    suggestion = _action_from_activation_probe(
        is_abnormal=is_abnormal,
        harm_l1=harm_l1_display,
        predicted_l1_id=predicted_l1_id,
    )
    evidence_chain = _evidence_chain_from_activation_probe(
        source_item=source_item,
        status=status,
        score=hit.score,
        predicted_l1_id=predicted_l1_id,
        harm_l1=harm_l1_display,
        is_abnormal=is_abnormal,
    )
    return Topic2KeywordPrediction(
        id=f"P2-AP-{hit.index + 1:03d}",
        text=source_item.text,
        source_index=hit.index,
        lineage_node_id=source_item.lineage_node_id,
        lineage_node_label=source_item.lineage_node_label,
        risk_category_l1=risk_category_l1,
        risk_category_l2=source_item.risk_category_l2,
        predicted_l1_id=predicted_l1_id,
        detect_method=METHOD_ACTIVATION_PROBE,
        action=suggestion,
        score=hit.score,
        threshold=hit.threshold,
        prediction=1 if is_abnormal else 0,
        is_abnormal=is_abnormal,
        status=status,
        suggestion=suggestion,
        evidence_chain=evidence_chain,
        findings=findings,
    )


def _action_from_activation_probe(
    *,
    is_abnormal: bool,
    harm_l1: str = "",
    predicted_l1_id: str = "",
) -> str:
    if not is_abnormal:
        return "可纳入低风险抽检；如需抽检，优先核对 L1 路由是否合理。"
    l1 = harm_l1 or predicted_l1_id or "未返回 L1"
    return (
        f"【处置要点】Activation Probe 判定异常（{l1}）。\n"
        "- 课题二当前未提供安全改写正文。\n"
        "- 建议：按 L1 从训练正样本剔除、脱敏关键实体，或人工改写后复跑识别。"
    )


def _action_from_keyword(is_abnormal: bool, hits: list[str]) -> str:
    if not is_abnormal:
        return "可纳入低风险抽检。"
    if hits:
        preview = "、".join(hits[:3])
        more = f" 等 {len(hits)} 个" if len(hits) > 3 else ""
        return f"命中关键词「{preview}」{more}：请删除/脱敏/改写命中片段后复检。"
    return "判定为异常，请人工处置（当前无自动 rewrite）。"


def _evidence_chain_from_activation_probe(
    *,
    source_item: Topic2RiskScanItem,
    status: str,
    score: float,
    predicted_l1_id: str,
    harm_l1: str,
    is_abnormal: bool,
) -> list[str]:
    chain = [
        f"输入语料片段 #{source_item.lineage_node_id or source_item.lineage_node_label or '未绑定节点'}"
    ]
    if source_item.lineage_node_label:
        chain.append(f"血缘节点：{source_item.lineage_node_label}")
    chain.append(
        f"Activation Probe L1：{harm_l1 or '未返回明文'}（id={predicted_l1_id or '未知'}）"
    )
    chain.append(
        f"课题二判定：{status}，unsafe={'true' if is_abnormal else 'false'}，风险分 {score:.2f}"
    )
    chain.append("说明：上游不回显输入文本，也不将输入写入服务日志。")
    return chain


async def _run_topic2_risk_scan_task(
    task_id: str,
    items: list[Topic2RiskScanItem],
    method: str,
) -> None:
    try:
        method_label = (
            "Activation Probe"
            if method == METHOD_ACTIVATION_PROBE
            else "FilterGuard keyword"
        )
        _set_topic2_task_state(
            task_id,
            status="running",
            progress=10,
            message="正在整理上传语料切片与血缘节点引用。",
            cancellable=True,
        )
        if _is_topic2_task_cancelled(task_id):
            _mark_topic2_task_cancelled(task_id)
            return

        _set_topic2_task_state(
            task_id,
            progress=30,
            message=f"正在调用课题二 {method_label} 服务。",
        )
        prediction_task = asyncio.create_task(
            run_topic2_keyword_detection(scan_items=items, method=method)
        )
        progress = 30
        while not prediction_task.done():
            await asyncio.wait({prediction_task}, timeout=1)
            if _is_topic2_task_cancelled(task_id):
                prediction_task.cancel()
                _mark_topic2_task_cancelled(task_id)
                return
            progress = min(progress + 5, 80)
            _set_topic2_task_state(
                task_id,
                progress=progress,
                message=f"课题二 {method_label} 正在识别输入语料片段。",
            )
        result = await prediction_task

        if _is_topic2_task_cancelled(task_id):
            _mark_topic2_task_cancelled(task_id)
            return

        if not result.connected:
            _set_topic2_task_state(
                task_id,
                status="failed",
                progress=100,
                message=result.message,
                cancellable=False,
                result=result,
            )
            return

        _set_topic2_task_state(
            task_id,
            status="running",
            progress=85,
            message="正在生成风险归因证据链与修正预览。",
            cancellable=True,
        )
        if _is_topic2_task_cancelled(task_id):
            _mark_topic2_task_cancelled(task_id)
            return

        _set_topic2_task_state(
            task_id,
            status="completed",
            progress=100,
            message=f"课题二输入风险识别任务已完成（{method_label}）。",
            cancellable=False,
            result=result,
        )
    except Exception as exc:  # pragma: no cover - defensive task boundary
        _set_topic2_task_state(
            task_id,
            status="failed",
            progress=100,
            message=f"课题二输入风险识别任务失败：{exc}",
            cancellable=False,
        )


def _set_topic2_task_state(
    task_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    cancellable: bool | None = None,
    result: Topic2KeywordPredictResponse | None = None,
) -> None:
    task = _topic2_risk_scan_tasks.get(task_id)
    if task is None:
        return
    if status is not None:
        task.status = status
    if progress is not None:
        task.progress = min(max(progress, 0), 100)
    if message is not None:
        task.message = message
    if cancellable is not None:
        task.cancellable = cancellable
    if result is not None:
        task.result = result


def _is_topic2_task_cancelled(task_id: str) -> bool:
    return task_id in _topic2_risk_scan_cancel_requested


def _mark_topic2_task_cancelled(task_id: str) -> None:
    _topic2_risk_scan_cancel_requested.discard(task_id)
    _set_topic2_task_state(
        task_id,
        status="cancelled",
        progress=100,
        message="课题二输入风险识别任务已取消，未同步本轮结果。",
        cancellable=False,
    )


def _prepare_scan_items(
    *,
    texts: list[str] | None = None,
    scan_items: list[Topic2RiskScanItem] | None = None,
) -> list[Topic2RiskScanItem]:
    if scan_items:
        return [item for item in scan_items if item.text.strip()]
    return [
        Topic2RiskScanItem(text=text.strip()) for text in texts or [] if text.strip()
    ]


async def _resolve_topic2_prerun_asset(
    db: AsyncSession,
    registry_service: BenchmarkAssetRegistryService,
    *,
    asset_id: str | None,
) -> BenchmarkAsset | None:
    if asset_id:
        asset = await registry_service.get_asset(db, asset_id)
        return asset if asset and _is_topic2_prerun_asset(asset) else None

    assets = await registry_service.list_assets(db, source_mode="prerun_snapshot")
    return next((asset for asset in assets if _is_topic2_prerun_asset(asset)), None)


def _is_topic2_prerun_asset(asset: BenchmarkAsset) -> bool:
    manifest = _loads_json_object(asset.manifest_json)
    asset_id = str(asset.asset_id or "").lower()
    source_repo = str(manifest.get("source_repo") or "").lower()
    delivery_schema = str(manifest.get("delivery_schema_version") or "").lower()
    benchmark_type = str(manifest.get("benchmark_type") or "").lower()
    return (
        manifest.get("source_mode") == "prerun_snapshot"
        and benchmark_type != "risk_content_generation"
        and (
            "topic2_simple_hard" in asset_id
            or "dynbench" in source_repo
            or "simple-hard-prerun" in delivery_schema
        )
    )


def _topic2_prerun_rows(pairs: list[dict[str, Any]]) -> list[Topic2PrerunSampleRow]:
    rows: list[Topic2PrerunSampleRow] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        for difficulty in ("simple", "hard"):
            sample = pair.get(difficulty)
            if isinstance(sample, dict):
                rows.append(_topic2_prerun_row(pair, sample, difficulty))
    return rows


def _topic2_prerun_row(
    pair: dict[str, Any],
    sample: dict[str, Any],
    difficulty: str,
) -> Topic2PrerunSampleRow:
    verdict = _moderator_verdict_summary(sample, difficulty=difficulty)
    l1 = str(pair.get("harm_category_l1") or "")
    l2 = str(pair.get("harm_category_l2") or "")
    strategy_chain = [str(item) for item in sample.get("strategy_chain", []) if str(item).strip()]
    suggestion_parts = [
        "【说明】课题二预跑未提供「安全改写正文」；strategy_chain 是攻击侧改写路径，不是修正稿。",
        f"来源：{difficulty} 预跑样本。",
        f"L1：{l1 or '未标注'}；L2：{l2 or '未标注'}。",
        verdict["summary"],
        f"攻击改写策略：{' -> '.join(strategy_chain)}。" if strategy_chain else "",
        "【处置建议】勿作训练正样本；可隔离为困难负例，或整段剔除后入训。",
    ]
    return Topic2PrerunSampleRow(
        id=f"{difficulty}-{sample.get('sample_id') or sample.get('id') or pair.get('pair_id')}",
        score=float(verdict["score"]),
        status=str(verdict["status"]),
        snippet=str(sample.get("query") or sample.get("query_preview") or ""),
        suggestion=" ".join(part for part in suggestion_parts if part),
        difficulty_level=difficulty,
        pair_id=str(pair.get("pair_id") or ""),
        harm_category_l1=l1,
        harm_category_l2=l2,
        strategy_chain=strategy_chain,
        bypassed_moderators=list(verdict["bypassed_moderators"]),
    )


def _moderator_verdict_summary(sample: dict[str, Any], *, difficulty: str) -> dict[str, Any]:
    results = sample.get("moderator_results") if isinstance(sample.get("moderator_results"), dict) else {}
    bypassed = [
        str(name)
        for name, result in results.items()
        if isinstance(result, dict) and result.get("label") == "safe"
    ]
    blocked = len(results) - len(bypassed)
    bypass_rate = len(bypassed) / len(results) if results else 0.0
    if bypassed:
        return {
            "score": max(0.7, bypass_rate),
            "status": "异常",
            "summary": f"存在 {len(bypassed)} 个评测器漏检：{'、'.join(bypassed)}。",
            "bypassed_moderators": bypassed,
        }
    if difficulty == "hard":
        return {
            "score": 0.55,
            "status": "安全",
            "summary": f"困难样本已被 {blocked} 个评测器拦截，建议继续纳入抽检。",
            "bypassed_moderators": [],
        }
    return {
        "score": 0.25,
        "status": "安全",
        "summary": f"简单样本已被 {blocked} 个评测器拦截，可作为稳定识别基线。",
        "bypassed_moderators": [],
    }


def _loads_json_object(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _unique_strings(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _status_from_result(score: float, threshold: float, is_abnormal: bool) -> str:
    del score, threshold  # Topic 2 live detection is binary; keep signature for call sites.
    return "异常" if is_abnormal else "安全"


def _suggestion_from_result(
    is_abnormal: bool,
    hits: list[str],
    source_item: Topic2RiskScanItem,
    findings: list[Topic2KeywordFinding] | None = None,
) -> str:
    lineage_hint = (
        f"血缘：{source_item.lineage_node_label or source_item.lineage_node_id}。"
        if source_item.lineage_node_id or source_item.lineage_node_label
        else ""
    )
    category_hint = ""
    if source_item.risk_category_l1 or source_item.risk_category_l2:
        category_hint = (
            f"风险类别：{source_item.risk_category_l1 or '未标注'}"
            f" / {source_item.risk_category_l2 or '未标注'}。"
        )
    if not is_abnormal:
        return f"课题二 keyword 未识别出显式异常，可纳入低风险抽检。{lineage_hint}{category_hint}"

    lines = [
        "【处置要点】课题二未提供安全改写正文，请按证据人工删除/脱敏/改写：",
    ]
    used_findings = findings or []
    if used_findings:
        for finding in used_findings[:5]:
            keyword = (finding.keyword or "").strip()
            evidence = (finding.evidence or "").strip().replace("\n", " ")
            if evidence and len(evidence) > 72:
                evidence = evidence[:72] + "…"
            if keyword and evidence:
                lines.append(f"- 命中「{keyword}」：相关片段「{evidence}」")
            elif keyword:
                lines.append(f"- 命中「{keyword}」")
            elif evidence:
                lines.append(f"- 证据片段「{evidence}」")
    elif hits:
        lines.append(f"- 命中关键词：{'、'.join(hits[:5])}")
    else:
        lines.append("- 未返回显式关键词，请通读原文定位风险表述。")
    if category_hint:
        lines.append(f"- {category_hint}")
    if lineage_hint:
        lines.append(f"- {lineage_hint}")
    lines.append("- 建议动作：删除或替换命中片段 → 复跑 keyword/neuron → 再决定是否入训。")
    return "\n".join(lines)


def _risk_type_from_hit(hit: str) -> str:
    lowered = hit.lower()
    if any(keyword in lowered for keyword in ("爆炸", "炸药", "武器", "枪", "bomb")):
        return "dangerous_instruction_keyword"
    if any(keyword in lowered for keyword in ("隐私", "身份证", "手机号", "地址", "privacy")):
        return "privacy_keyword"
    if any(keyword in lowered for keyword in ("歧视", "刻板", "贬损", "仇恨", "hate")):
        return "bias_or_hate_keyword"
    return "keyword_hit"


def _evidence_chain_from_result(
    source_item: Topic2RiskScanItem,
    findings: list[Topic2KeywordFinding],
    status: str,
    score: float,
) -> list[str]:
    chain = [f"输入语料片段 #{source_item.lineage_node_id or source_item.lineage_node_label or '未绑定节点'}"]
    if source_item.lineage_node_label:
        chain.append(f"血缘节点：{source_item.lineage_node_label}")
    if source_item.risk_category_l1 or source_item.risk_category_l2:
        chain.append(
            f"评估标签：{source_item.risk_category_l1 or '未提供 L1'} / {source_item.risk_category_l2 or '未提供 L2'}"
        )
    else:
        chain.append("评估标签：实时 keyword 链路暂未提供 L1/L2")
    if findings:
        chain.append("命中证据：" + "、".join(finding.keyword for finding in findings))
    else:
        chain.append("命中证据：未命中显式关键词")
    chain.append(f"课题二判定：{status}，风险分 {score:.2f}")
    return chain


def _evidence_for_hit(text: str, hit: str) -> str:
    if not hit or hit not in text:
        return ""
    index = text.find(hit)
    start = max(index - 16, 0)
    end = min(index + len(hit) + 16, len(text))
    return text[start:end]
