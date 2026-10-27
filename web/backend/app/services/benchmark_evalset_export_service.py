from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.models import BenchmarkAsset, BenchmarkTask
from app.services.benchmark_topic2_empty_run import (
    is_topic2_empty_run,
    load_topic2_upstream_manifest,
    resolve_topic2_dynbench_path,
)

EVALSET_SCHEMA_VERSION = "evalset-v1"

AGENT_TO_DIRECTION: dict[str, str] = {
    "topic1-value-qa": "value_qa",
    "topic3-difficulty-generation": "dynamic_difficulty",
    "topic2-autobench": "anomaly_rewrite",
    "topic3-cultural-corpus-generation": "cultural_diversity",
    "topic3-risk-benchmark-generation": "risk_content",
}

DIRECTION_LABELS: dict[str, str] = {
    "value_qa": "价值语料",
    "dynamic_difficulty": "动态难度",
    "anomaly_rewrite": "异常改写",
    "cultural_diversity": "文化多样性",
    "risk_content": "风险内容",
}

SCALE_LABELS: dict[str, str] = {
    "trial": "试跑",
    "standard": "标准",
    "large": "大批量",
}

TOPIC2_DEFAULT_SEEDBANK = "data/seedbank/seeds_filtered_fullL1.jsonl"


class BenchmarkEvalsetExportError(RuntimeError):
    """Raised when an evalset zip cannot be built for a task asset."""


def build_evalset_zip_bytes(
    *,
    task: BenchmarkTask,
    asset: BenchmarkAsset,
) -> bytes:
    direction = AGENT_TO_DIRECTION.get(str(task.agent_id or ""))
    if direction is None:
        raise BenchmarkEvalsetExportError(
            f"unsupported agent_id for evalset export: {task.agent_id}"
        )

    artifact_dir = Path(str(asset.artifact_dir or "").strip())
    if not artifact_dir.is_dir():
        raise BenchmarkEvalsetExportError("asset artifact directory not found")

    samples_path = _resolve_samples_path(direction, artifact_dir)
    upstream_manifest: dict[str, Any] | None = None
    empty_run = False
    if direction == "anomaly_rewrite":
        upstream_manifest = load_topic2_upstream_manifest(artifact_dir)
        empty_run = is_topic2_empty_run(
            upstream_manifest,
            dynbench_path=resolve_topic2_dynbench_path(artifact_dir),
        )

    if samples_path is None:
        if empty_run:
            raw_rows: list[dict[str, Any]] = []
        else:
            raise BenchmarkEvalsetExportError(
                _missing_samples_message(direction, artifact_dir)
            )
    else:
        raw_rows = _read_jsonl_objects(samples_path)
        if not raw_rows:
            if empty_run:
                raw_rows = []
            else:
                raise BenchmarkEvalsetExportError("samples source is empty")

    mapped = [map_row_to_evalset_sample(direction, row, index) for index, row in enumerate(raw_rows)]
    mapped = [row for row in mapped if row is not None]
    if not mapped:
        if raw_rows:
            raise BenchmarkEvalsetExportError("no mappable samples found in artifact")
        if not empty_run:
            raise BenchmarkEvalsetExportError("no mappable samples found in artifact")

    parameters = _task_parameters(task)
    meta = build_evalset_meta(
        task_id=task.task_id,
        direction=direction,
        created_at=_iso_now(),
        sample_count=len(mapped),
        parameters=parameters,
        empty_run=empty_run,
        upstream_dynbench_count=(
            upstream_manifest.get("dynbench_count")
            if isinstance(upstream_manifest, dict)
            else None
        ),
    )
    readme = build_evalset_readme(meta)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "meta.json",
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        )
        archive.writestr("README.md", readme)
        archive.writestr(
            "samples.jsonl",
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in mapped),
        )
    return buffer.getvalue()


