from pathlib import Path
import json
import re
from typing import Any

from app.services.document_parser import (
    clean_text,
    content_hash,
    extract_text_from_bytes,
    is_supported_upload,
)
from app.adapters.topic4.input_workflow_client import (
    Topic4InputWorkflowUnavailable,
    build_topic4_input_workflow_client,
)

TOPIC4_STATIC_ASSET_ID = "topic4_medical_demo_static"
from app.schemas.data_input import (
    IntegrationEndpoint,
    Topic4LineageEdge,
    Topic4HealthResponse,
    Topic4LineageNode,
    Topic4LineageParseFailure,
    Topic4LineageParseResponse,
    Topic4LineageResponse,
    Topic4LineageSummary,
    Topic4WorkflowStage,
)

TOPIC4_ENDPOINTS = [
    IntegrationEndpoint(
        method="GET",
        path="/api/health",
        purpose="检查课题四输入侧血缘图谱服务是否可达",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/api/build_graph",
        purpose="根据 records 构建 Meta/Chunk/CleanedChunk/Question/Answer 血缘图谱",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/api/graph/merge",
        purpose="将风险标注合并到血缘图谱节点，形成风险节点与传播信息",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/api/annotate/batch",
        purpose="批量风险标注；后续用于替换当前中性标注输入",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/api/cleaning/apply",
        purpose="对合并后的图谱执行配置驱动清洗；后续接入修正节点",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/api/cleaning/report",
        purpose="生成清洗前后分析报告；后续接入归因/报告展示",
    ),
    IntegrationEndpoint(
        method="POST",
        path="/api/workflow/full_v2",
        purpose="课题四完整同步工作流；后续评估是否作为一键联调入口",
    ),
]

MAX_TOPIC4_CHARS_PER_CHUNK = 2000
MAX_TOPIC4_CHUNKS_PER_FILE = 40
MAX_TOPIC4_QA_PAIRS_PER_CHUNK = 6
MAX_TOPIC4_DISPLAY_NODES = 400
MIN_TOPIC4_TEXT_LENGTH = 10
MIN_TOPIC4_FACT_SENTENCE_CHARS = 8
MAX_TOPIC4_SUMMARY_CHARS = 180
MAX_TOPIC4_FACT_CHARS = 160


def _unavailable_message(base_url: str) -> str:
    return (
        "暂时无法连接血缘图谱生成服务。"
        "当前不会展示本地预设或模拟图谱，请确认课题四服务已启动后重试。"
    )


def _topic4_unavailable_payload(base_url: str) -> dict[str, Any]:
    return {
        "connected": False,
        "base_url": base_url,
        "message": _unavailable_message(base_url),
        "fallback": False,
        "blocking_reason": "血缘图谱生成服务当前不可达。",
        "next_action": "请确认课题四服务已启动，并稍后重新生成图谱。",
        "endpoints": TOPIC4_ENDPOINTS,
    }


async def check_topic4_input_workflow_health() -> Topic4HealthResponse:
    client = build_topic4_input_workflow_client()
    try:
        await client.health()
    except Topic4InputWorkflowUnavailable:
        return Topic4HealthResponse(**_topic4_unavailable_payload(client.base_url))

    return Topic4HealthResponse(
        connected=True,
        base_url=client.base_url,
        message="已连接课题四输入侧血缘图谱服务。",
        next_action="进入血缘图谱节点后会自动生成图谱。",
        endpoints=TOPIC4_ENDPOINTS,
    )


