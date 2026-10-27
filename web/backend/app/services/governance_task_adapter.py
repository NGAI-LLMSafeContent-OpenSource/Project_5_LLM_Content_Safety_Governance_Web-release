"""Uniform adapter boundary used by the governance task worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import uuid4

from app.schemas.governance import RISK_RESCAN_MAX_SAMPLES
from app.services.governance_risk_rescan_service import execute_input_risk_rescan


@dataclass(frozen=True)
class AdapterCapabilityDeclaration:
    capability: str
    version: str
    supports: set[str]


class _SampleDetectionAdapter:
    """Shared one-sample Adapter boundary for Probe-backed input capabilities."""

    _SUPPORTS = {
        "validate",
        "start",
        "status",
        "events",
        "artifact",
        "cancel",
        "execute_sample",
    }

    capability_key: str = ""
    missing_samples_message: str = "缺少冻结样本"
    over_limit_message: str = "超过服务端样本上限"
    missing_id_message: str = "冻结样本缺少标识"

    def __init__(
        self,
        runner: Callable[[dict], Awaitable[dict]],
    ) -> None:
        self._runner = runner
        self._runs: dict[str, dict] = {}

    def declare_capabilities(self) -> tuple[AdapterCapabilityDeclaration, ...]:
        return (
            AdapterCapabilityDeclaration(
                capability=self.capability_key,
                version="v1",
                supports=set(self._SUPPORTS),
            ),
        )

    def validate(self, scope: dict) -> dict:
        samples = scope.get("samples")
        if not isinstance(samples, list) or not samples:
            raise ValueError(self.missing_samples_message)
        if len(samples) > RISK_RESCAN_MAX_SAMPLES:
            raise ValueError(self.over_limit_message)
        if any(not str(sample.get("sample_id") or "") for sample in samples):
            raise ValueError(self.missing_id_message)
        return dict(scope)

    async def start(self, scope: dict) -> str:
        validated = self.validate(scope)
        if len(validated["samples"]) != 1:
            raise ValueError("Adapter 单次执行只允许一个冻结样本")
        handle = str(uuid4())
        self._runs[handle] = {
            "scope": validated,
            "outcome": await self._runner(validated),
        }
        return handle

    async def execute_sample(self, scope: dict) -> dict:
        """Execute one sample and return its normalized adapter artifact."""

        handle = await self.start(scope)
        return await self.artifact(handle)

    async def status(self, handle: str) -> str:
        return str(self._outcome(handle).get("status") or "failed")

    async def events(self, handle: str, *, after: int = 0) -> list[dict]:
        if after > 0:
            return []
        outcome = self._outcome(handle)
        samples = outcome.get("samples") or []
        total = 1
        sample = samples[0] if samples else {}
        completed = int(
            outcome.get("status") == "completed"
            and sample.get("status") in {"consistent", "inconsistent"}
        )
        failed = total - completed
        return [
            {
                "stage": "completed" if completed else "failed",
                "counts": {
                    "completed": completed,
                    "failed": failed,
                    "total": total,
                },
                "resource_refs": [],
            }
        ]

    async def artifact(self, handle: str) -> dict:
        return dict(self._outcome(handle))

    async def cancel(self, handle: str) -> None:
        outcome = self._outcome(handle)
        if outcome.get("status") not in {"completed", "failed", "timeout"}:
            outcome.update(status="cancelled", reason="任务已取消")

    def _run(self, handle: str) -> dict:
        try:
            return self._runs[handle]
        except KeyError as exc:
            raise ValueError("Adapter 运行标识不存在") from exc

    def _outcome(self, handle: str) -> dict:
        return self._run(handle)["outcome"]


class RiskCorpusRescanAdapter(_SampleDetectionAdapter):
    """Adapter for the real Topic-2 risk re-detection boundary."""

    capability_key = "risk_corpus_rescan"
    missing_samples_message = "风险二次检测缺少冻结样本"
    over_limit_message = "风险二次检测超过服务端样本上限"
    missing_id_message = "风险二次检测冻结样本缺少标识"

    def __init__(self) -> None:
        super().__init__(execute_input_risk_rescan)


def adapter_for(capability: str):
    if capability == "risk_corpus_rescan":
        return RiskCorpusRescanAdapter()
    raise ValueError(f"未登记任务 Adapter：{capability}")
