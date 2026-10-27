"""Topic3 output eval: taxonomy, task lifecycle, and results mappers."""
from __future__ import annotations
import csv
import io as _io
import json
import logging
import re as _re
import uuid as _uuid
from urllib.parse import urlencode

from app.schemas.output_eval import (
    DatasetSummary,
    EvalLogEntry,
    EvalMetrics,
    EvalResultSummary,
    EvalSampleOut,
    EvalStartResponse,
    EvalTaskStatus,
    ExportQuery,
    InferSampleResponse,
    InferStep,
    RiskCategory,
    RiskTaxonomyOut,
    SubcategoryItem,
    ThresholdDefaults,
)

from .client import (
    BENCHMARK_BASE,
    benchmark_get,
    benchmark_post,
    get_task_meta,
    register_task_job,
    resolve_job_id,
    store_task_meta,
    utcnow,
)
from .mock_data import (
    _build_dataset_metrics,
    _build_grouped_metrics,
    _build_multi_dataset_radar,
    _build_radar,
)

logger = logging.getLogger(__name__)

# UUID task_id only. Mock task ids are no longer accepted by the output adapter.
_TASK_ID_RE = _re.compile(r"^(?:[a-f0-9-]{36}|[a-f0-9]{32})$")

# selected_dimensions 未保存时的回退维度（旧任务兼容）
_FALLBACK_DIMENSIONS: list[str] = [f"C{i:02d}" for i in range(1, 18)]

# 映射表用冻结字典型（不可变类别映射）
_CATEGORY_MAP: dict[str, str] = {
    "C01": "culture", "C02": "culture", "C03": "culture",
    "C04": "culture", "C05": "culture", "C06": "culture",
    "C07": "ai4sci", "C08": "culture", "C09": "ai4sci",
    "C10": "culture", "C11": "ai4sci", "C12": "ai4sci",
    "C13": "culture", "C14": "ai4sci", "C15": "culture",
    "C16": "culture", "C17": "culture",
}

_CATEGORY_LEVEL_MAP: dict[str, str] = {
    "C01": "HIGH", "C02": "HIGH", "C03": "HIGH", "C04": "HIGH",
    "C05": "HIGH", "C06": "MEDIUM", "C07": "MEDIUM", "C08": "MEDIUM",
    "C09": "MEDIUM", "C10": "MEDIUM", "C11": "LOW", "C12": "MEDIUM",
    "C13": "HIGH", "C14": "HIGH", "C15": "HIGH", "C16": "MEDIUM",
    "C17": "MEDIUM",
}


# ---- Helpers ----

def _validate_task_id(task_id: str) -> bool:
    return bool(_TASK_ID_RE.match(task_id))


def _derive_category(cat_id: str, name: str) -> str:
    if cat_id in _CATEGORY_MAP:
        return _CATEGORY_MAP[cat_id]
    return "culture"


def _derive_level(cat_id: str) -> str:
    return _CATEGORY_LEVEL_MAP.get(cat_id, "MEDIUM")


def _error_status(task_id: str, detail: str) -> EvalTaskStatus:
    return EvalTaskStatus(
        task_id=task_id, status="error", stage_label=detail, source="error",
        logs=[EvalLogEntry(time=utcnow(), level="error", message=detail)],
        artifacts={"retryable": "true", "source": "error"},
    )


# ---- Risk Taxonomy ----