async def build_topic4_lineage(
    records: list[dict[str, Any]] | None = None,
    risk_annotations: list[dict[str, Any]] | None = None,
) -> Topic4LineageResponse:
    client = build_topic4_input_workflow_client()
    next_records = records or []
    if not next_records:
        raise ValueError("topic4 lineage requires parsed dataset records")
    explicit_risk_annotations = risk_annotations or None
    try:
        if explicit_risk_annotations is None:
            try:
                workflow_result = await client.run_full_workflow(
                    records=next_records,
                    source=_workflow_source(next_records),
                    enable_cleaning=True,
                    cleaning_mode="remove_risk_nodes",
                    enable_neo4j=False,
                )
                merged_graph = _extract_graph(workflow_result, "merged_graph")
                annotations = _list_or_empty(workflow_result.get("annotations"))
                cleaning_result = _dict_or_empty(workflow_result.get("cleaning_result"))
                cleaning_actions = _list_or_empty(cleaning_result.get("actions"))
                report_summary = _report_summary(workflow_result)
                workflow_mode = "topic4_full_v2"
                workflow_stages = _full_workflow_stages(
                    annotation_count=len(annotations),
                    cleaning_action_count=len(cleaning_actions),
                    report_summary=report_summary,
                )
                message = "已生成血缘图谱，并同步完成风险标注与报告分析。"
                next_action = "可以查看图谱节点详情，或重新生成当前训练语料的血缘图谱。"
            except Topic4InputWorkflowUnavailable as exc:
                fallback = await _try_build_graph_fallback(client, next_records, exc)
                if fallback is None:
                    return _topic4_full_workflow_failed_response(client.base_url, str(exc))
                (
                    merged_graph,
                    annotations,
                    cleaning_actions,
                    report_summary,
                    workflow_mode,
                    workflow_stages,
                    message,
                    next_action,
                ) = fallback
        else:
            lineage_graph = await client.build_graph(next_records)
            merged_graph = await client.merge_risk(
                lineage_graph=lineage_graph,
                risk_annotations=explicit_risk_annotations,
            )
            annotations = explicit_risk_annotations
            cleaning_actions = []
            report_summary = ""
            workflow_mode = "topic4_build_merge"
            workflow_stages = _build_merge_stages(len(annotations))
            message = "已生成血缘图谱，并完成风险信息合并。"
            next_action = "可以查看图谱节点详情，或重新生成当前训练语料的血缘图谱。"
    except Topic4InputWorkflowUnavailable:
        return Topic4LineageResponse(**_topic4_unavailable_payload(client.base_url))

    # 结构以课题五 records 为准重建，避免课题四服务端状态污染导致边数漂移；
    # 课题四结果只用于回填风险属性与正文。
    display_graph = _build_lineage_skeleton_from_records(next_records)
    _overlay_topic4_properties(display_graph, merged_graph)
    _repair_question_mark_content(display_graph, next_records)
    nodes = _normalize_nodes(display_graph, records=next_records)
    edges = _normalize_edges(display_graph, {node.id for node in nodes})
    summary = _normalize_summary(display_graph)
    # 摘要与前端实际展示的节点/边对齐（含截断与无效边过滤后的结果）。
    summary.totalNodes = len(nodes)
    summary.totalEdges = len(edges)
    summary.metaCount = sum(1 for node in nodes if node.type == "Meta")
    summary.chunkCount = sum(1 for node in nodes if node.type == "Chunk")
    summary.cleanedChunkCount = sum(1 for node in nodes if node.type == "CleanedChunk")
    summary.questionCount = sum(1 for node in nodes if node.type == "Question")
    summary.answerCount = sum(1 for node in nodes if node.type == "Answer")
    summary.riskyNodes = sum(1 for node in nodes if node.isRisky)
    summary.cleanNodes = max(len(nodes) - summary.riskyNodes, 0)
    return Topic4LineageResponse(
        connected=True,
        base_url=client.base_url,
        message=message,
        fallback=workflow_mode == "topic4_build_graph_fallback",
        next_action=next_action,
        endpoints=TOPIC4_ENDPOINTS,
        summary=summary,
        nodes=nodes,
        edges=edges,
        workflowMode=workflow_mode,
        workflowStages=workflow_stages,
        annotations=annotations,
        cleaningActions=cleaning_actions,
        reportSummary=report_summary,
        selectedNodeId=nodes[0].id if nodes else "",
    )


def load_topic4_static_lineage() -> Topic4LineageResponse:
    """Load Topic4 offline prerun lineage asset bundled in Project 5."""
    asset_dir = _resolve_topic4_static_asset_dir()
    if asset_dir is None:
        return Topic4LineageResponse(
            connected=False,
            base_url="static://topic4_medical_demo_static",
            message="课题四静态血缘资产未找到。",
            source="topic4_static_prerun",
            mode="static_asset",
            fallback=False,
            blocking_reason="仓库内缺少 web/backend/data/input_lineage/topic4_medical_demo_static。",
            next_action="请确认静态资产已随 Project_5 仓库发布后重试。",
            endpoints=TOPIC4_ENDPOINTS,
        )

    manifest = _read_json_object(asset_dir / "manifest.json")
    graph = _read_json_object(asset_dir / "merged_lineage_graph.json")
    annotations_payload = _read_json_payload(asset_dir / "risk_annotations.json")
    if manifest.get("asset_id") != TOPIC4_STATIC_ASSET_ID:
        return _topic4_static_asset_failure("静态血缘资产清单无效。")
    if not isinstance(graph.get("nodes"), list) or not graph["nodes"]:
        return _topic4_static_asset_failure("静态血缘资产未包含有效节点。")
    if not isinstance(graph.get("edges"), list):
        return _topic4_static_asset_failure("静态血缘资产未包含有效边集合。")
    if not isinstance(annotations_payload, list):
        return _topic4_static_asset_failure("静态血缘风险标注文件无效。")
    annotations = annotations_payload

    nodes = _normalize_nodes(graph, records=[])
    edges = _normalize_edges(graph, {node.id for node in nodes})
    if not nodes:
        return _topic4_static_asset_failure("静态血缘资产节点无法归一化。")
    expected_nodes = int(manifest.get("node_count") or 0)
    expected_edges = int(manifest.get("edge_count") or 0)
    if expected_nodes and expected_nodes != len(nodes):
        return _topic4_static_asset_failure("静态血缘资产节点计数校验失败。")
    if expected_edges and expected_edges != len(edges):
        return _topic4_static_asset_failure("静态血缘资产边计数校验失败。")
    summary = _normalize_summary(graph)
    summary.totalNodes = len(nodes)
    summary.totalEdges = len(edges)
    summary.metaCount = sum(1 for node in nodes if node.type == "Meta")
    summary.chunkCount = sum(1 for node in nodes if node.type == "Chunk")
    summary.cleanedChunkCount = sum(1 for node in nodes if node.type == "CleanedChunk")
    summary.questionCount = sum(1 for node in nodes if node.type == "Question")
    summary.answerCount = sum(1 for node in nodes if node.type == "Answer")
    summary.riskyNodes = sum(1 for node in nodes if node.isRisky)
    summary.cleanNodes = max(len(nodes) - summary.riskyNodes, 0)

    asset_name = str(manifest.get("name") or "课题四静态血缘预跑")
    report_summary = str(
        manifest.get("report_summary")
        or f"已加载课题四静态血缘资产：{summary.totalNodes} 节点 / {summary.totalEdges} 边。"
    )
    stages = [
        Topic4WorkflowStage(
            key="static_asset",
            label="静态预跑资产",
            description="已读取课题四发布的离线预跑结果。",
        ),
        Topic4WorkflowStage(
            key="build_graph",
            label="血缘图谱构建",
            description="图谱结构来自课题四离线导出结果。",
        ),
        Topic4WorkflowStage(
            key="merge",
            label="风险标注合并",
            description=f"已内置合并 {len(annotations)} 条风险标注。",
        ),
    ]
    return Topic4LineageResponse(
        connected=True,
        service=asset_name,
        base_url="",
        message="",
        source="topic4_static_prerun",
        mode="static_asset",
        fallback=False,
        next_action="",
        endpoints=[],
        summary=summary,
        nodes=nodes,
        edges=edges,
        workflowMode="topic4_static_prerun",
        workflowStages=stages,
        annotations=annotations,
        cleaningActions=[],
        reportSummary=report_summary,
        selectedNodeId=nodes[0].id if nodes else "",
    )


