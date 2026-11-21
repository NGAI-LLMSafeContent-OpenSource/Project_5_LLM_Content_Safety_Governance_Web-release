"""Read-only service probes; API reachability does not prove model execution."""

import asyncio
from datetime import datetime, timezone

from app.adapters.topic1.corpus_tools import CorpusToolClient, CorpusToolError, Tool
from app.core.config import get_settings
from app.schemas.topic1_corpus_tools import Topic1CorpusToolCatalogResult, Topic1ToolServiceStatus


async def enrich_service_status(catalog: Topic1CorpusToolCatalogResult) -> Topic1CorpusToolCatalogResult:
    settings = get_settings()
    configurations: dict[str, tuple[Tool, str, str]] = {
        "data_denoising": ("refinement", settings.topic1_refinement_base_url,
                           settings.topic1_refinement_api_key.get_secret_value()),
        "data_detoxification": ("detox", settings.topic1_detox_base_url, ""),
        "scarcity_evaluation": ("detection", settings.topic1_detection_base_url, ""),
    }
    # Probe fresh copies, never mutate the delivery snapshot or retain old readiness.
    result = catalog.model_copy(deep=True)
    descriptors = [item for item in result.tools if item.tool_key in configurations]
    statuses = await asyncio.gather(*(probe_tool(*configurations[item.tool_key]) for item in descriptors))
    for descriptor, status in zip(descriptors, statuses):
        descriptor.service_status = status
    return result


async def probe_tool(tool: Tool, url: str, api_key: str = "") -> Topic1ToolServiceStatus:
    checked_at = datetime.now(timezone.utc).isoformat()
    if not url.strip():
        return Topic1ToolServiceStatus(connection="not_configured", readiness="unknown",
                                       message="尚未配置工具服务。", checked_at=checked_at)
    try:
        async with CorpusToolClient(tool, url, api_key=api_key,
                                    timeout=get_settings().topic1_corpus_tools_timeout_seconds) as client:
            health = await client.health()
            capabilities = await client.capabilities()
        if tool == "detection":
            if health.get("service") != "scdc-pdd" or capabilities.get("service") != "scdc-pdd" or health.get("status") != "ok":
                raise CorpusToolError("invalid_contract", "服务身份不符合约定。")
            readiness = "unverified"
            message = "服务已连接；模型在任务中加载，尚未验证推理能力。"
        else:
            items = capabilities.get("tools")
            if not isinstance(items, list):
                raise CorpusToolError("invalid_contract", "服务能力信息不完整。")
            if tool == "refinement":
                selected = next((item for item in items if isinstance(item, dict) and item.get("id") == "refinemodel_clean"), None)
                if health.get("status") != "healthy" or selected is None:
                    raise CorpusToolError("invalid_contract", "服务身份不符合约定。")
                ready = selected.get("available") is True and health.get("scheduler") == "running"
                demo = False
            else:
                selected = next((item for item in items if isinstance(item, dict) and item.get("name") == "detox"), None)
                if (health.get("service") != "data-detox" or health.get("status") != "ok"
                        or selected is None or capabilities.get("backend") not in {"real", "demo"}):
                    raise CorpusToolError("invalid_contract", "服务身份不符合约定。")
                ready = selected.get("ready") is True and health.get("worker_alive") is True
                demo = capabilities.get("backend") == "demo" or health.get("backend") == "demo"
            readiness = "demo" if demo else "declared_ready" if ready else "missing_resources"
            message = {
                "demo": "服务当前为演示模式，不能作为真实处理结果。",
                "declared_ready": "服务自检通过；真实处理效果仍需任务验证。",
                "missing_resources": "服务已连接，模型资源或执行进程尚未就绪。",
            }[readiness]
        return Topic1ToolServiceStatus(connection="online", readiness=readiness,
                                       message=message, checked_at=checked_at)
    except CorpusToolError as exc:
        return Topic1ToolServiceStatus(connection="unreachable", readiness="unknown",
                                       message=str(exc), checked_at=checked_at)