async def get_active_risk_taxonomy() -> RiskTaxonomyOut | None:
    data = await benchmark_get("/api/taxonomies")
    if not data:
        return None  # Benchmark 不可达 → route 返回 502，与 /datasets 对齐
    items = data if isinstance(data, list) else []
    active = next((t for t in items if t.get("is_active")), None)
    if not active and items:
        active = items[0]
    if not active:
        return None
    tax_id = active.get("id", 0)
    detail = await benchmark_get(f"/api/taxonomies/{tax_id}")
    if not detail:
        return None  # Benchmark 不可达 → 502
    content = detail.get("content", {}) if isinstance(detail, dict) else {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            content = {}
    raw_categories = content.get("categories", [])
    categories: list[RiskCategory] = []
    for cat in raw_categories:
        cat_id = cat.get("id", f"cat-{len(categories)}")
        cat_name = cat.get("name", "")
        subcats = [SubcategoryItem(key=s.get("id", ""), label=s.get("name", "")) for s in cat.get("subcategories", [])]
        categories.append(RiskCategory(
            key=cat_id, label=cat_name,
            category=_derive_category(cat_id, cat_name),
            level=_derive_level(cat_id),
            selected=True,
            definition=cat.get("definition", ""),
            subcategories=subcats,
        ))
    return RiskTaxonomyOut(
        taxonomy_id=tax_id, taxonomy_name=active.get("name", "unknown"),
        version=active.get("updated_at", ""), categories=categories, threshold_defaults=ThresholdDefaults(),
    )


# ---- Available Datasets ----

# 课题三风险系列的版本、条数和结果由 Benchmark 版本解析提供。
# 演示目录不能再把某一版资产或固定条数写成事实来源。
# 这里过滤 versioned series 是刻意行为：当前版本由 output_eval_service 注入，
# 上游目录既没有 record_count，也会把同一版本重复放进多个 task 分组。
_TOPIC3_SERIES_DATASET_PREFIX = "Risk_Hierarchical_Classification_Benchmark_"

_FALLBACK_BENCHMARK_DATASETS: list[dict[str, str]] = [
    {
        "id": "seed_v1_1_response_en",
        "name": "seed-v1.1 多语言评测集",
        "description": "展示原始多语言评测数据；模型评测实际使用 response 翻译成英文后的数据。",
    },
    {
        "id": "seed_v2_multilabel",
        "name": "seed-v2 多标签评测集",
        "description": "BingoGuard 与人工构建数据整合后的多标签风险分类、逐类别分级评测结果。",
    },
    {
        "id": "seed_v3_multilabel",
        "name": "seed-v3 多标签评测集",
        "description": "Seed-v3多标签风险分类与逐类别分级数据集上的评测结果。",
    },
    {
        "id": "seed_v4_multilabel",
        "name": "seed-v4 多标签评测集",
        "description": "Seed-v4多标签风险分类与逐类别分级数据集上的评测结果。",
    },
]

_HIDDEN_BENCHMARK_DATASET_IDS = {
    "infer_examples",
    "safety_bingo",
    "safety_bingo_testset",
    "safety_bingo_ti",
}


def _is_topic3_series_dataset(dataset_id: str) -> bool:
    return dataset_id.startswith(_TOPIC3_SERIES_DATASET_PREFIX)


def _map_benchmark_dataset(group_name: str, item: dict) -> dict:
    ds_id = item.get("id", "")
    record_count = 988
    is_tibetan_dataset = ds_id.endswith("_ti") or ds_id == "safety_bingo_ti"
    return {
        "id": ds_id,
        "name": item.get("name", ds_id),
        "type": "science" if is_tibetan_dataset else "culture",
        "subType": f"benchmark-{group_name}",
        "description": item.get("description", ""),
        "recordCount": record_count,
        "language": "藏语" if is_tibetan_dataset else "中文",
        "riskLevel": "MEDIUM",
        "createdAt": "",
        "updatedAt": "",
    }


async def get_available_datasets() -> list[dict] | None:
    data = await benchmark_get("/api/demo/options")
    if not data:
        logger.warning(
            "Benchmark /api/demo/options unavailable; using static dataset catalog fallback",
        )
        return [
            _map_benchmark_dataset("risk_classification", item)
            for item in _FALLBACK_BENCHMARK_DATASETS
            if not _is_topic3_series_dataset(str(item.get("id", "")))
        ]
    datasets_raw = data.get("datasets", {}) if isinstance(data, dict) else {}
    result: list[dict] = []
    for group_name, items in datasets_raw.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if item.get("id") in _HIDDEN_BENCHMARK_DATASET_IDS or item.get("name") in _HIDDEN_BENCHMARK_DATASET_IDS:
                continue
            if _is_topic3_series_dataset(str(item.get("id", ""))):
                continue
            result.append(_map_benchmark_dataset(group_name, item))
    return result


# ---- Eval Task Lifecycle ----

_MOCK_TO_REAL_DATASET = {
    "ds-science-001": "safety_bingo",
    "ds-science-002": "safety_bingo",
    "ds-science-003": "safety_bingo",
    "ds-science-004": "safety_bingo",
    "ds-science-005": "safety_bingo",
    "ds-science-006": "safety_bingo",
}


async def start_eval_task(dataset_ids: list[str], selected_dimensions: list[str] | None = None) -> EvalStartResponse | None:
    if not dataset_ids:
        return None
    # 当前 Benchmark run_eval 仅支持单数据集执行；多数据集循环 + 聚合待后续实现
    dataset_id = dataset_ids[0]
    dataset_id = _MOCK_TO_REAL_DATASET.get(dataset_id, dataset_id)
    is_v6 = dataset_id == "Risk_Hierarchical_Classification_Benchmark_v6"
    data = await benchmark_post("/api/demo/run_eval", {
        "task": "joint_level_then_multilabel" if is_v6 else "binary",
        "dataset_id": dataset_id,
        "model_id": "qwen3.5-9B-V7" if is_v6 else "bingoguard-local",
        "use_vllm": bool(is_v6),
        "response_only": True if is_v6 else False,
    })
    if not data:
        return None
    job_id = data.get("job_id")
    if not job_id:
        logger.warning("Benchmark run_eval 响应缺少 job_id，视为启动失败")
        return None
    task_id = job_id
    await register_task_job(task_id, job_id)
    if selected_dimensions:
        await store_task_meta(task_id, {"selected_dimensions": selected_dimensions})
    return EvalStartResponse(task_id=task_id, status="running", task_type="output_risk_eval", created_at=utcnow())


async def get_eval_task_status(task_id: str) -> EvalTaskStatus | None:
    if not _validate_task_id(task_id):
        return _error_status(task_id, "无效的 task_id 格式")
    job_id = await resolve_job_id(task_id)
    if job_id is None:
        return _error_status(task_id, "任务未注册，无法查询状态")
    data = await benchmark_get(f"/api/demo/job/{job_id}")
    if not data:
        return _error_status(task_id, "评测服务不可达，请检查 Benchmark 后重试")
    status_raw = data.get("status", "running")
    if status_raw in ("error", "failed"):
        return EvalTaskStatus(
            task_id=task_id, status="error", stage_label="评测执行失败", source="benchmark",
            logs=[EvalLogEntry(time=utcnow(), level="error", message=data.get("log_tail", "未知错误")[:2000])],
        )
    progress, stage, stage_label = 0.0, "pending", "等待中"
    if status_raw == "running":
        progress, stage, stage_label = 0.5, "evaluating", "正在执行风险评测"
    elif status_raw == "finished":
        progress, stage, stage_label = 1.0, "done", "评测完成"
    log_tail = data.get("log_tail", "")
    logs = [EvalLogEntry(time=utcnow(), level="info", message=l.strip()[:500]) for l in log_tail.strip().split("\n")[-20:] if l.strip()] if log_tail else []
    artifacts = {k: data[k] for k in ("run_name", "log_path") if data.get(k)}
    return EvalTaskStatus(
        task_id=task_id, status=status_raw, progress=progress, stage=stage, stage_label=stage_label,
        created_at=data.get("created_at", utcnow()), logs=logs, artifacts=artifacts, source="benchmark",
    )


# ---- Eval Results ----

async def get_eval_results(task_id: str) -> EvalResultSummary | None:
    if not _validate_task_id(task_id):
        return None
    # 优先内存 → DB fallback → 全量兜底（兼容旧任务 / 重启 / mock 路径）
    meta = await get_task_meta(task_id)
    selected_dimensions: list[str] | None = meta.get("selected_dimensions") if meta else None
    if not selected_dimensions:
        from app.services.output_eval_store import get_task_dimensions as _db_dims
        selected_dimensions = await _db_dims(task_id)
    if not selected_dimensions:
        selected_dimensions = list(_FALLBACK_DIMENSIONS)

    job_id = await resolve_job_id(task_id)
    if job_id is None:
        return None
    results_data = await benchmark_get(f"/api/demo/results?task=binary&job_id={job_id}")
    if not results_data:
        return None
    selected = results_data.get("selected") if isinstance(results_data, dict) else None
    if not selected:
        return None
    metrics_raw = selected.get("metrics", {})
    ba = round(metrics_raw.get("accuracy_safe_unsafe", 0.0), 3)
    rr = round(metrics_raw.get("risk_recall", 0.0), 3)
    metrics = EvalMetrics(
        binary_safe_acc=ba, risk_class_acc=round(metrics_raw.get("risk_class_accuracy_v1", 0.0), 3),
        severity_acc=round(metrics_raw.get("risk_class_accuracy_v2", 0.0), 3),
        accuracy=ba, precision=round(metrics_raw.get("precision_safe_unsafe", 0.0), 3),
        recall=round(metrics_raw.get("recall", rr), 3), f1=round(metrics_raw.get("f1_safe_unsafe", 0.0), 3),
        risk_recall=rr, fpr=round(metrics_raw.get("fpr", 0.0), 3),
    )
    pp = selected.get("paths", {}).get("predictions", "")
    pd = await benchmark_get(
        f"/api/demo/predictions?task=binary&dataset_id={selected.get('dataset_id', '')}&model_id={selected.get('model_id', '')}&limit=50"
    ) if pp else None
    rows = []
    if pd and isinstance(pd, dict):
        for i, row in enumerate(pd.get("rows", [])):
            example = row.get("example", {}) if isinstance(row, dict) else {}
            text = example.get("response", "") or example.get("prompt", "") or str(row.get("text", ""))
            pred_categories = row.get("pred_categories") or []
            gold_categories = row.get("gold_categories") or []
            pred_level = row.get("pred_level", example.get("risk_level_id", 0))
            gold_level = row.get("gold_level", example.get("risk_level_id", ""))
            ol = _level_from_value(pred_level)
            pred_category_code = _join_category_codes(pred_categories)
            gold_category_code = _join_category_codes(gold_categories)
            dimension_scores: dict[str, str] = {}
            pred_category_levels = row.get("pred_category_levels") or {}
            if isinstance(pred_category_levels, dict):
                for cat_id, level in pred_category_levels.items():
                    dimension_scores[_parse_category_id(str(cat_id))] = _level_from_value(level)
            if not dimension_scores and pred_category_code:
                for cat_id in pred_category_code.split(","):
                    if cat_id:
                        dimension_scores[cat_id] = ol
            rows.append(EvalSampleOut(
                id=f"eval-{i + 1:04d}",
                text=str(text),
                dimension_scores=dimension_scores or {"综合评分": ol},
                overall_level=ol,
                overall_score=LEVEL_WEIGHT.get(ol, 0.35),
                summary=str(row.get("raw_classification", ""))[:500],
                dataset_id=str(selected.get("dataset_id", "")),
                dataset_name=str(selected.get("dataset_id", "")),
                gold_binary_label=row.get("gold_binary_label"),
                pred_binary_label=row.get("pred_binary_label"),
                gold_category=gold_category_code,
                gold_category_code=gold_category_code,
                pred_category=pred_category_code,
                pred_category_code=pred_category_code,
                gold_level=_level_from_value(gold_level),
                pred_level=ol,
                is_correct=row.get("gold_binary_label") == row.get("pred_binary_label"),
                is_category_correct=bool(
                    row.get("risk_class_correct_v5_exact_match")
                    or row.get("risk_class_correct_v3")
                ),
            ))
    hc = sum(1 for r in rows if r.overall_level == "HIGH")
    mc = sum(1 for r in rows if r.overall_level == "MEDIUM")
    lc = sum(1 for r in rows if r.overall_level == "LOW")
    summary = EvalResultSummary(
        task_id=task_id, config_id="risk-benchmark-v1", source="benchmark",
        dataset_summary=DatasetSummary(sample_total=len(rows), high_count=hc, medium_count=mc, low_count=lc, selected_dimension_count=len(selected_dimensions)),
        radar_risk_data=_build_radar(rows, selected_dimensions),
        radar_multi_dataset=_build_multi_dataset_radar(rows, selected_dimensions),
        samples=rows, metrics=metrics, dataset_metrics=_build_dataset_metrics(rows),
        grouped_metrics=_build_grouped_metrics(rows),
        artifacts={"metrics_ref": selected.get("paths", {}).get("metrics", ""), "predictions_ref": pp},
        created_at=utcnow(),
    )
    return summary


# ---- Single-Sample Dynamic Inference ----

async def infer_single_sample(payload) -> dict:
    """代理 Benchmark 单条数据动态推理，返回步骤化推理结果。"""
    data = await benchmark_post(
        "/api/demo/infer",
        {
            "task": payload.task,
            "model_id": payload.model_id,
            "prompt": payload.prompt,
            "response": payload.response,
            "template_policy": payload.template_policy,
            "use_vllm": payload.use_vllm,
            "use_api": payload.use_api,
            "max_new_tokens": payload.max_new_tokens,
            "severity_max_new_tokens": payload.severity_max_new_tokens,
            "evidence_max_new_tokens": payload.evidence_max_new_tokens,
            "max_model_len": payload.max_model_len,
        },
        timeout=900.0,
    )
    if not data:
        return InferSampleResponse(
            ok=False,
            source="unavailable",
            cached=False,
            pred_safe_type="error",
            raw_response=(
                f"无法连接到 Benchmark 推理服务。\n"
                f"目标地址: {BENCHMARK_BASE}/api/demo/infer\n"
                f"请检查:\n"
                f"  1. Benchmark 服务是否已启动\n"
                f"  2. 网络是否能访问 {BENCHMARK_BASE}\n"
                f"  3. 如使用远程服务，确认 --benchmark=remote 参数已传入"
            ),
            stderr=f"POST {BENCHMARK_BASE}/api/demo/infer 连接失败",
            steps=[
                InferStep(
                    name="Benchmark 服务连接",
                    status="error",
                    detail=(
                        f"无法连接到 {BENCHMARK_BASE}\n"
                        f"该错误发生在课题5后端 → Benchmark 的网络连接层，\n"
                        f"尚未到达远程推理引擎。"
                    ),
                )
            ],
        ).model_dump()
    # 远程 Benchmark 返回了响应，但推理可能失败 — 透传完整的远程错误信息
    if not data.get("ok"):
        # 确保 source 标记为 remote，便于前端区分本地/远程错误
        if not data.get("source"):
            data["source"] = "remote"
        # 确保有足够的错误信息展示
        if not data.get("steps"):
            data["steps"] = [
                InferStep(
                    name="远程推理",
                    status="error",
                    detail=data.get("stderr") or data.get("raw_response") or "远程推理引擎返回错误",
                ).model_dump()
            ]
    return data


# ---- Export ----

async def export_eval_results(task_id: str, query: ExportQuery) -> tuple[str, str]:
    summary = await get_eval_results(task_id)
    if not summary:
        raise LookupError("eval results unavailable; no mock export was generated")
    samples = summary.samples
    if query.level:
        samples = [s for s in samples if s.overall_level == query.level]
    if query.only_wrong:
        samples = [s for s in samples if s.is_correct is False]
    if query.output_format == "json":
        return json.dumps([s.model_dump() for s in samples], ensure_ascii=False, indent=2), "application/json; charset=utf-8"
    output = _io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["id", "text", "overall_level", "overall_score", "summary",
                     "gold_category_code", "pred_category_code", "gold_level", "pred_level", "is_correct"])
    for s in samples:
        text = s.text
        if text and text[0] in ("=", "+", "-", "@"):
            text = "'" + text
        writer.writerow([s.id, text, s.overall_level, str(s.overall_score), s.summary,
                         s.gold_category_code, s.pred_category_code, s.gold_level, s.pred_level, str(s.is_correct)])
    return output.getvalue(), "text/csv; charset=utf-8"