def _topic4_static_asset_failure(message: str) -> Topic4LineageResponse:
    return Topic4LineageResponse(
        connected=False,
        base_url=f"static://{TOPIC4_STATIC_ASSET_ID}",
        message=message,
        source="topic4_static_prerun",
        mode="static_asset",
        fallback=False,
        blocking_reason="仓库内静态预跑资产缺失、损坏或版本不一致。",
        next_action="请重新发布课题四静态预跑资产后重试。",
        endpoints=TOPIC4_ENDPOINTS,
    )


def _resolve_topic4_static_asset_dir() -> Path | None:
    here = Path(__file__).resolve()
    backend_root = here.parents[2]
    project_root = here.parents[4]
    candidates = [
        backend_root / "data" / "input_lineage" / TOPIC4_STATIC_ASSET_ID,
        project_root / "data" / "input_lineage" / TOPIC4_STATIC_ASSET_ID,
        Path.cwd() / "data" / "input_lineage" / TOPIC4_STATIC_ASSET_ID,
    ]
    for path in candidates:
        if (path / "merged_lineage_graph.json").is_file():
            return path
    return None


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = _read_json_payload(path)
    return payload if isinstance(payload, dict) else {}


def _read_json_payload(path: Path) -> Any:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build_topic4_records_from_documents(
    documents: list[dict[str, Any]],
    *,
    dataset_name: str = "",
    dataset_domain: str = "",
    dataset_volume: str = "",
    dataset_desc: str = "",
) -> Topic4LineageParseResponse:
    records: list[dict[str, Any]] = []
    failures: list[Topic4LineageParseFailure] = []
    dataset_context = _dataset_context_text(
        dataset_name=dataset_name,
        dataset_domain=dataset_domain,
        dataset_volume=dataset_volume,
        dataset_desc=dataset_desc,
    )

    for document_index, document in enumerate(documents):
        filename = str(document.get("filename") or f"upload-{document_index + 1}")
        raw = document.get("raw")
        content_type = str(document.get("content_type") or "")
        if not isinstance(raw, bytes):
            failures.append(Topic4LineageParseFailure(name=filename, reason="文件内容为空"))
            continue
        if not is_supported_upload(filename, content_type):
            failures.append(Topic4LineageParseFailure(name=filename, reason="不支持的文件类型"))
            continue

        try:
            text = extract_text_from_bytes(filename, raw, content_type)
            if len(text) < MIN_TOPIC4_TEXT_LENGTH:
                raise ValueError("提取文本过短")
        except Exception as exc:
            failures.append(Topic4LineageParseFailure(name=filename, reason=str(exc)))
            continue

        chunks = _split_topic4_chunks(text)
        for chunk_index, chunk in enumerate(chunks):
            chunk_fingerprint = content_hash(f"{filename}\n{chunk}")[:10]
            chunk_id = _topic4_chunk_id(document_index, chunk_index, chunk_fingerprint, "CHUNK")
            cleaned_chunk_id = _topic4_chunk_id(
                document_index,
                chunk_index,
                chunk_fingerprint,
                "CLEANED",
            )
            cleaned_chunk = clean_text(chunk)
            records.append(
                {
                    "source": filename,
                    "source_hash": chunk_fingerprint,
                    "dataset_name": dataset_name,
                    "dataset_domain": dataset_domain,
                    "dataset_volume": dataset_volume,
                    "dataset_description": dataset_desc,
                    "chunk_id": chunk_id,
                    "cleaned_chunk_id": cleaned_chunk_id,
                    "raw_chunk": chunk,
                    "cleaned_chunk": cleaned_chunk,
                    "metadata": {
                        "dataset_context": dataset_context,
                        "dataset_name": dataset_name,
                        "dataset_domain": dataset_domain,
                        "dataset_volume": dataset_volume,
                        "dataset_description": dataset_desc,
                        "source": filename,
                        "source_path": filename,
                    },
                    "QA_pairs": _build_topic4_qa_pairs(
                        filename=filename,
                        chunk=cleaned_chunk or chunk,
                        dataset_name=dataset_name,
                        dataset_domain=dataset_domain,
                    ),
                }
            )

    return Topic4LineageParseResponse(records=records, failures=failures)


