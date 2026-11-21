"""One-off helper: pack Topic4 demo-data into Project5 static lineage asset."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

DEFAULT_OUT = (
    Path(__file__).resolve().parents[1]
    / "web"
    / "backend"
    / "data"
    / "input_lineage"
    / "topic4_medical_demo_static"
)
EMAIL_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+\s*[@＠]\s*[A-Za-z0-9.．-]+[.．][A-Za-z]{2,}"),
    re.compile(r"[A-Za-z0-9._%+-]+\s*\$@\$\s*[A-Za-z0-9.．-]+[.．][A-Za-z]{2,}"),
)


def redact_personal_contacts(value):
    """Remove author contact details from the bundled demonstration asset."""
    if isinstance(value, str):
        for pattern in EMAIL_PATTERNS:
            value = pattern.sub("[邮箱已脱敏]", value)
        return value
    if isinstance(value, list):
        return [redact_personal_contacts(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_personal_contacts(item) for key, item in value.items()}
    return value


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo-dir",
        type=Path,
        required=True,
        help="Topic4 demo_result directory containing lineage_graph.json.",
    )
    parser.add_argument(
        "--project4-dir",
        type=Path,
        default=project_root.parent.parent / "Project_4_Input_workflow",
        help="Project_4_Input_workflow repository root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUT,
        help="Destination directory for the bundled static asset.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    demo_dir = args.demo_dir.resolve()
    project4_dir = args.project4_dir.resolve()
    output_dir = args.output_dir.resolve()
    lineage_path = demo_dir / "lineage_graph.json"
    annotations_path = demo_dir / "risk_annotations.json"
    merger_path = project4_dir / "risk_graph_merger.py"
    for required in (lineage_path, annotations_path, merger_path):
        if not required.is_file():
            raise FileNotFoundError(f"required input not found: {required}")

    output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(project4_dir))
    from risk_graph_merger import RiskGraphMerger

    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    anns = json.loads(annotations_path.read_text(encoding="utf-8"))
    schema: dict = {}
    for name in ("risk_schema.json", "_default_risk_schema.json"):
        path = demo_dir / name
        if path.exists():
            schema = json.loads(path.read_text(encoding="utf-8"))
            break

    merged = RiskGraphMerger(schema).merge(lineage, anns)

    for node in merged["nodes"]:
        props = node.get("properties") or {}
        for key in ("source_path", "text_path"):
            value = props.get(key)
            if isinstance(value, str) and value:
                props[key] = Path(value.replace("\\", "/")).name
        # Keep node payloads compact for git/demo.
        content = props.get("content")
        if isinstance(content, str) and len(content) > 360:
            props["content"] = content[:360] + "…"
        facts = props.get("supporting_facts")
        if isinstance(facts, list) and len(facts) > 3:
            props["supporting_facts"] = facts[:3]
        node["properties"] = props

    node_by_id = {node["id"]: node for node in merged["nodes"]}
    children: dict[str, list[str]] = defaultdict(list)
    for edge in merged["edges"]:
        frm = edge.get("from") or edge.get("source")
        to = edge.get("to") or edge.get("target")
        if frm and to:
            children[frm].append(to)

    def subtree(meta_id: str) -> set[str]:
        seen: set[str] = set()
        queue: deque[str] = deque([meta_id])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            for nxt in children.get(current, []):
                if nxt not in seen:
                    queue.append(nxt)
        return seen

    def risky_count(ids: set[str]) -> int:
        total = 0
        for node_id in ids:
            node = node_by_id.get(node_id)
            if node and (node.get("properties") or {}).get("is_risky"):
                total += 1
        return total

    ranked = []
    for meta in (node for node in merged["nodes"] if node.get("type") == "Meta"):
        ids = subtree(meta["id"])
        ranked.append((risky_count(ids), len(ids), meta["id"], ids))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))

    selected: set[str] = set()
    picked_metas: list[str] = []
    for risk_c, size, meta_id, ids in ranked:
        if len(picked_metas) >= 10:
            break
        if not selected:
            selected |= ids
            picked_metas.append(meta_id)
            continue
        if len(selected) + size > 340 and len(picked_metas) >= 4:
            continue
        selected |= ids
        picked_metas.append(meta_id)
        if len(selected) >= 280 and len(picked_metas) >= 6:
            break

    nodes = [node for node in merged["nodes"] if node.get("id") in selected]
    idset = set(selected)
    edges = []
    for edge in merged["edges"]:
        frm = edge.get("from") or edge.get("source")
        to = edge.get("to") or edge.get("target")
        if frm in idset and to in idset:
            edges.append({"from": frm, "to": to, "type": edge.get("type") or "related"})

    ann_keep = []
    for ann in anns:
        if ann.get("case_id") not in idset:
            continue
        item = dict(ann)
        original = item.get("original_description")
        if isinstance(original, str) and len(original) > 400:
            item["original_description"] = original[:400] + "…"
        risks = []
        for risk in item.get("risk_list") or []:
            next_risk = dict(risk)
            content = next_risk.get("content")
            if isinstance(content, str) and len(content) > 280:
                next_risk["content"] = content[:280] + "…"
            risks.append(next_risk)
        item["risk_list"] = risks
        ann_keep.append(item)

    types: dict[str, int] = {}
    for node in nodes:
        types[node.get("type", "?")] = types.get(node.get("type", "?"), 0) + 1
    risky_nodes = sum(
        1 for node in nodes if (node.get("properties") or {}).get("is_risky")
    )

    pack = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "meta_count": types.get("Meta", 0),
            "chunk_count": types.get("Chunk", 0),
            "cleaned_chunk_count": types.get("CleanedChunk", 0),
            "question_count": types.get("Question", 0),
            "answer_count": types.get("Answer", 0),
            "risky_nodes": risky_nodes,
            "clean_nodes": max(len(nodes) - risky_nodes, 0),
        },
        "risk_metadata": {
            "total_risky_nodes": risky_nodes,
            "total_clean_nodes": max(len(nodes) - risky_nodes, 0),
        },
    }
    manifest = {
        "asset_id": "topic4_medical_demo_static",
        "name": "课题四医学文献血缘预跑（静态）",
        "source": "topic4_demo_data_export",
        "source_note": (
            "来自课题四 demo-data 离线导出；已合并 risk_annotations，"
            "并裁剪为演示子集。原始 PDF 不可用。演示服务器无需携带 demo-data。"
        ),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "annotation_count": len(ann_keep),
        "risky_nodes": risky_nodes,
        "picked_meta_ids": picked_metas,
        "files": {
            "merged_lineage_graph": "merged_lineage_graph.json",
            "risk_annotations": "risk_annotations.json",
        },
        "report_summary": (
            f"课题四静态预跑资产：{len(picked_metas)} 篇文档子图，"
            f"{len(nodes)} 节点 / {len(edges)} 边，风险节点 {risky_nodes}，"
            f"标注 {len(ann_keep)} 条。无需启动课题四服务即可展示。"
        ),
    }

    sanitized_pack = redact_personal_contacts(pack)
    sanitized_annotations = redact_personal_contacts(ann_keep)
    (output_dir / "merged_lineage_graph.json").write_text(
        json.dumps(sanitized_pack, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "risk_annotations.json").write_text(
        json.dumps(sanitized_annotations, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {output_dir}")
    print(
        f"metas={len(picked_metas)} nodes={len(nodes)} edges={len(edges)} "
        f"risky={risky_nodes} anns={len(ann_keep)}"
    )
    print(
        "MB graph=",
        round((output_dir / "merged_lineage_graph.json").stat().st_size / 1024 / 1024, 2),
        "anns=",
        round((output_dir / "risk_annotations.json").stat().st_size / 1024 / 1024, 2),
    )


if __name__ == "__main__":
    main()
