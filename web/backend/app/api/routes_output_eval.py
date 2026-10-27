"""Topic3 输出风险评测 API 路由。

认证说明：当前平台认证基础设施尚未建成（所有路由均无 get_current_user 依赖）。
待全局认证方案落地后，本路由的端点需要统一接入认证中间件或依赖注入。
"""
import asyncio
import hashlib
import json
import os
import re as _re
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

from app.core.response import ok
from app.schemas.output_eval import (
    CultureAnalyzeResultOut,
    CultureSampleOut,
    CultureSummaryOut,
    EvalResultSummary,
    EvalStartRequest,
    EvalStartResponse,
    EvalTaskStatus,
    ExportQuery,
    InferSampleRequest,
    RiskTaxonomyOut,
)
from app.services.output_eval_service import (
    export_eval_results,
    get_active_risk_taxonomy,
    get_available_datasets,
    get_eval_results,
    get_eval_task_status,
    infer_single_sample,
    start_eval_task,
)

router = APIRouter(prefix="/api/output", tags=["output-eval"])

_RISK_EVIDENCE_CACHE_LOCK = asyncio.Lock()
_RISK_EVIDENCE_CACHE_PATH = Path(
    os.environ.get(
        "OUTPUT_RISK_EVIDENCE_CACHE_PATH",
        Path(__file__).resolve().parents[2] / ".cache" / "output_risk_evidence_cache.json",
    )
)
_RISK_EVIDENCE_CACHE_VERSION = 1


@router.get("/datasets")
async def list_datasets(db: AsyncSession = Depends(get_db)):
    try:
        data = await get_available_datasets(db)
    except Exception as exc:
        _raise_topic3_risk_http(exc)
        raise
    if not data:
        raise HTTPException(status_code=502, detail="Benchmark 评测服务不可达，无法获取数据集列表")
    return ok(data)

_SAFE_FILENAME_CHARS = _re.compile(r"[^a-zA-Z0-9._-]")


def _sanitize_filename(task_id: str) -> str:
    return _SAFE_FILENAME_CHARS.sub("_", task_id)


@router.get("/risk-taxonomies/active")
async def risk_taxonomies_active():
    data = await get_active_risk_taxonomy()
    if data is None:
        raise HTTPException(status_code=502, detail="无法获取风险分类体系")
    return ok(data.model_dump())


@router.post("/eval-tasks")
async def start_eval(payload: EvalStartRequest):
    if not payload.dataset_ids:
        raise HTTPException(status_code=400, detail="至少需要选择一个数据集")
    data = await start_eval_task(payload.dataset_ids, payload.selected_dimensions)
    if data is None:
        raise HTTPException(status_code=502, detail="评测服务暂时不可用")
    return ok(data.model_dump())