# ---- Risk Attribution ----

# 标准 C01-C17 风险类别标签映射（从 seed-v1.1 taxonomy 提取）
_RISK_CATEGORY_LABELS: dict[str, str] = {
    "C01": "煽动颠覆国家政权",
    "C02": "危害国家安全",
    "C03": "破坏国家统一、领土完整",
    "C04": "宣扬恐怖主义、极端主义",
    "C05": "煽动民族仇恨、民族歧视",
    "C06": "宣扬暴力、淫秽色情",
    "C07": "危害社会公德",
    "C08": "侮辱诽谤他人",
    "C09": "侵犯知识产权",
    "C10": "泄露国家秘密",
    "C11": "破坏民族团结",
    "C12": "破坏宗教政策",
    "C13": "散布谣言",
    "C14": "宣扬邪教、封建迷信",
    "C15": "宣扬赌博、暴力凶杀",
    "C16": "教唆犯罪",
    "C17": "危害社会秩序",
}

LEVEL_LABEL: dict[int, str] = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "LOW"}
LEVEL_WEIGHT: dict[str, float] = {"HIGH": 0.85, "MEDIUM": 0.65, "LOW": 0.35}


def _short_label(cat_id: str) -> str:
    """返回 C01-C17 的短标签，未知时返回 cat_id 本身"""
    return _RISK_CATEGORY_LABELS.get(cat_id, cat_id)


