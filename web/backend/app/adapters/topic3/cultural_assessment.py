from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _repo_root() -> Path:
    configured = get_settings().cultural_assessment_root.strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[6] / "Project_3_Cultural_Diversity_Assessment_Tool"


def _benchmark_root() -> Path:
    v2_root = _repo_root() / "culture_eval_benchmark_v2"
    if v2_root.is_dir():
        return v2_root
    return _repo_root() / "culture_eval_benchmark"


def _benchmark_roots() -> list[Path]:
    roots = [_repo_root() / "culture_eval_benchmark", _repo_root() / "culture_eval_benchmark_v2"]
    return [root for root in roots if root.is_dir()]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _resolve_benchmark_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (_benchmark_root() / path).resolve()


def _resolve_from_root(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _ensure_repo() -> None:
    if not _benchmark_root().is_dir():
        raise FileNotFoundError(f"culture assessment benchmark not found: {_benchmark_root()}")


def list_assessment_datasets() -> dict[str, Any]:
    _ensure_repo()
    result: list[dict[str, Any]] = []
    wanted = {
        "cultural_evaluation_ui_batch_30",
        "framework_cultural_diversity_evaluation_dataset_v1",
    }
    seen: set[str] = set()
    for root in _benchmark_roots():
        catalog_path = root / "data" / "datasets" / "catalog.json"
        if not catalog_path.exists():
            continue
        datasets = _read_json(catalog_path).get("datasets", [])
        for item in datasets:
            if not isinstance(item, dict):
                continue
            dataset_id = str(item.get("id", ""))
            if dataset_id not in wanted or dataset_id in seen:
                continue
            seen.add(dataset_id)
            dataset_path = _resolve_from_root(root, str(item.get("path", "")))
            preview = _read_jsonl(dataset_path)[:1]
            first = preview[0] if preview else {}
            result.append(
                {
                    **item,
                    "exists": dataset_path.exists(),
                    "preview_sample_id": first.get("sample_id") or first.get("id"),
                    "preview_ethnic_group": first.get("implied_ethnic_group")
                    or first.get("ethnic_group"),
                    "preview_difficulty_level": first.get("difficulty_level"),
                    "source": "culture_assessment_static",
                }
            )
    return {
        "source": "culture_assessment_static",
        "repo_root": str(_repo_root()),
        "datasets": result,
    }


def list_assessment_static_views() -> dict[str, Any]:
    _ensure_repo()
    views: list[dict[str, Any]] = []
    wanted = {"ui_batch_30_direct_vs_agent", "cultural_diversity_evaluation_dataset_v1"}
    for root in _benchmark_roots():
        catalog_path = root / "data" / "static_views" / "catalog.json"
        if not catalog_path.exists():
            continue
        for view in _read_json(catalog_path).get("views", []):
            if isinstance(view, dict) and view.get("id") in wanted:
                views.append({**view, "_benchmark_root": str(root)})
    return {
        "source": "culture_assessment_static",
        "repo_root": str(_repo_root()),
        "views": views,
    }


def get_assessment_static_view(view_id: str) -> dict[str, Any]:
    _ensure_repo()
    views = list_assessment_static_views().get("views", [])
    view = next((item for item in views if isinstance(item, dict) and item.get("id") == view_id), None)
    if not view:
        raise KeyError(f"unknown culture assessment static view: {view_id}")
    root = Path(str(view.get("_benchmark_root") or _benchmark_root()))

    reference_summary = _read_json_if_present(
        _resolve_from_root(root, Path(str(view.get("reference_run_dir", ""))) / "summary.json"),
    )
    reference_rows = _read_jsonl(
        _resolve_from_root(root, Path(str(view.get("reference_run_dir", ""))) / "sample_results.jsonl"),
    )
    direct_summary = _read_json_if_present(
        _resolve_from_root(root, Path(str(view.get("direct_run_dir", ""))) / "summary.json"),
    )
    agent_summary = _read_json_if_present(
        _resolve_from_root(root, Path(str(view.get("agent_run_dir", ""))) / "summary.json"),
    )
    direct_rows = _read_jsonl(
        _resolve_from_root(root, Path(str(view.get("direct_run_dir", ""))) / "sample_results.jsonl"),
    )
    agent_rows = _read_jsonl(
        _resolve_from_root(root, Path(str(view.get("agent_run_dir", ""))) / "sample_results.jsonl"),
    )

    return {
        "source": "culture_assessment_static",
        "view_id": view["id"],
        "title": view["title"],
        "dataset_id": view["dataset_id"],
        "dataset_label": view["dataset_label"],
        "highlights": view.get("highlights", []),
        "advantage_summary": view.get("advantage_summary", ""),
        "reference": {
            "label": "DeepSeek 基准验证",
            "run_dir": view.get("reference_run_dir", ""),
            "summary": reference_summary,
        },
        "direct": {
            "label": "普通 DeepSeek API",
            "run_dir": view.get("direct_run_dir", ""),
            "summary": direct_summary,
        },
        "agent": {
            "label": "3-Agent",
            "run_dir": view.get("agent_run_dir", ""),
            "summary": agent_summary,
        },
        "radar": _build_radar_payload(direct_summary, agent_summary),
        "sample_pairs": _join_sample_results(direct_rows, agent_rows),
        "reference_samples": _build_reference_samples(reference_rows),
    }


def load_assessment_review_evidence(
    view_id: str = "ui_batch_30_direct_vs_agent",
) -> dict[str, Any]:
    """Load the immutable inputs behind a cultural static comparison.

    Unlike :func:`get_assessment_static_view`, this governance-facing adapter
    intentionally keeps every row and file identity.  The caller can therefore
    validate corpus/Direct/3-Agent/Judge population alignment before persisting
    a review snapshot, without reaching into this adapter's private path helpers.
    """
    _ensure_repo()
    views = list_assessment_static_views().get("views", [])
    view = next(
        (item for item in views if isinstance(item, dict) and item.get("id") == view_id),
        None,
    )
    if not view:
        raise KeyError(f"unknown culture assessment static view: {view_id}")
    root = Path(str(view.get("_benchmark_root") or _benchmark_root()))

    catalog = _read_json(root / "data" / "datasets" / "catalog.json")
    dataset = next(
        (
            item
            for item in catalog.get("datasets", [])
            if isinstance(item, dict) and item.get("id") == view.get("dataset_id")
        ),
        None,
    )
    if not dataset:
        raise FileNotFoundError(f"dataset not registered: {view.get('dataset_id')}")

    dataset_path = _resolve_from_root(root, str(dataset.get("path") or ""))
    direct_dir = _resolve_from_root(root, str(view.get("direct_run_dir") or ""))
    agent_dir = _resolve_from_root(root, str(view.get("agent_run_dir") or ""))
    paths = {
        "dataset": dataset_path,
        "direct_config": direct_dir / "config.snapshot.json",
        "direct_summary": direct_dir / "summary.json",
        "direct_results": direct_dir / "sample_results.jsonl",
        "agent_config": agent_dir / "config.snapshot.json",
        "agent_summary": agent_dir / "summary.json",
        "agent_results": agent_dir / "sample_results.jsonl",
    }
    missing = [label for label, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError("culture review evidence missing: " + ", ".join(missing))

    return {
        "source": "culture_assessment_static",
        "view": {key: value for key, value in view.items() if not key.startswith("_")},
        "dataset": {
            **dataset,
            "rows": _read_jsonl(dataset_path),
        },
        "direct": {
            "run_dir": str(view.get("direct_run_dir") or ""),
            "config": _read_json(paths["direct_config"]),
            "summary": _read_json(paths["direct_summary"]),
            "rows": _read_jsonl(paths["direct_results"]),
        },
        "agent": {
            "run_dir": str(view.get("agent_run_dir") or ""),
            "config": _read_json(paths["agent_config"]),
            "summary": _read_json(paths["agent_summary"]),
            "rows": _read_jsonl(paths["agent_results"]),
        },
        "files": [
            {
                "role": label,
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "sha256": _sha256(path),
            }
            for label, path in paths.items()
        ],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    return _read_json(path)


def _join_sample_results(
    direct_rows: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    agent_map = {str(row.get("sample_id")): row for row in agent_rows}
    joined: list[dict[str, Any]] = []
    for direct_row in direct_rows:
        sample_id = str(direct_row.get("sample_id", ""))
        agent_row = agent_map.get(sample_id)
        if not sample_id or not agent_row:
            continue
        joined.append(
            {
                "sample_id": sample_id,
                "difficulty_level": direct_row.get("difficulty_level"),
                "expected_ethnic_group": direct_row.get("expected_ethnic_group"),
                "original_question": direct_row.get("original_question"),
                "neutralized_question": direct_row.get("neutralized_question"),
                "direct": _simplify_row(direct_row),
                "agent": _simplify_row(agent_row),
                "advantage_note": _build_advantage_note(direct_row, agent_row),
            }
        )
    joined.sort(key=_pair_sort_key)
    return joined


def _simplify_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer_a": row.get("answer_a", ""),
        "answer_b": row.get("answer_b", ""),
        "ethnic_group_judge": row.get("ethnic_group_judge", {}),
        "cultural_difference_judge": row.get("cultural_difference_judge", {}),
        "composite_score": row.get("composite_score", 0),
    }


def _build_reference_samples(rows: list[dict[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    good = [row for row in rows if int(row.get("composite_score", 0)) == 1]
    weak = [row for row in rows if int(row.get("composite_score", 0)) != 1]
    selected: list[dict[str, Any]] = []
    good_index = 0
    weak_index = 0
    while len(selected) < limit and (good_index < len(good) or weak_index < len(weak)):
        for _ in range(3):
            if len(selected) >= limit or good_index >= len(good):
                break
            selected.append(good[good_index])
            good_index += 1
        if len(selected) < limit and weak_index < len(weak):
            selected.append(weak[weak_index])
            weak_index += 1
    return [_simplify_reference_row(row) for row in selected]


def _simplify_reference_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": row.get("sample_id", ""),
        "difficulty_level": row.get("difficulty_level"),
        "expected_ethnic_group": row.get("expected_ethnic_group"),
        "original_question": row.get("original_question"),
        "neutralized_question": row.get("neutralized_question"),
        "answer_a": row.get("answer_a", ""),
        "answer_b": row.get("answer_b", ""),
        "ethnic_group_judge": row.get("ethnic_group_judge", {}),
        "cultural_difference_judge": row.get("cultural_difference_judge", {}),
        "composite_score": row.get("composite_score", 0),
    }


def _build_advantage_note(direct_row: dict[str, Any], agent_row: dict[str, Any]) -> str:
    direct_ethnic = int(direct_row.get("ethnic_group_judge", {}).get("score", 0))
    agent_ethnic = int(agent_row.get("ethnic_group_judge", {}).get("score", 0))
    direct_cultural = int(direct_row.get("cultural_difference_judge", {}).get("score", 0))
    agent_cultural = int(agent_row.get("cultural_difference_judge", {}).get("score", 0))
    direct_composite = int(direct_row.get("composite_score", 0))
    agent_composite = int(agent_row.get("composite_score", 0))
    if direct_ethnic == 0 and agent_ethnic == 1 and direct_cultural == 0 and agent_cultural == 1:
        return "3-Agent 同时补上了民族识别和文化深度响应两项缺口。"
    if direct_ethnic == 0 and agent_ethnic == 1:
        return "3-Agent 明确识别了正确民族，而普通 DeepSeek 在这一点上失分。"
    if direct_cultural == 0 and agent_cultural == 1:
        return "3-Agent 给出了更强的文化逻辑、冲突性质和价值底线判断。"
    if agent_composite > direct_composite:
        return "3-Agent 在综合指标上优于普通 DeepSeek。"
    if agent_composite == direct_composite == 1:
        return "两种方案在这条样本上都通过了综合指标。"
    return "这条样本上两种方案都还没有完全满足评测要求。"


def _pair_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    direct_score = int(row["direct"].get("composite_score", 0))
    agent_score = int(row["agent"].get("composite_score", 0))
    improvement = agent_score - direct_score
    return (-improvement, direct_score, str(row["sample_id"]))


def _build_radar_payload(
    direct_summary: dict[str, Any],
    agent_summary: dict[str, Any],
) -> dict[str, Any]:
    labels = ["民族识别", "文化差异度", "综合通过率", "L1", "L2", "L3"]

    def values(summary: dict[str, Any]) -> list[float]:
        by_difficulty = summary.get("by_difficulty", {})
        return [
            float(summary.get("ethnic_group_metric_rate", 0)),
            float(summary.get("cultural_difference_rate", 0)),
            float(summary.get("composite_pass_rate", 0)),
            float(by_difficulty.get("L1", {}).get("pass_rate", 0)),
            float(by_difficulty.get("L2", {}).get("pass_rate", 0)),
            float(by_difficulty.get("L3", {}).get("pass_rate", 0)),
        ]

    return {
        "labels": labels,
        "series": [
            {"name": "普通 DeepSeek API", "values": values(direct_summary), "color": "#b45309"},
            {"name": "3-Agent", "values": values(agent_summary), "color": "#0f766e"},
        ],
    }