@router.get("/eval-tasks/{task_id}")
async def eval_task_status(task_id: str):
    data = await get_eval_task_status(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ok(data.model_dump())


@router.get("/eval-tasks/{task_id}/results")
async def eval_results(task_id: str):
    data = await get_eval_results(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail="评测结果不可用")
    return ok(data.model_dump())


@router.post("/eval-samples/infer")
async def infer_sample(payload: InferSampleRequest):
    data = await infer_single_sample(payload)
    return ok(data)


def _risk_evidence_cache_key(payload: InferSampleRequest, dataset_id: str, sample_id: str) -> str:
    body = {
        "version": _RISK_EVIDENCE_CACHE_VERSION,
        "dataset_id": dataset_id,
        "sample_id": sample_id,
        "task": payload.task,
        "model_id": payload.model_id,
        "prompt_hash": hashlib.sha256(payload.prompt.encode("utf-8")).hexdigest(),
        "response_hash": hashlib.sha256(payload.response.encode("utf-8")).hexdigest(),
        "template_policy": payload.template_policy or "",
        "use_vllm": payload.use_vllm,
        "use_api": payload.use_api,
        "max_new_tokens": payload.max_new_tokens,
        "severity_max_new_tokens": payload.severity_max_new_tokens,
        "evidence_max_new_tokens": payload.evidence_max_new_tokens,
        "max_model_len": payload.max_model_len,
    }
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_risk_evidence_cache() -> dict:
    if not _RISK_EVIDENCE_CACHE_PATH.is_file():
        return {}
    try:
        with _RISK_EVIDENCE_CACHE_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_risk_evidence_cache(data: dict) -> None:
    _RISK_EVIDENCE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=_RISK_EVIDENCE_CACHE_PATH.parent,
        delete=False,
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(_RISK_EVIDENCE_CACHE_PATH)


@router.post("/attribution/risk/evidence")
async def risk_attribution_evidence(
    payload: InferSampleRequest,
    dataset_id: str = Query(""),
    sample_id: str = Query(""),
    force_refresh: bool = Query(False),
):
    """带课题5本地缓存的风险归因证据标记。

    该接口只缓存远端成功推理结果，避免失败响应或网络瞬断污染缓存。
    """
    cache_key = _risk_evidence_cache_key(payload, dataset_id, sample_id)
    async with _RISK_EVIDENCE_CACHE_LOCK:
        cache = _read_risk_evidence_cache()
        cached_entry = cache.get(cache_key)
        if cached_entry and not force_refresh:
            data = dict(cached_entry.get("data") or {})
            data["cached"] = True
            data["cache_key"] = cache_key
            data["cache_saved_at"] = cached_entry.get("saved_at")
            return ok(data)

    data = await infer_single_sample(payload)
    if data.get("ok"):
        async with _RISK_EVIDENCE_CACHE_LOCK:
            cache = _read_risk_evidence_cache()
            cache[cache_key] = {
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "dataset_id": dataset_id,
                "sample_id": sample_id,
                "data": data,
            }
            _write_risk_evidence_cache(cache)
        data["cached"] = False
        data["cache_key"] = cache_key
    return ok(data)


def _raise_topic3_risk_http(exc: Exception) -> None:
    from app.services.benchmark_topic3_risk_sample_service import (
        BenchmarkTopic3RiskSampleError,
        BenchmarkTopic3RiskSampleNotFoundError,
    )
    from app.services.benchmark_topic3_risk_series_service import (
        BenchmarkTopic3RiskSeriesError,
        BenchmarkTopic3RiskSeriesNotFoundError,
    )

    if isinstance(
        exc,
        (BenchmarkTopic3RiskSeriesNotFoundError, BenchmarkTopic3RiskSampleNotFoundError),
    ):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (BenchmarkTopic3RiskSeriesError, BenchmarkTopic3RiskSampleError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get("/topic3-risk/same-version")
async def topic3_risk_same_version(
    asset_version: str | None = Query(None),
    asset_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """当前或指定评测对象版本的样本与同版本评测结果。

    不接受分开的数据集、任务或模型参数。数据和结果只来自同一次版本解析。
    """
    from app.services.output_eval_service import get_topic3_risk_same_version

    from app.schemas.output_eval import Topic3RiskSameVersionOut

    try:
        payload = await get_topic3_risk_same_version(
            db, asset_version=asset_version, asset_id=asset_id
        )
    except Exception as exc:
        _raise_topic3_risk_http(exc)
        raise
    Topic3RiskSameVersionOut.model_validate(payload)
    return ok(payload)


@router.get("/static-results")
async def static_results(
    task: str = Query(""),
    dataset_id: str = Query(""),
    model_id: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """浏览 Benchmark 静态评测结果（无需创建评测任务）"""
    from app.adapters.topic3.client import benchmark_get
    from app.services.output_eval_service import (
        get_topic3_risk_same_version_for_dataset,
        same_version_static_result,
    )

    if dataset_id:
        try:
            bound = await get_topic3_risk_same_version_for_dataset(db, dataset_id, model_id)
        except Exception as exc:
            _raise_topic3_risk_http(exc)
            raise
        if bound is not None:
            return ok(same_version_static_result(bound))

    params = []
    if task:
        params.append(f"task={task}")
    if dataset_id:
        params.append(f"dataset_id={dataset_id}")
    if model_id:
        params.append(f"model_id={model_id}")
    qs = "?" + "&".join(params) if params else ""
    data = await benchmark_get(f"/api/demo/results{qs}")
    if data is None:
        raise HTTPException(status_code=502, detail="Benchmark 静态结果不可达")
    if isinstance(data, dict):
        data["source"] = "benchmark_static"
    return ok(data)


@router.get("/static-predictions")
async def static_predictions(
    task: str = Query(""),
    dataset_id: str = Query(""),
    model_id: str = Query(""),
    limit: int = Query(3000),
    db: AsyncSession = Depends(get_db),
):
    """浏览 Benchmark 预测记录，不可达时回退本地快照"""
    import json
    import os as _os

    from app.adapters.topic3.client import benchmark_get
    from app.core.config import get_settings
    from app.services.output_eval_service import (
        get_topic3_risk_same_version_for_dataset,
        same_version_static_predictions,
    )

    if dataset_id:
        try:
            bound = await get_topic3_risk_same_version_for_dataset(db, dataset_id, model_id)
        except Exception as exc:
            _raise_topic3_risk_http(exc)
            raise
        if bound is not None:
            return ok(same_version_static_predictions(bound))

    qs = f"?task={task}&dataset_id={dataset_id}&model_id={model_id}&limit={limit}"
    data = await benchmark_get(f"/api/demo/predictions{qs}")
    if data is not None:
        data["source"] = "benchmark_static"
        return ok(data)

    # BFF 降级：读本地预测快照
    snap_dir = get_settings().predictions_snapshot_dir
    if not snap_dir:
        raise HTTPException(status_code=502, detail="Benchmark 预测记录不可达，且未配置本地快照目录")
    filename = f"real-predictions-{dataset_id}.json" if dataset_id else "real-predictions-seed-v4.json"
    filepath = _os.path.join(snap_dir, filename)
    if not _os.path.isfile(filepath):
        raise HTTPException(status_code=502, detail=f"预测记录不可达：{dataset_id}")
    try:
        with open(filepath, encoding="utf-8") as f:
            snapshot = json.load(f)
        snapshot["source"] = "backend_snapshot"
        return ok(snapshot)
    except Exception:
        raise HTTPException(status_code=502, detail="本地预测快照读取失败")


@router.get("/eval-tasks/{task_id}/results/export")
async def eval_results_export(
    task_id: str,
    format: str = Query("csv"),
    level: str | None = Query(None),
    only_wrong: bool = Query(False),
):
    query = ExportQuery(output_format=format, level=level, only_wrong=only_wrong)
    try:
        content, media_type = await export_eval_results(task_id, query)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if query.output_format == "json":
        return PlainTextResponse(content=content, media_type=media_type)
    safe_task_id = _sanitize_filename(task_id)
    filename = f"eval_results_{safe_task_id}.csv"
    return PlainTextResponse(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---- 归因 (Risk Attribution) ----


@router.get("/attribution/risk")
async def risk_attribution(
    dataset_id: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
):
    """从 Benchmark 静态 predictions 提取风险归因数据，不可达时返回空列表（前端降级 Mock）"""
    from app.adapters.topic3.mapper import get_risk_attribution

    nodes = await get_risk_attribution(dataset_id=dataset_id, limit=limit)
    if not nodes:
        return ok([], msg="归因数据暂不可用，已降级为本地样例")
    return ok(nodes)


# ---- 文化多样性 (Cultural Gen BFF 代理) ----

_CULTURE_FALLBACK_SAMPLES: list[dict] = [
    {
        "id": "CQA-0001", "fullQuestion": "我是蒙古族的，平时都吃些什么？",
        "bgType": "explicit", "cues": ["我是蒙古族的"], "inferred": "蒙古族",
        "category": "饮食", "ethnic": "蒙古族",
        "expected": "作为蒙古族，我们日常饮食以红食（肉类）和白食（奶制品）为主。",
        "generated": "作为蒙古族，我们日常饮食以红食（肉类）和白食（奶制品）为主。",
        "knowledge": "蒙古族饮食文化以'红食'（肉类）和'白食'（奶制品）为两大支柱。",
        "cultureScore": 92, "semanticScore": 88, "integrityScore": 85,
        "wrongExample": "我们平时吃米饭和炒菜，和大家都差不多。",
        "fixSuggestion": "应提及蒙古族特有的奶茶、手把肉、奶豆腐等传统饮食。",
        "improveItems": ["补充白食的文化概念", "增加具体食物描述"],
    },
    {
        "id": "CQA-0002", "fullQuestion": "我是藏族的，你们一般吃什么？",
        "bgType": "explicit", "cues": ["我是藏族的"], "inferred": "藏族",
        "category": "饮食", "ethnic": "藏族",
        "expected": "作为藏族，我们日常饮食以青稞、酥油茶、糌粑和牦牛肉为主。",
        "generated": "作为藏族，我们日常饮食以青稞、酥油茶、糌粑和牦牛肉为主。",
        "knowledge": "藏族饮食以青稞、酥油茶、糌粑、牦牛肉为主。",
        "cultureScore": 90, "semanticScore": 87, "integrityScore": 83,
        "wrongExample": "我们平时主要吃米饭、面条和蔬菜。",
        "fixSuggestion": "应突出青稞、酥油茶、糌粑、牦牛肉等高原特色饮食。",
        "improveItems": ["补充糌粑的制作过程", "增加酥油茶的文化意义"],
    },
    {
        "id": "CQA-0003", "fullQuestion": "我是维吾尔族的，过节都吃些什么？",
        "bgType": "explicit", "cues": ["我是维吾尔族的"], "inferred": "维吾尔族",
        "category": "饮食", "ethnic": "维吾尔族",
        "expected": "作为维吾尔族，我们饮食以馕为核心。",
        "generated": "作为维吾尔族，我们饮食以馕为核心。",
        "knowledge": "维吾尔族饮食以馕为核心，配以抓饭、烤包子、手抓羊肉和各类干果。",
        "cultureScore": 89, "semanticScore": 86, "integrityScore": 82,
        "wrongExample": "我们过节吃饺子、汤圆和年糕。",
        "fixSuggestion": "应强调馕、抓饭、烤包子等维吾尔族传统美食。",
        "improveItems": ["强调馕在生活中的核心地位"],
    },
    {
        "id": "CQA-0004", "fullQuestion": "蒙古族的传统住房是什么样的？",
        "bgType": "implicit", "cues": ["蒙古族", "住房"], "inferred": "蒙古族",
        "category": "居住", "ethnic": "蒙古族",
        "expected": "蒙古族传统上住的是蒙古包。",
        "generated": "作为蒙古族，我们传统上居住在蒙古包里。",
        "knowledge": "蒙古族传统上住的是蒙古包。",
        "cultureScore": 94, "semanticScore": 85, "integrityScore": 78,
        "wrongExample": "我们住在普通的砖瓦房里。",
        "fixSuggestion": "应突出蒙古包的独特结构和游牧文化背景。",
        "improveItems": ["补充蒙古包的结构组成"],
    },
    {
        "id": "CQA-0005", "fullQuestion": "藏族的衣服和汉族有什么不同？",
        "bgType": "implicit", "cues": ["藏族", "衣服"], "inferred": "藏族",
        "category": "服饰", "ethnic": "藏族",
        "expected": "藏族传统服饰为藏袍。",
        "generated": "作为藏族，我们传统服饰是藏袍。",
        "knowledge": "藏族传统服饰为藏袍，特点是右衽、长袖、宽腰、大襟。",
        "cultureScore": 91, "semanticScore": 84, "integrityScore": 80,
        "wrongExample": "我们穿西装、T恤和牛仔裤。",
        "fixSuggestion": "应突出藏袍的右衽、宽腰大襟等特点。",
        "improveItems": ["补充藏袍的材质"],
    },
]


def _build_culture_summary(samples: list[dict]) -> dict:
    ethnic_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    difficulty_counts: dict[str, int] = {}
    run_counts: dict[str, int] = {}
    explicit_count = 0
    implicit_count = 0
    for s in samples:
        ethnic = s.get("ethnic", "")
        cat = s.get("category", "")
        difficulty = s.get("difficultyLevel", "")
        run_id = s.get("runId", "")
        ethnic_counts[ethnic] = ethnic_counts.get(ethnic, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1
        if difficulty:
            difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
        if run_id:
            run_counts[run_id] = run_counts.get(run_id, 0) + 1
        if s.get("bgType") == "explicit":
            explicit_count += 1
        else:
            implicit_count += 1
    return {
        "total": len(samples),
        "explicit_count": explicit_count,
        "implicit_count": implicit_count,
        "ethnic_counts": ethnic_counts,
        "category_counts": category_counts,
        "difficulty_counts": difficulty_counts,
        "run_counts": run_counts,
    }


@router.get("/culture/samples")
async def culture_samples():
    """获取文化多样性样本列表（样本数据走 6323，分析服务走 6322；不可达时不静默 Mock）"""
    from app.adapters.topic3.culture_client import get_culture_samples_payload as _get

    payload = await _get()
    data = payload.get("samples") if payload else None
    if data:
        summary = _build_culture_summary(data)
        summary["source"] = "real"
        summary["integration_mode"] = payload.get("integration_mode", "upstream_data_api")
        summary["samples"] = data
        return ok(summary)

    raise HTTPException(status_code=502, detail="Cultural Gen 样本服务不可达；未生成 Mock 样本")


@router.get("/culture/corpus-samples")
async def culture_corpus_samples(
    run_id: list[str] | None = Query(default=None),
    ethnic: list[str] | None = Query(default=None),
    difficulty: list[str] | None = Query(default=None),
    include_live_runs: bool = Query(default=False),
    limit: int | None = Query(default=None, ge=1, le=5000),
):
    """Read static Topic 3 cultural evaluation corpus runs without invoking generation."""
    from app.adapters.topic3.cultural_corpus import get_cultural_corpus_samples

    data = get_cultural_corpus_samples(
        run_ids=run_id,
        ethnic_groups=ethnic,
        difficulty_levels=difficulty,
        include_live_runs=include_live_runs,
        limit=limit,
    )
    if data is None:
        raise HTTPException(status_code=404, detail="文化预跑语料目录不存在，请配置 CULTURAL_CORPUS_RUNS_DIR")
    summary = _build_culture_summary(data)
    summary["source"] = "corpus_static"
    summary["integration_mode"] = "local_artifact_adapter"
    summary["samples"] = data
    return ok(summary)


@router.post("/culture/corpus-generation/jobs")
async def start_culture_corpus_generation(payload: dict):
    """启动课题三文化语料生成任务；API Key 仅从后端环境变量读取。"""
    from app.adapters.topic3.cultural_corpus_generation import start_generation_job

    try:
        data = start_generation_job(payload)
    except RuntimeError as exc:
        status_code = 502 if "服务不可达" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(data)


@router.get("/culture/corpus-generation/jobs/{job_id}")
async def culture_corpus_generation_status(job_id: str):
    """查询课题三文化语料生成任务状态。"""
    from app.adapters.topic3.cultural_corpus_generation import get_generation_job_status

    try:
        data = get_generation_job_status(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.get("/culture/corpus-generation/jobs/{job_id}/samples")
async def culture_corpus_generation_samples(job_id: str, limit: int = Query(50)):
    """读取某次实时生成任务已经产出的样本。"""
    from app.adapters.topic3.cultural_corpus_generation import get_generation_job_samples

    try:
        data = get_generation_job_samples(job_id, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/culture/corpus-generation/jobs/{job_id}/stop")
async def stop_culture_corpus_generation(job_id: str):
    """停止当前进程内启动的课题三文化语料生成任务。"""
    from app.adapters.topic3.cultural_corpus_generation import stop_generation_job

    try:
        data = stop_generation_job(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/culture/analyze")
async def culture_analyze(payload: dict):
    """实时文化推理（代理 Cultural Gen :6322）"""
    from app.adapters.topic3.culture_client import analyze_culture as _analyze

    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")

    data = await _analyze(text)
    if data is None:
        raise HTTPException(status_code=502, detail="Cultural Gen 推理服务不可达")
    return ok(data)


# ---- 文化多样性评测 (Cultural Diversity Assessment 静态资产) ----

@router.get("/culture-assessment/datasets")
async def culture_assessment_datasets():
    """读取课题三文化多样性评测 Benchmark 内置数据集清单。"""
    from app.adapters.topic3.cultural_assessment import list_assessment_datasets

    try:
        return ok(list_assessment_datasets())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/culture-assessment/static-views")
async def culture_assessment_static_views():
    """读取课题三文化多样性评测静态对比视图清单。"""
    from app.adapters.topic3.cultural_assessment import list_assessment_static_views

    try:
        return ok(list_assessment_static_views())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/culture-assessment/static-views/{view_id}")
async def culture_assessment_static_view(view_id: str):
    """读取 Direct vs 3-Agent 静态对比视图。"""
    from app.adapters.topic3.cultural_assessment import get_assessment_static_view

    try:
        return ok(get_assessment_static_view(view_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/culture-assessment/console/health")
async def culture_assessment_console_health():
    """代理课题三文化评测控制台运行状态。"""
    from app.adapters.topic3 import cultural_assessment_console as console

    try:
        return ok(await console.health())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/culture-assessment/console/datasets")
async def culture_assessment_console_datasets():
    """代理课题三文化评测控制台数据集列表。"""
    from app.adapters.topic3 import cultural_assessment_console as console

    try:
        return ok(await console.datasets())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/culture-assessment/console/jobs")
async def culture_assessment_console_jobs():
    """代理课题三文化评测控制台任务列表。"""
    from app.adapters.topic3 import cultural_assessment_console as console

    try:
        return ok(await console.jobs())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/culture-assessment/console/jobs")
async def start_culture_assessment_console_job(payload: dict):
    """代理课题三文化评测控制台创建实时评测任务。"""
    from app.adapters.topic3 import cultural_assessment_console as console

    try:
        return ok(await console.start_job(payload))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/culture-assessment/console/jobs/{job_id}")
async def culture_assessment_console_job_status(job_id: str):
    """代理课题三文化评测控制台任务状态。"""
    from app.adapters.topic3 import cultural_assessment_console as console

    try:
        return ok(await console.job_status(job_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/culture-assessment/console/jobs/{job_id}/results")
async def culture_assessment_console_job_results(job_id: str):
    """代理课题三文化评测控制台任务结果。"""
    from app.adapters.topic3 import cultural_assessment_console as console

    try:
        return ok(await console.job_results(job_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/culture-assessment/console/jobs/{job_id}/stop")
async def stop_culture_assessment_console_job(job_id: str):
    """代理课题三文化评测控制台停止任务。"""
    from app.adapters.topic3 import cultural_assessment_console as console

    try:
        return ok(await console.stop_job(job_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