def _workflow_source(records: list[dict[str, Any]]) -> str:
    for record in records:
        source = str(record.get("source") or "").strip()
        if source:
            return source
    return "project5_uploaded_dataset"


def _extract_graph(payload: dict[str, Any], key: str) -> dict[str, Any]:
    graph = payload.get(key)
    if isinstance(graph, dict):
        return graph
    raise Topic4InputWorkflowUnavailable(f"Topic4 workflow result missing {key}")


async def _try_build_graph_fallback(
    client: Any,
    records: list[dict[str, Any]],
    _full_workflow_error: Exception,
) -> tuple[dict[str, Any], list[dict], list[dict], str, str, list[Topic4WorkflowStage], str, str] | None:
    """Fall back to minimal /api/build_graph when full_v2 lacks dataflow/vLLM deps."""
    try:
        lineage_graph = await client.build_graph(records)
    except Topic4InputWorkflowUnavailable:
        return None

    stages = [
        Topic4WorkflowStage(
            key="full_v2",
            label="完整工作流",
            status="failed",
            description="自动标注与清洗暂未完成，已返回基础血缘图谱。",
        ),
        Topic4WorkflowStage(
            key="build_graph",
            label="基础图谱构建",
            status="completed",
            description="已根据当前训练语料生成节点与关系，可继续浏览和复核。",
        ),
    ]
    message = "已生成基础血缘图谱，自动风险标注与清洗结果暂未返回。"
    next_action = "当前图谱可继续用于节点浏览和后续风险识别。"
    return (
        lineage_graph,
        [],
        [],
        "",
        "topic4_build_graph_fallback",
        stages,
        message,
        next_action,
    )


def _topic4_full_workflow_failed_response(
    base_url: str,
    error_message: str,
) -> Topic4LineageResponse:
    return Topic4LineageResponse(
        connected=False,
        base_url=base_url,
        message="课题四完整工作流失败，未生成可信风险图谱。",
        fallback=False,
        blocking_reason=f"课题四 full_v2 完整工作流失败：{error_message}",
        next_action="请确认课题四风险标注、建图、合并、清洗和报告链路均可用后重新生成。",
        endpoints=TOPIC4_ENDPOINTS,
        workflowMode="topic4_full_v2_failed",
        workflowStages=[
            Topic4WorkflowStage(
                key="full_v2",
                label="完整工作流",
                status="failed",
                description="课题四 full_v2 与最小建图均失败时，不降级为中性风险图谱。",
            )
        ],
    )


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _report_summary(payload: dict[str, Any]) -> str:
    for key in ("analysis_report", "llm_report"):
        report = payload.get(key)
        if not isinstance(report, dict):
            continue
        for field in ("summary", "conclusion", "overall_summary"):
            value = report.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()[:240]
    return ""


def _full_workflow_stages(
    *,
    annotation_count: int,
    cleaning_action_count: int,
    report_summary: str,
) -> list[Topic4WorkflowStage]:
    return [
        Topic4WorkflowStage(
            key="parse_records",
            label="文件解析",
            description="已从上传材料中提取可用于建图的文本片段。",
        ),
        Topic4WorkflowStage(
            key="annotate",
            label="风险识别",
            description=f"已识别并合并 {annotation_count} 条风险标注。",
        ),
        Topic4WorkflowStage(
            key="build_graph",
            label="血缘图谱构建",
            description="已生成训练语料的节点与关系。",
        ),
        Topic4WorkflowStage(
            key="merge",
            label="风险标注合并",
            description="风险信息已合并到对应图谱节点。",
        ),
        Topic4WorkflowStage(
            key="cleaning",
            label="修正建议",
            description=f"已生成 {cleaning_action_count} 条清洗或修正动作。",
        ),
        Topic4WorkflowStage(
            key="report",
            label="结果摘要",
            description=report_summary or "已完成图谱分析，当前未返回额外摘要。",
        ),
    ]


def _build_merge_stages(annotation_count: int) -> list[Topic4WorkflowStage]:
    return [
        Topic4WorkflowStage(
            key="build_graph",
            label="血缘图谱构建",
            description="已生成训练语料的节点与关系。",
        ),
        Topic4WorkflowStage(
            key="merge",
            label="风险标注合并",
            description=f"已合并 {annotation_count} 条风险标注。",
        ),
    ]


def _dataset_context_text(
    *,
    dataset_name: str = "",
    dataset_domain: str = "",
    dataset_volume: str = "",
    dataset_desc: str = "",
) -> str:
    return clean_text(
        "\n".join(
            [
                f"数据集名称：{dataset_name or '未命名训练语料'}",
                f"数据场景：{dataset_domain or '未填写'}",
                f"数据量级：{dataset_volume or '未填写'}",
                f"数据集描述：{dataset_desc or '未填写'}",
            ]
        )
    )


