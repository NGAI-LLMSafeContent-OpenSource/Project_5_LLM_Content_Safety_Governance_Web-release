import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Topic4InputWorkflowUnavailable(RuntimeError):
    pass


class Topic4InputWorkflowClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.topic4_input_workflow_base_url.rstrip("/")
        self.timeout = float(settings.topic4_input_workflow_timeout_seconds)

    async def health(self) -> dict[str, Any]:
        return await self._get("/api/health")

    async def build_graph(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._post("/api/build_graph", {"records": records})

    async def merge_risk(
        self,
        *,
        lineage_graph: dict[str, Any],
        risk_annotations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._post(
            "/api/graph/merge",
            {
                "lineage_graph": lineage_graph,
                "risk_annotations": risk_annotations,
            },
        )

    async def run_full_workflow(
        self,
        *,
        records: list[dict[str, Any]],
        source: str,
        enable_cleaning: bool = True,
        cleaning_mode: str = "remove_risk_nodes",
        enable_neo4j: bool = False,
    ) -> dict[str, Any]:
        return await self._post(
            "/api/workflow/full_v2",
            {
                "records": records,
                "source": source,
                "enable_cleaning": enable_cleaning,
                "cleaning_mode": cleaning_mode,
                "enable_neo4j": enable_neo4j,
            },
        )

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.get(f"{self.base_url}{path}")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Topic4 input workflow GET failed: %s", path, exc_info=True)
            raise Topic4InputWorkflowUnavailable(str(exc)) from exc

        if not isinstance(payload, dict):
            raise Topic4InputWorkflowUnavailable("Topic4 response is not an object")
        return payload

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response is not None else ""
            logger.warning("Topic4 input workflow POST failed: %s", path, exc_info=True)
            raise Topic4InputWorkflowUnavailable(
                f"{path} returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Topic4 input workflow POST failed: %s", path, exc_info=True)
            raise Topic4InputWorkflowUnavailable(str(exc)) from exc

        if not isinstance(data, dict):
            raise Topic4InputWorkflowUnavailable("Topic4 response is not an object")
        return data


def build_topic4_input_workflow_client() -> Topic4InputWorkflowClient:
    return Topic4InputWorkflowClient()