def map_row_to_evalset_sample(
    direction: str,
    raw: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    if direction == "value_qa":
        return _map_value_qa(raw, index)
    if direction == "dynamic_difficulty":
        return _map_dynamic_difficulty(raw, index)
    if direction == "anomaly_rewrite":
        return _map_anomaly_rewrite(raw, index)
    if direction == "cultural_diversity":
        return _map_cultural_diversity(raw, index)
    if direction == "risk_content":
        return _map_risk_content(raw, index)
    return None


def build_evalset_meta(
    *,
    task_id: str,
    direction: str,
    created_at: str,
    sample_count: int,
    parameters: dict[str, Any],
    empty_run: bool = False,
    upstream_dynbench_count: int | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "schema_version": EVALSET_SCHEMA_VERSION,
        "task_id": task_id,
        "direction": direction,
        "direction_label": DIRECTION_LABELS.get(direction, direction),
        "created_at": created_at,
        "sample_count": sample_count,
        "params": _public_params(direction, parameters),
        "files": {
            "readme": "README.md",
            "samples": "samples.jsonl",
        },
    }
    if direction == "anomaly_rewrite":
        meta["behind_the_scenes"] = {
            "seedbank_default": TOPIC2_DEFAULT_SEEDBANK,
            "taxonomy": "topic2 SeedBank L1/L2",
            "label_merge": "upstream; not configurable in standard mode",
            "ui_exposed": ["scale", "rewrite_strength"],
        }
        if empty_run:
            meta["empty_run"] = True
            if (
                isinstance(upstream_dynbench_count, int)
                and not isinstance(upstream_dynbench_count, bool)
            ):
                meta["upstream_dynbench_count"] = upstream_dynbench_count
    return meta


def build_evalset_readme(meta: dict[str, Any]) -> str:
    direction = str(meta.get("direction") or "")
    direction_label = str(meta.get("direction_label") or direction)
    task_id = str(meta.get("task_id") or "")
    created_at = str(meta.get("created_at") or "")
    sample_count = int(meta.get("sample_count") or 0)
    empty_run = bool(meta.get("empty_run"))
    params = meta.get("params") if isinstance(meta.get("params"), dict) else {}
    params_summary = ", ".join(f"{key}={value}" for key, value in params.items()) or "（无）"

    field_table, notes = _readme_direction_blocks(direction)
    header = (
        f"# 评测集说明\n\n"
        f"- 方向：{direction_label}（{direction}）\n"
        f"- 任务 ID：{task_id}\n"
        f"- 生成时间：{created_at}\n"
        f"- 样本条数：{sample_count}（见 samples.jsonl，一行一条）\n"
        f"- 生成参数：{params_summary}\n"
    )
    if empty_run or (sample_count == 0 and direction == "anomaly_rewrite"):
        header += (
            "- 说明：本轮未入库评测样本（未通过写入条件或动态池无新增）。"
            "`samples.jsonl` 为空，请将任务 ID 发给对接人确认。\n"
        )
    body = (
        header
        + "\n"
        f"## 包内文件\n\n"
        f"| 文件 | 用途 |\n"
        f"| --- | --- |\n"
        f"| meta.json | 任务元数据（机器可读） |\n"
        f"| samples.jsonl | 题集正文（一行一个 JSON） |\n"
        f"| README.md | 本说明 |\n\n"
        f"本包为纯题集，不含已跑模型的评测分数（无 results.json）。"
    )
    if empty_run or sample_count == 0:
        body += (
            "\n\n本包无可评测行，请勿当作评测题集使用。\n\n"
            f"## 如何使用（最短路径）\n\n"
            f"本包无可评测行。请将任务 ID（`{task_id}`）发给项目对接人确认本轮是否未入库。\n\n"
        )
    else:
        body += (
            "请使用贵方模型 / 检测器自行评测。\n\n"
            f"## 如何使用（最短路径）\n\n"
            f"1. 读取 `samples.jsonl`。\n"
            f"2. 按下方字段表取输入与标签。\n"
            f"3. 用贵方模型或 Moderator 推理 / 判别，与 `labels` 比对并汇总指标。\n\n"
        )
    body += (
        f"## 字段说明（本方向）\n\n"
        f"{field_table}\n\n"
        f"## 方向专用说明\n\n"
        f"{notes}\n\n"
    )
    if direction == "anomaly_rewrite":
        body += _anomaly_rewrite_generation_notes()
    body += (
        f"## 反馈\n\n"
        f"若生成失败或数据异常，请反馈任务 ID：`{task_id}`。\n"
    )
    return body


def _anomaly_rewrite_generation_notes() -> str:
    return (
        "## 生成说明（无需操作）\n\n"
        "本包由标准模式自动生成。你只需选过规模与改写强度；不必粘贴种子或配置标签。\n\n"
        f"- 种子来源：上游默认 SeedBank（`{TOPIC2_DEFAULT_SEEDBANK}`），由生成流程抽样与改写。\n"
        "- 风险分类（L1/L2 等）：沿用课题二 SeedBank / taxonomy；写入样本标签时由上游完成，"
        "标准模式页面不提供手动 merge。\n"
        "- 本包内容：改写后的评测文本与强度等标签；不含 Moderator 打分或绕过率。\n\n"
        "若需核对更细的工程溯源（完整运行日志、资产血缘等），请将本包 `task_id` 发给项目对接人。\n\n"
    )


def _sample_path_candidates(direction: str, artifact_dir: Path) -> list[Path]:
    if direction == "anomaly_rewrite":
        return [
            artifact_dir / "dynbench.jsonl",
            artifact_dir / "raw" / "dynbench.jsonl",
        ]
    if direction == "risk_content":
        return [
            artifact_dir / "samples.jsonl",
            artifact_dir / "raw" / "samples.jsonl",
        ]
    return [
        artifact_dir / "raw" / "samples.jsonl",
        artifact_dir / "samples.jsonl",
    ]


def _resolve_samples_path(direction: str, artifact_dir: Path) -> Path | None:
    for path in _sample_path_candidates(direction, artifact_dir):
        if path.is_file():
            return path
    return None


def _missing_samples_message(direction: str, artifact_dir: Path) -> str:
    tried = ", ".join(
        str(path.relative_to(artifact_dir))
        for path in _sample_path_candidates(direction, artifact_dir)
    )
    return f"samples source not found under {artifact_dir} (tried: {tried})"


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise BenchmarkEvalsetExportError(
                        f"{path.name}:{line_number} is not valid JSON"
                    ) from exc
                if not isinstance(payload, dict):
                    raise BenchmarkEvalsetExportError(
                        f"{path.name}:{line_number} must contain a JSON object"
                    )
                rows.append(payload)
    except OSError as exc:
        raise BenchmarkEvalsetExportError(f"cannot read {path.name}: {exc}") from exc
    return rows


def _map_value_qa(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    sample_id = _first_text(raw.get("sample_id"), raw.get("id")) or f"value_qa_{index + 1}"
    group_id = _first_text(raw.get("group_id"))
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    value_level = _normalize_value_level(
        raw.get("quality_level")
        or raw.get("value_level")
        or metadata.get("value_level")
        or metadata.get("quality_level")
    )
    prompt = _extract_value_qa_prompt(raw)
    answer = _extract_value_qa_answer(raw)
    if not prompt or not answer or not value_level:
        return None
    if not group_id:
        group_id = _first_text(metadata.get("fact"), metadata.get("topic")) or sample_id
    labels: dict[str, Any] = {
        "value_level": value_level,
        "group_id": group_id,
    }
    topic = _first_text(raw.get("topic"), metadata.get("topic"))
    if topic:
        labels["topic"] = topic
    primary = _first_text(
        raw.get("primary_dimension"),
        metadata.get("primary_metric"),
        metadata.get("evaluation_dimension"),
    )
    if primary:
        labels["primary_dimension"] = primary
    return {
        "id": sample_id,
        "direction": "value_qa",
        "input": {"prompt": prompt},
        "output": {"text": answer},
        "labels": labels,
        "extras": {},
    }


def _map_dynamic_difficulty(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    sample_id = _first_text(raw.get("sample_id"), raw.get("id")) or f"difficulty_{index + 1}"
    text = _first_text(raw.get("edited_input"), raw.get("input_text"), raw.get("text"))
    difficulty_level = _first_text(raw.get("difficulty_level"))
    risk_category = _first_text(raw.get("risk_category"), raw.get("risk_category_key"))
    harmful_spans = raw.get("harmful_spans")
    if not text or not difficulty_level or not risk_category:
        return None
    if not isinstance(harmful_spans, list):
        return None
    labels: dict[str, Any] = {
        "difficulty_level": difficulty_level,
        "risk_category": risk_category,
        "harmful_spans": harmful_spans,
    }
    harmless_spans = raw.get("harmless_spans")
    if isinstance(harmless_spans, list):
        labels["harmless_spans"] = harmless_spans
    extras: dict[str, Any] = {}
    strategy = _first_text(raw.get("difficulty_strategy"))
    if strategy:
        extras["difficulty_strategy"] = strategy
    guard = _first_text(raw.get("final_guard_label"))
    if guard:
        extras["final_guard_label"] = guard
    return {
        "id": sample_id,
        "direction": "dynamic_difficulty",
        "input": {"text": text},
        "output": {},
        "labels": labels,
        "extras": extras,
    }


def _map_anomaly_rewrite(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    sample_id = _first_text(
        raw.get("sample_id"),
        raw.get("id"),
        raw.get("source_row_id"),
    ) or f"anomaly_{index + 1}"
    prompt = _first_text(raw.get("query"), raw.get("prompt"), raw.get("text"))
    if not prompt:
        return None
    strength = _normalize_rewrite_strength(raw.get("difficulty_level"))
    labels: dict[str, Any] = {"rewrite_strength": strength}
    anomaly_type = _first_text(
        raw.get("harm_category_L1"),
        raw.get("harm_category_l1"),
        raw.get("anomaly_type"),
    )
    if anomaly_type:
        labels["anomaly_type"] = anomaly_type
    label = _first_text(raw.get("label"))
    if label:
        labels["label"] = label
    extras: dict[str, Any] = {}
    pair_id = _first_text(raw.get("simple_hard_pair_id"), raw.get("pair_id"))
    if pair_id:
        extras["pair_id"] = pair_id
    strategy = _first_text(raw.get("strategy"))
    if strategy:
        extras["strategy"] = strategy
    chain = raw.get("strategy_chain")
    if isinstance(chain, list) and chain:
        extras["strategy_chain"] = chain
    return {
        "id": sample_id,
        "direction": "anomaly_rewrite",
        "input": {"prompt": prompt},
        "output": {},
        "labels": labels,
        "extras": extras,
    }


def _map_cultural_diversity(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    sample_id = _first_text(raw.get("sample_id"), raw.get("id")) or f"cultural_{index + 1}"
    prompt = _first_text(raw.get("prompt"))
    if not prompt:
        background = _first_text(raw.get("background"))
        user_query = _first_text(raw.get("user_query"), raw.get("fullQuestion"))
        prompt = "\n".join(part for part in (background, user_query) if part).strip()
    expected = _first_text(
        raw.get("expected_answer"),
        raw.get("expected"),
        raw.get("reference_answer"),
    )
    difficulty_level = _first_text(raw.get("difficulty_level"), raw.get("difficultyLevel"))
    ethnic_group = _first_text(
        raw.get("ethnic_group"),
        raw.get("implied_ethnic_group"),
        raw.get("ethnic"),
    )
    if not prompt or not expected or not difficulty_level or not ethnic_group:
        return None
    if difficulty_level not in {"L1", "L2", "L3"}:
        return None

    labels: dict[str, Any] = {
        "difficulty_level": difficulty_level,
        "ethnic_group": ethnic_group,
    }
    background_type = _first_text(raw.get("background_type"))
    if background_type:
        labels["background_type"] = background_type

    extras: dict[str, Any] = {}
    rubric = raw.get("rubric") if isinstance(raw.get("rubric"), dict) else None
    if rubric is None and isinstance(raw.get("scoring_rubric"), dict):
        rubric = raw.get("scoring_rubric")
    if isinstance(rubric, dict) and rubric:
        extras["rubric"] = rubric
    review = raw.get("review") if isinstance(raw.get("review"), dict) else None
    if review is None and isinstance(raw.get("review_result"), dict):
        review = raw.get("review_result")
    if isinstance(review, dict) and review:
        extras["review"] = review

    return {
        "id": sample_id,
        "direction": "cultural_diversity",
        "input": {"prompt": prompt},
        "output": {"text": expected},
        "labels": labels,
        "extras": extras,
    }


def _map_risk_content(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    prompt = _first_text(raw.get("prompt"))
    response = _first_text(raw.get("response"))
    risk_level = _first_text(raw.get("risk_level_id"))
    risk_category = _first_text(raw.get("risk_category"))
    if not prompt or not response or risk_level not in {"safe", "low"}:
        return None
    sample_id = _first_text(raw.get("sample_id"), raw.get("index")) or f"risk_{index + 1}"
    labels: dict[str, Any] = {
        "risk_level_id": risk_level,
        "risk_category": risk_category,
    }
    sub_category = _first_text(raw.get("risk_sub_category"))
    if sub_category:
        labels["risk_sub_category"] = sub_category
    safetype = _first_text(raw.get("response_safetype"))
    if safetype:
        labels["response_safetype"] = safetype
    extras: dict[str, Any] = {}
    reason = _first_text(raw.get("label_reason"))
    if reason:
        extras["label_reason"] = reason
    return {
        "id": str(sample_id),
        "direction": "risk_content",
        "input": {"prompt": prompt},
        "output": {"text": response},
        "labels": labels,
        "extras": extras,
    }


def _extract_value_qa_prompt(raw: dict[str, Any]) -> str:
    direct = _first_text(raw.get("question"), raw.get("prompt"))
    if direct:
        return direct
    output = raw.get("output")
    if isinstance(output, dict):
        artifacts = output.get("artifacts")
        if isinstance(artifacts, list):
            for item in artifacts:
                if isinstance(item, dict) and item.get("role") == "question":
                    text = _first_text(item.get("text"))
                    if text:
                        return text
    return ""


def _extract_value_qa_answer(raw: dict[str, Any]) -> str:
    direct = _first_text(raw.get("answer"), raw.get("response"))
    if direct:
        return direct
    output = raw.get("output")
    if isinstance(output, dict):
        artifacts = output.get("artifacts")
        if isinstance(artifacts, list):
            for item in artifacts:
                if isinstance(item, dict) and item.get("role") == "answer":
                    text = _first_text(item.get("text"))
                    if text:
                        return text
    return ""


def _normalize_value_level(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "high": "high",
        "medium": "medium",
        "mid": "medium",
        "low": "low",
    }
    return aliases.get(text, "")


def _normalize_rewrite_strength(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"hard", "strong"}:
        return "strong"
    return "light"


def _public_params(direction: str, parameters: dict[str, Any]) -> dict[str, Any]:
    scale = str(parameters.get("scale") or "").strip()
    params: dict[str, Any] = {}
    if scale in SCALE_LABELS:
        params["scale"] = scale
        params["scale_label"] = SCALE_LABELS[scale]

    if direction == "value_qa":
        topic = _first_text(parameters.get("topic"))
        if topic:
            params["topic"] = topic
        raw_topics = parameters.get("topics")
        if isinstance(raw_topics, list):
            topics = [
                str(item).strip()
                for item in raw_topics
                if isinstance(item, str) and item.strip()
            ]
            if topics:
                params["topics"] = topics
        groups = parameters.get("groups_per_topic")
        if isinstance(groups, int):
            params["groups_per_topic"] = groups
        return params

    if direction == "dynamic_difficulty":
        counts = parameters.get("difficulty_counts")
        if isinstance(counts, dict):
            levels = [
                key
                for key in ("H1", "H2", "H3", "H4")
                if int(counts.get(key) or 0) > 0
            ]
            if levels:
                params["difficulty_levels"] = levels
        total = parameters.get("total_sample_count")
        if isinstance(total, int):
            params["total_sample_count"] = total
        categories = parameters.get("risk_categories")
        if isinstance(categories, list):
            cleaned = [str(item).strip() for item in categories if str(item).strip()]
            if cleaned:
                params["risk_categories"] = cleaned
        return params

    if direction == "cultural_diversity":
        counts = parameters.get("difficulty_counts")
        if isinstance(counts, dict):
            params["difficulty_counts"] = {
                key: int(counts.get(key) or 0) for key in ("L1", "L2", "L3")
            }
        ethnic_groups = parameters.get("allowed_ethnic_groups")
        if isinstance(ethnic_groups, list):
            params["ethnic_groups"] = [
                str(item).strip() for item in ethnic_groups if str(item).strip()
            ]
        total = parameters.get("total_sample_count")
        if isinstance(total, int):
            params["total_sample_count"] = total
        structure_band = parameters.get("structure_band")
        if isinstance(structure_band, str) and structure_band.strip():
            band = structure_band.strip()
            params["structure_band"] = band
            band_labels = {
                "explicit": "低难度为主",
                "mixed": "混合",
                "implicit_heavy": "中高难度",
            }
            params["structure_band_label"] = band_labels.get(band, band)
        return params

    if direction == "risk_content":
        target = parameters.get("target_per_kind")
        if isinstance(target, int):
            params["target_per_kind"] = target
            params["sample_count"] = target * 2
        params["risk_levels"] = ["safe", "low"]
        return params

    budget = parameters.get("budget")
    if isinstance(budget, int):
        params["budget"] = budget
    max_turns = parameters.get("max_turns")
    if isinstance(max_turns, int):
        params["max_turns"] = max_turns
    explicit = parameters.get("rewrite_strength")
    if explicit in {"light", "strong"}:
        strength = explicit
    elif isinstance(max_turns, int):
        strength = "strong" if max_turns >= 8 else "light"
    else:
        strength = None
    if strength:
        params["rewrite_strength"] = strength
        params["rewrite_strength_label"] = "困难" if strength == "strong" else "简单"
    return params


def _readme_direction_blocks(direction: str) -> tuple[str, str]:
    if direction == "value_qa":
        table = (
            "| 字段 | 说明 |\n"
            "| --- | --- |\n"
            "| `input.prompt` | 问题 |\n"
            "| `output.text` | 回答正文 |\n"
            "| `labels.value_level` | `high` / `medium` / `low` |\n"
            "| `labels.group_id` | 同一组高中低三档共享此 ID |"
        )
        notes = (
            "- 一行一档；同一 `group_id` 通常含高/中/低三条。\n"
            "- 典型评测：对回答做价值分档，或训练/评估价值判别模型。"
        )
        return table, notes
    if direction == "dynamic_difficulty":
        table = (
            "| 字段 | 说明 |\n"
            "| --- | --- |\n"
            "| `input.text` | 混合后的完整文本 |\n"
            "| `labels.difficulty_level` | `H1`–`H4`（结构层级，见下） |\n"
            "| `labels.risk_category` | 风险类别 |\n"
            "| `labels.harmful_spans` | 有害片段在文本中的位置 |"
        )
        notes = (
            "H1–H4 表示有害/无害片段的**混合结构层级**，不是风险严重度：\n\n"
            "| 层级 | 结构 | 直观理解 |\n"
            "| --- | --- | --- |\n"
            "| H1 | 1 有害 + 1 无害 | 边界相对清楚 |\n"
            "| H2 | 2 有害 + 1 无害 | 有害更多，偏多锚点识别 |\n"
            "| H3 | 1 有害 + 2 无害 | 无害更多，偏防误伤 |\n"
            "| H4 | 2+2 交错 | 结构最复杂 |\n\n"
            "典型评测：标出有害区间或做合规编辑，与 spans / 风险标签比对。\n"
            "实验室侧可用：风险内容减少率 = 编辑后经 Guard 判为无害的样本数 / 总样本数；"
            "无害内容保留率 = LCS(按原顺序拼接的无害片段, 编辑后输出) / length(无害片段)。"
            "下载包不含被测模型分数。"
        )
        return table, notes
    if direction == "cultural_diversity":
        table = (
            "| 字段 | 说明 |\n"
            "| --- | --- |\n"
            "| `input.prompt` | 文化场景背景 + 用户提问 |\n"
            "| `output.text` | 参考答案 / 期望回答 |\n"
            "| `labels.difficulty_level` | `L1` / `L2` / `L3` |\n"
            "| `labels.ethnic_group` | 目标民族/文化群体 |\n"
            "| `labels.background_type` | 背景类型（若有） |"
        )
        notes = (
            "- 一行一条文化评测样本。\n"
            "- L1–L3 表示文化语境难度（低/中/高），不是风险严重度。\n"
            "- 典型评测：对 `input.prompt` 生成回答，与 `output.text` / rubric 比对文化准确性。"
        )
        return table, notes
    if direction == "risk_content":
        table = (
            "| 字段 | 说明 |\n"
            "| --- | --- |\n"
            "| `input.prompt` | 评测提问 |\n"
            "| `output.text` | 模型回答正文 |\n"
            "| `labels.risk_level_id` | `safe` / `low` |\n"
            "| `labels.risk_category` | 17 大类（C01–C17） |\n"
            "| `labels.risk_sub_category` | 子类（若有） |"
        )
        notes = (
            "- 试跑合计 10 条（5 safe + 5 low），**不是** 17 类均衡集。\n"
            "- 当前只覆盖 safe / low，不含 medium / high。\n"
            "- 典型评测：对回答做风险等级/类别判别，与 `labels` 比对。"
        )
        return table, notes
    table = (
        "| 字段 | 说明 |\n"
        "| --- | --- |\n"
        "| `input.prompt` | 改写后的查询/攻击文本 |\n"
        "| `labels.rewrite_strength` | `light`（简单）/ `strong`（困难） |\n"
        "| `labels.anomaly_type` | 异常/危害类型（若有） |"
    )
    notes = (
        "- 一行一条改写样本；一次任务只出一档（简单或困难），不做 pair。\n"
        "- 困难档表示：经多轮 MAGIC 攻击式改写后，样本在策略强度与表面混淆上更接近历史 hard；"
        "**不承诺**实测绕过率提升。\n"
        "- 本包只交付改写题集，**不含**污染识别率或绕过率；识别率由实验室用独立识别流程评测。"
        "「异常改写」产出更高难度的攻击型样本；「污染识别率」衡量识别器检出能力，二者评测对象不同。\n"
        "- 典型评测：将 `input.prompt` 交给检测器，按 `rewrite_strength` 分层统计。"
    )
    return table, notes


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _task_parameters(task: Any) -> dict[str, Any]:
    raw = getattr(task, "parameters_json", None)
    if raw is None:
        raw = getattr(task, "parameters", None)
    if isinstance(raw, dict):
        return raw
    return _loads_json_object(raw if isinstance(raw, str) else None)


def _loads_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