def _split_topic4_chunks(text: str) -> list[str]:
    normalized = clean_text(text)
    if not normalized:
        return []
    paragraphs = [part.strip() for part in normalized.split("\n") if part.strip()]
    chunks: list[str] = []
    buffer = ""

    for paragraph in paragraphs or [normalized]:
        if len(paragraph) > MAX_TOPIC4_CHARS_PER_CHUNK:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(
                paragraph[index : index + MAX_TOPIC4_CHARS_PER_CHUNK]
                for index in range(0, len(paragraph), MAX_TOPIC4_CHARS_PER_CHUNK)
            )
            continue

        next_value = f"{buffer}\n{paragraph}".strip() if buffer else paragraph
        if len(next_value) <= MAX_TOPIC4_CHARS_PER_CHUNK:
            buffer = next_value
            continue
        if buffer:
            chunks.append(buffer)
        buffer = paragraph

    if buffer:
        chunks.append(buffer)
    return chunks[:MAX_TOPIC4_CHUNKS_PER_FILE]


def _build_topic4_qa_pairs(
    *,
    filename: str,
    chunk: str,
    dataset_name: str = "",
    dataset_domain: str = "",
) -> list[dict[str, Any]]:
    """从上传正文启发式生成 QA，丰富课题四 Question/Answer 血缘层。"""
    pairs: list[dict[str, Any]] = [
        {
            "question": "【血缘元数据】该节点对应的原始上传文档是什么？",
            "answer": filename,
            "type": "source_document",
            "supporting_facts": [filename],
        }
    ]

    normalized = clean_text(chunk)
    if not normalized:
        return pairs[:MAX_TOPIC4_QA_PAIRS_PER_CHUNK]

    summary = _topic4_summary_text(normalized)
    if summary:
        pairs.append(
            {
                "question": "该训练语料片段的主要内容是什么？",
                "answer": summary,
                "type": "chunk_summary",
                "supporting_facts": [summary],
            }
        )

    for index, sentence in enumerate(_topic4_fact_sentences(normalized), start=1):
        if len(pairs) >= MAX_TOPIC4_QA_PAIRS_PER_CHUNK:
            break
        # 避免与摘要完全重复。
        if summary and sentence == summary:
            continue
        pairs.append(
            {
                "question": f"该片段中的关键信息 {index} 是什么？",
                "answer": sentence,
                "type": "chunk_fact",
                "supporting_facts": [sentence],
            }
        )

    if dataset_name and len(pairs) < MAX_TOPIC4_QA_PAIRS_PER_CHUNK:
        pairs.append(
            {
                "question": "该训练语料片段归属哪个数据集？",
                "answer": dataset_name,
                "type": "dataset_context",
                "supporting_facts": [
                    value for value in [dataset_name, dataset_domain] if value
                ],
            }
        )

    return pairs[:MAX_TOPIC4_QA_PAIRS_PER_CHUNK]


def _topic4_summary_text(text: str) -> str:
    compact = " ".join(text.split())
    if not compact:
        return ""
    sentences = _topic4_fact_sentences(compact)
    if sentences:
        return sentences[0][:MAX_TOPIC4_SUMMARY_CHARS]
    return compact[:MAX_TOPIC4_SUMMARY_CHARS]


def _topic4_fact_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；;.!?])\s*|\n+", text)
    sentences: list[str] = []
    seen: set[str] = set()
    for part in parts:
        sentence = clean_text(part)
        if len(sentence) < MIN_TOPIC4_FACT_SENTENCE_CHARS:
            continue
        clipped = sentence[:MAX_TOPIC4_FACT_CHARS]
        if clipped in seen:
            continue
        seen.add(clipped)
        sentences.append(clipped)
        if len(sentences) >= MAX_TOPIC4_QA_PAIRS_PER_CHUNK:
            break
    return sentences


def _topic4_chunk_id(
    document_index: int,
    chunk_index: int,
    chunk_fingerprint: str,
    suffix: str,
) -> str:
    return f"P5_DOC{document_index + 1:02d}_{chunk_index + 1:02d}_{chunk_fingerprint}_{suffix}"


def _repair_question_mark_content(graph: dict[str, Any], records: list[dict[str, Any]]) -> None:
    replacements = _record_content_replacements(records)
    qa_types = _record_qa_types(records)
    if not replacements and not qa_types:
        return

    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        properties = node.get("properties")
        if not isinstance(properties, dict):
            properties = {}
            node["properties"] = properties
        if node_id in qa_types and not str(properties.get("type") or "").strip():
            properties["type"] = qa_types[node_id]
        if node_id not in replacements:
            continue
        current = str(
            properties.get("content") or properties.get("question") or properties.get("answer") or ""
        )
        if _looks_like_replacement_text(current):
            properties["content"] = replacements[node_id]


def _record_qa_types(records: list[dict[str, Any]]) -> dict[str, str]:
    qa_types: dict[str, str] = {}
    for record in records:
        cleaned_chunk_id = str(record.get("cleaned_chunk_id") or "")
        qa_pairs = record.get("QA_pairs", [])
        if not cleaned_chunk_id or not isinstance(qa_pairs, list):
            continue
        for index, qa in enumerate(qa_pairs):
            if not isinstance(qa, dict):
                continue
            qa_type = str(qa.get("type") or "").strip()
            if not qa_type:
                continue
            qa_types[f"Q_{cleaned_chunk_id}_{index:03d}"] = qa_type
            qa_types[f"A_{cleaned_chunk_id}_{index:03d}"] = qa_type
    return qa_types