def _parse_category_id(raw: str) -> str:
    """从 'C04宣扬恐怖主义、极端主义' 中提取 'C04'"""
    m = _re.match(r"(C\d{2})", str(raw))
    return m.group(1) if m else str(raw)[:3] if len(str(raw)) >= 3 else str(raw)


def _level_from_value(value: object) -> str:
    if isinstance(value, (int, float)):
        return LEVEL_LABEL.get(int(value), "LOW")
    raw = str(value or "").upper()
    if raw in {"HIGH", "MEDIUM", "LOW"}:
        return raw
    if raw in {"3", "LEVEL_3", "HIGH_RISK", "高风险"}:
        return "HIGH"
    if raw in {"2", "LEVEL_2", "MEDIUM_RISK", "中风险"}:
        return "MEDIUM"
    return "LOW"


def _join_category_codes(values: object) -> str:
    if isinstance(values, list):
        return ",".join(_parse_category_id(str(item)) for item in values)
    if values is None:
        return ""
    return _parse_category_id(str(values))


def _path_exists_safely(path) -> bool:
    try:
        return path.exists()
    except OSError as exc:
        logger.warning(
            "Risk attribution: predictions file is not accessible: %s (%s)",
            path,
            exc,
        )
        return False


def _build_attribution_chain(
    gold_cats: list[str],
    pred_cats: list[str],
    pred_level: int,
) -> str:
    gold_str = "+".join(gold_cats[:2]) if gold_cats else "未标注"
    pred_str = "+".join(pred_cats[:2]) if pred_cats else "未预测"
    lv = LEVEL_LABEL.get(pred_level, "LOW")
    return f"真实标注({gold_str}) → 模型预测({pred_str}) → 综合风险等级({lv})"