def _record_content_replacements(records: list[dict[str, Any]]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for record in records:
        chunk_id = str(record.get("chunk_id") or "")
        cleaned_chunk_id = str(record.get("cleaned_chunk_id") or "")
        raw_chunk = str(record.get("raw_chunk") or record.get("raw_content") or "")
        cleaned_chunk = str(record.get("cleaned_chunk") or record.get("cleaned") or raw_chunk)
        if chunk_id and raw_chunk:
            replacements[chunk_id] = raw_chunk
        if cleaned_chunk_id and cleaned_chunk:
            replacements[cleaned_chunk_id] = cleaned_chunk

        qa_pairs = record.get("QA_pairs", [])
        if not isinstance(qa_pairs, list):
            continue
        for index, qa in enumerate(qa_pairs):
            if not isinstance(qa, dict) or not cleaned_chunk_id:
                continue
            question_id = f"Q_{cleaned_chunk_id}_{index:03d}"
            answer_id = f"A_{cleaned_chunk_id}_{index:03d}"
            question = str(qa.get("question") or "")
            answer = str(qa.get("answer") or "")
            if question:
                replacements[question_id] = question
            if answer:
                replacements[answer_id] = answer
    return replacements


def _looks_like_replacement_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    question_marks = text.count("?")
    return question_marks >= 3 and question_marks / max(len(text), 1) >= 0.35


def _normalize_summary(graph: dict[str, Any]) -> Topic4LineageSummary:
    stats = graph.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    risk_metadata = graph.get("risk_metadata", {})
    if not isinstance(risk_metadata, dict):
        risk_metadata = {}

    return Topic4LineageSummary(
        totalNodes=_to_int(stats.get("total_nodes")),
        totalEdges=_to_int(stats.get("total_edges")),
        metaCount=_to_int(stats.get("meta_count")),
        chunkCount=_to_int(stats.get("chunk_count")),
        cleanedChunkCount=_to_int(stats.get("cleaned_chunk_count")),
        questionCount=_to_int(stats.get("question_count")),
        answerCount=_to_int(stats.get("answer_count")),
        riskyNodes=_to_int(stats.get("risky_nodes") or risk_metadata.get("total_risky_nodes")),
        cleanNodes=_to_int(stats.get("clean_nodes") or risk_metadata.get("total_clean_nodes")),
    )


def _normalize_nodes(
    graph: dict[str, Any],
    *,
    records: list[dict[str, Any]] | None = None,
) -> list[Topic4LineageNode]:
    doc_name_by_node = _resolve_doc_names(graph, records or [])
    result: list[Topic4LineageNode] = []
    for item in graph.get("nodes", []):
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "")
        if not node_id:
            continue
        properties = item.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}

        doc_name = doc_name_by_node.get(node_id) or _direct_doc_name(properties)
        node_type = str(item.get("type") or "Unknown")
        result.append(
            Topic4LineageNode(
                id=node_id,
                type=node_type,
                summary=_node_summary(properties, node_type=node_type),
                url=str(properties.get("source_path") or properties.get("text_path") or ""),
                docName=doc_name or "未绑定上传文档",
                docId=_doc_id_from_name(doc_name, node_id),
                topic=_node_topic(properties, node_type=node_type),
                isRisky=bool(properties.get("is_risky")),
                riskLevel=str(properties.get("risk_level") or properties.get("severity") or "none"),
                riskTypes=[
                    str(value)
                    for value in properties.get("risk_types", [])
                    if isinstance(value, str) and value
                ],
            )
        )
    return result[:MAX_TOPIC4_DISPLAY_NODES]


def _direct_doc_name(properties: dict[str, Any]) -> str:
    for key in ("source_path", "source", "filename", "doc_name", "document_name"):
        value = str(properties.get(key) or "").strip()
        if value and value != "课题四联调样例":
            return value
    return ""


def _doc_id_from_name(doc_name: str, node_id: str) -> str:
    if doc_name and doc_name != "未绑定上传文档":
        return Path(doc_name).stem[:64] if "/" in doc_name or "\\" in doc_name else doc_name[:64]
    return node_id.split("_")[0]


def _resolve_doc_names(graph: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, str]:
    """从 Meta / records / 边关系推导每个节点对应的上传文档名。"""
    doc_names: dict[str, str] = {}

    for record in records:
        source = str(record.get("source") or "").strip()
        if not source:
            continue
        for key in ("chunk_id", "cleaned_chunk_id"):
            node_id = str(record.get(key) or "").strip()
            if node_id:
                doc_names[node_id] = source
        qa_pairs = record.get("QA_pairs", [])
        cleaned_chunk_id = str(record.get("cleaned_chunk_id") or "")
        if isinstance(qa_pairs, list) and cleaned_chunk_id:
            for index, _qa in enumerate(qa_pairs):
                doc_names[f"Q_{cleaned_chunk_id}_{index:03d}"] = source
                doc_names[f"A_{cleaned_chunk_id}_{index:03d}"] = source

    for item in graph.get("nodes", []):
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "")
        if not node_id:
            continue
        properties = item.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        direct = _direct_doc_name(properties)
        if direct:
            doc_names[node_id] = direct

    adjacency: dict[str, list[str]] = {}
    for item in graph.get("edges", []):
        if not isinstance(item, dict):
            continue
        source = str(
            item.get("source")
            or item.get("from")
            or item.get("from_id")
            or item.get("start")
            or ""
        )
        target = str(
            item.get("target")
            or item.get("to")
            or item.get("to_id")
            or item.get("end")
            or ""
        )
        if not source or not target:
            continue
        adjacency.setdefault(source, []).append(target)
        # 血缘边多为有向，但也允许反向继承，避免子节点先出现时丢文档名。
        adjacency.setdefault(target, []).append(source)

    changed = True
    while changed:
        changed = False
        for node_id, neighbors in adjacency.items():
            current = doc_names.get(node_id, "")
            if current:
                for neighbor in neighbors:
                    if neighbor not in doc_names:
                        doc_names[neighbor] = current
                        changed = True
                continue
            for neighbor in neighbors:
                inherited = doc_names.get(neighbor, "")
                if inherited:
                    doc_names[node_id] = inherited
                    changed = True
                    break

    return doc_names


def _normalize_edges(graph: dict[str, Any], valid_node_ids: set[str]) -> list[Topic4LineageEdge]:
    result: list[Topic4LineageEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(graph.get("edges", [])):
        if not isinstance(item, dict):
            continue
        source = str(
            item.get("source")
            or item.get("from")
            or item.get("from_id")
            or item.get("start")
            or ""
        )
        target = str(
            item.get("target")
            or item.get("to")
            or item.get("to_id")
            or item.get("end")
            or ""
        )
        if not source or not target:
            continue
        if valid_node_ids and (source not in valid_node_ids or target not in valid_node_ids):
            continue
        edge_type = str(item.get("type") or item.get("relation") or item.get("label") or "related")
        dedupe_key = (source, target, edge_type)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        edge_id = str(item.get("id") or f"{source}->{target}:{index}")
        result.append(
            Topic4LineageEdge(
                id=edge_id,
                source=source,
                target=target,
                type=edge_type,
            )
        )
    return result


def _build_lineage_skeleton_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """按课题四同款血缘模板，从 records 确定性重建节点与边。"""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    sources: dict[str, str] = {}

    def add_node(node_id: str, node_type: str, properties: dict[str, Any]) -> None:
        if not node_id or node_id in seen_ids:
            return
        seen_ids.add(node_id)
        nodes.append({"id": node_id, "type": node_type, "properties": properties})

    def add_edge(source: str, target: str, edge_type: str) -> None:
        if not source or not target:
            return
        edges.append({"from": source, "to": target, "type": edge_type})

    for record in records:
        source_name = str(record.get("source") or "").strip()
        if source_name and source_name not in sources:
            meta_id = f"META_{len(sources):04d}"
            sources[source_name] = meta_id
            add_node(
                meta_id,
                "Meta",
                {
                    "source_path": source_name,
                    "source": source_name,
                    "text_path": str(record.get("text_path") or ""),
                },
            )

    for index, record in enumerate(records):
        source_name = str(record.get("source") or "").strip()
        meta_id = sources.get(source_name, f"META_{index:04d}")
        chunk_id = str(record.get("chunk_id") or f"CHUNK_{index:04d}")
        cleaned_id = str(record.get("cleaned_chunk_id") or f"CCHUNK_{index:04d}")
        raw_text = str(record.get("raw_chunk") or record.get("raw_content") or "")
        cleaned_text = str(
            record.get("cleaned_chunk") or record.get("cleaned") or record.get("text") or raw_text
        )

        risk_props = _record_risk_properties(record)
        add_node(
            chunk_id,
            "Chunk",
            {
                "content": raw_text[:2000],
                "full_length": len(raw_text),
                "source": source_name,
                "source_path": source_name,
                **risk_props,
            },
        )
        add_edge(meta_id, chunk_id, "contains")

        add_node(
            cleaned_id,
            "CleanedChunk",
            {
                "content": cleaned_text[:2000],
                "source": source_name,
                "source_path": source_name,
                "cleaning_steps": record.get("cleaning_steps", [])
                if isinstance(record.get("cleaning_steps"), list)
                else [],
                **risk_props,
            },
        )
        add_edge(chunk_id, cleaned_id, "cleaned_to")

        qa_pairs = record.get("QA_pairs", [])
        if not isinstance(qa_pairs, list):
            continue
        for qa_index, qa in enumerate(qa_pairs):
            if not isinstance(qa, dict):
                continue
            question_id = f"Q_{cleaned_id}_{qa_index:03d}"
            answer_id = f"A_{cleaned_id}_{qa_index:03d}"
            qa_type = str(qa.get("type") or "")
            add_node(
                question_id,
                "Question",
                {
                    "content": str(qa.get("question") or ""),
                    "type": qa_type,
                    "source": source_name,
                    "source_path": source_name,
                    **risk_props,
                },
            )
            add_node(
                answer_id,
                "Answer",
                {
                    "content": str(qa.get("answer") or ""),
                    "type": qa_type,
                    "supporting_facts": qa.get("supporting_facts", [])
                    if isinstance(qa.get("supporting_facts"), list)
                    else [],
                    "source": source_name,
                    "source_path": source_name,
                    **risk_props,
                },
            )
            add_edge(cleaned_id, question_id, "has_question")
            add_edge(question_id, answer_id, "answers")
            add_edge(answer_id, cleaned_id, "answers_question_from")

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "meta_count": sum(1 for node in nodes if node["type"] == "Meta"),
            "chunk_count": sum(1 for node in nodes if node["type"] == "Chunk"),
            "cleaned_chunk_count": sum(1 for node in nodes if node["type"] == "CleanedChunk"),
            "question_count": sum(1 for node in nodes if node["type"] == "Question"),
            "answer_count": sum(1 for node in nodes if node["type"] == "Answer"),
        },
    }