def _build_reason_path(
    example: dict,
    pred_level: int,
) -> str:
    subcats_raw = example.get("risk_sub_category", [])
    if isinstance(subcats_raw, str):
        try:
            subcats = json.loads(subcats_raw)
        except (json.JSONDecodeError, TypeError):
            subcats = [subcats_raw]
    else:
        subcats = subcats_raw
    if isinstance(subcats, list) and subcats:
        parts = []
        for s in subcats[:2]:
            if isinstance(s, str) and "：" in s:
                parts.append(s.split("：", 1)[1][:60])
            elif isinstance(s, str):
                parts.append(s[:60])
        if parts:
            return " + ".join(parts)
    risk_cat_raw = example.get("risk_category", "")
    if isinstance(risk_cat_raw, str) and risk_cat_raw.startswith("["):
        try:
            risk_cat_raw = json.loads(risk_cat_raw)
        except (json.JSONDecodeError, TypeError):
            pass
    if isinstance(risk_cat_raw, list):
        risk_cat = ", ".join(str(c) for c in risk_cat_raw[:2])
    else:
        risk_cat = risk_cat_raw
    lv = LEVEL_LABEL.get(pred_level, "LOW")
    return f"{str(risk_cat)[:120]} → 综合评定: {lv}"


async def get_risk_attribution(
    dataset_id: str = "",
    limit: int = 50,
) -> list[dict]:
    """从 Benchmark 静态 predictions.jsonl 提取归因数据，不可达时返回空列表"""
    # 1. 获取可用结果列表
    results_data = await benchmark_get("/api/demo/results")
    if not results_data:
        logger.warning("Risk attribution: Benchmark /api/demo/results unavailable")
        return []

    from pathlib import Path as _Path

    # /api/demo/results 返回 {"selected": {...}, "results": [...]}
    result_items = []
    if isinstance(results_data, dict):
        result_items = results_data.get("results") or []
    elif isinstance(results_data, list):
        result_items = results_data
    target = None
    for item in result_items:
        rid = str(item.get("dataset_id", ""))
        if dataset_id and rid != dataset_id:
            continue
        pp = (item.get("paths") or {})
        pred_path = pp.get("predictions", "")
        if pred_path:
            target = item
            break

    if not target:
        # 回退：选第一个有 predictions 路径的结果
        for item in result_items:
            pp = (item.get("paths") or {})
            if pp.get("predictions"):
                target = item
                break

    if not target:
        logger.warning("Risk attribution: no results with predictions path found")
        return []

    model_id = str(target.get("model_id") or "")
    if model_id != "qwen3.5-9B-V7" and ("qwen" in model_id.lower() or "Qwen3.5-9B" in str(target)):
        model_id = "qwen3.5-9b"
    query = urlencode(
        {
            "task": target.get("task") or "multilabel_then_severity",
            "dataset_id": target.get("dataset_id") or dataset_id,
            "model_id": model_id,
            "limit": min(limit, 200),
        }
    )
    try:
        predictions_data = await benchmark_get(f"/api/demo/predictions?{query}")
    except Exception as exc:  # defensive fallback for legacy/local adapters
        logger.warning("Risk attribution: predictions API unavailable: %s", exc)
        predictions_data = None
    prediction_rows = []
    if isinstance(predictions_data, dict):
        prediction_rows = predictions_data.get("rows") or []

    pred_path = _Path(str((target.get("paths") or {}).get("predictions", "")))
    if not prediction_rows and not _path_exists_safely(pred_path):
        logger.warning("Risk attribution: predictions unavailable via API or file: %s", pred_path)
        return []

    # 2. 读取 predictions.jsonl
    nodes: list[dict] = []
    try:
        if prediction_rows:
            records = prediction_rows[:limit]
        else:
            records = []
            with pred_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if len(records) >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        for rec in records:
            if len(nodes) >= limit:
                break

            example = rec.get("example") or {}
            pred_cats_raw = rec.get("pred_categories") or []
            gold_cats_raw = rec.get("gold_categories") or []
            pred_level = rec.get("pred_level", 0)
            cat_levels = rec.get("pred_category_levels") or {}

            # signals: { C06: HIGH, C03: MEDIUM, ... }
            signals: dict[str, str] = {}
            for cat_id_str in pred_cats_raw:
                cid = _parse_category_id(str(cat_id_str))
                lv = cat_levels.get(cid, cat_levels.get(cat_id_str))
                if isinstance(lv, (int, float)):
                    signals[cid] = LEVEL_LABEL.get(int(lv), "MEDIUM")
                else:
                    signals[cid] = LEVEL_LABEL.get(pred_level, "MEDIUM")

            if not signals:
                # 没有预测类别时用 gold 类别 + pred_level
                for cat_id_str in gold_cats_raw[:3]:
                    cid = _parse_category_id(str(cat_id_str))
                    signals[cid] = LEVEL_LABEL.get(pred_level, "MEDIUM")

            overall = LEVEL_LABEL.get(pred_level, "LOW")
            weight = LEVEL_WEIGHT.get(overall, 0.35)

            # 提取文本（全文，不截断）
            text = str(example.get("response") or rec.get("text") or example.get("prompt") or "")

            # 风险证据：从 risk_sub_category 提取可读描述
            risk_subcats_raw = example.get("risk_sub_category") or []
            # risk_sub_category 可能是 JSON 字符串，需解析
            if isinstance(risk_subcats_raw, str):
                try:
                    risk_subcats = json.loads(risk_subcats_raw)
                except (json.JSONDecodeError, TypeError):
                    risk_subcats = [risk_subcats_raw]
            else:
                risk_subcats = risk_subcats_raw
            risk_evidence: list[str] = []
            _risk_keywords: set[str] = set()
            if isinstance(risk_subcats, list):
                for sc in risk_subcats:
                    if isinstance(sc, str):
                        # 提取 "C04-S01：暴力、破坏..." → 保留后半描述
                        if "：" in sc:
                            desc = sc.split("：", 1)[1]
                            risk_evidence.append(desc)
                            # 提取关键词用于句子匹配
                            for kw in _re.split(r"[、，,;；]", desc):
                                kw = kw.strip()
                                if len(kw) >= 2:
                                    _risk_keywords.add(kw)
                        else:
                            risk_evidence.append(sc)

            # 句子级风险标记：按句号/问号/感叹号分句，检查是否含风险关键词
            _raw_sentences = _re.split(r"(?<=[。！？!?\n])", text)
            risk_sentence_indices: list[int] = []
            sentences: list[str] = []
            for s in _raw_sentences:
                stripped = s.strip()
                if not stripped:
                    continue
                sentences.append(stripped)
                if _risk_keywords:
                    for kw in _risk_keywords:
                        if kw in stripped:
                            risk_sentence_indices.append(len(sentences) - 1)
                            break

            chain = _build_attribution_chain(
                [_parse_category_id(str(c)) for c in gold_cats_raw],
                [_parse_category_id(str(c)) for c in pred_cats_raw],
                pred_level,
            )
            reason_path = _build_reason_path(example, pred_level)

            nodes.append({
                "id": f"PRED-{rec.get('index', len(nodes)):04d}",
                "signals": signals,
                "overall": overall,
                "chain": chain,
                "reasonPath": reason_path,
                "weight": round(weight, 2),
                "text": text,
                "sentences": sentences,
                "riskSentenceIndices": risk_sentence_indices,
                "riskEvidence": risk_evidence[:5],
                "goldCategories": [_parse_category_id(str(c)) for c in gold_cats_raw],
                "predCategories": [_parse_category_id(str(c)) for c in pred_cats_raw],
            })
    except OSError as exc:
        logger.warning("Risk attribution: failed to read predictions file: %s", exc)
        return []

    return nodes