def _record_risk_properties(record: dict[str, Any]) -> dict[str, Any]:
    """从课题五 records / risk meta / 价值质量档推导节点高亮属性。"""
    explicit = record.get("is_risky")
    if isinstance(explicit, bool):
        is_risky = explicit
    else:
        label = str(record.get("original_label") or record.get("risk_label") or "").strip().lower()
        is_risky = label == "unsafe" or str(explicit).strip().lower() in {"1", "true", "yes"}

    risk_types: list[str] = []
    for key in ("harm_category_L1", "harm_category_l1", "risk_category_l1"):
        value = str(record.get(key) or "").strip()
        if value:
            risk_types.append(value)
            break
    if is_risky:
        return {
            "is_risky": True,
            "risk_level": "High",
            "risk_types": risk_types,
            "severity": "High",
        }

    # 价值轨：quality_level=low / 待提升 → 图谱高亮（复用 is_risky 计数通道）
    quality = str(record.get("quality_level") or "").strip().lower()
    status = str(record.get("quality_status") or record.get("status") or "").strip()
    needs_improvement = str(record.get("needs_improvement") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if (
        needs_improvement
        or quality in {"low", "待提升"}
        or status in {"待提升", "improve", "low"}
    ):
        dim = str(
            record.get("primary_dimension")
            or record.get("secondary_dimension")
            or "待提升"
        ).strip()
        return {
            "is_risky": True,
            "risk_level": "Improve",
            "risk_types": [dim or "待提升"],
            "severity": "Improve",
        }

    return {
        "is_risky": False,
        "risk_level": "none",
        "risk_types": [],
    }


def _overlay_topic4_properties(
    skeleton: dict[str, Any],
    topic4_graph: dict[str, Any],
) -> None:
    """把课题四返回的风险/正文属性回填到确定性骨架节点上。"""
    topic4_nodes = {
        str(item.get("id") or ""): item
        for item in topic4_graph.get("nodes", [])
        if isinstance(item, dict) and item.get("id")
    }
    risk_keys = (
        "is_risky",
        "risk_level",
        "risk_types",
        "severity",
        "risk_details",
        "propagated_from",
    )
    for node in skeleton.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        upstream = topic4_nodes.get(node_id)
        if not upstream:
            continue
        upstream_props = upstream.get("properties")
        if not isinstance(upstream_props, dict):
            continue
        properties = node.get("properties")
        if not isinstance(properties, dict):
            properties = {}
            node["properties"] = properties
        keep_value_improve = properties.get("risk_level") == "Improve" and not upstream_props.get(
            "is_risky"
        )
        for key in risk_keys:
            if key in upstream_props:
                if keep_value_improve and key in {"is_risky", "risk_level", "risk_types", "severity"}:
                    continue
                properties[key] = upstream_props[key]
        for key in ("content", "question", "answer"):
            value = upstream_props.get(key)
            if isinstance(value, str) and value.strip() and not _looks_like_replacement_text(value):
                properties[key] = value

    risk_metadata = topic4_graph.get("risk_metadata")
    if isinstance(risk_metadata, dict):
        skeleton["risk_metadata"] = risk_metadata
        stats = skeleton.get("stats")
        if isinstance(stats, dict):
            stats["risky_nodes"] = _to_int(
                risk_metadata.get("total_risky_nodes") or stats.get("risky_nodes")
            )
            stats["clean_nodes"] = _to_int(
                risk_metadata.get("total_clean_nodes") or stats.get("clean_nodes")
            )


def _node_summary(properties: dict[str, Any], *, node_type: str = "") -> str:
    content = str(
        properties.get("content") or properties.get("question") or properties.get("answer") or ""
    )
    qa_type = str(properties.get("type") or "").strip()
    if content:
        summary = content[:160]
        if qa_type in {"source_document", "dataset_context"} or summary.startswith("【血缘元数据】"):
            if not summary.startswith("【血缘元数据】"):
                return f"【血缘元数据】{summary}"
            return summary
        if node_type in {"Question", "Answer"} and qa_type:
            return f"【{qa_type}】{summary}"
        return summary
    risk_details = properties.get("risk_details", [])
    if isinstance(risk_details, list) and risk_details:
        first = risk_details[0]
        if isinstance(first, dict):
            return str(first.get("content") or "")[:160]
    return "课题四返回的血缘图谱节点。"


def _node_topic(properties: dict[str, Any], *, node_type: str = "") -> str:
    qa_type = str(properties.get("type") or "").strip()
    if qa_type in {"source_document", "dataset_context"}:
        return f"血缘元数据 / {qa_type}"
    if qa_type in {"chunk_summary", "chunk_fact"}:
        return f"语料问答 / {qa_type}"
    if node_type in {"Question", "Answer"} and qa_type:
        return f"问答节点 / {qa_type}"
    if properties.get("is_risky"):
        level = str(properties.get("risk_level") or properties.get("severity") or "unknown")
        if level == "Improve":
            return "待提升节点 / Improve"
        return f"风险节点 / {level}"
    return "血缘图谱节点 / 无风险标记"


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
